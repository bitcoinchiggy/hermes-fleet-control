"""Control-local inbound allowlist. Preserves humans and the private key."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fleet_control.inbound_allow import (  # noqa: E402
    InboundAllowError,
    apply_inbound_authorization,
    inspect_inbound_authorization,
)
from fleet_control.support.nostr_codec import (  # noqa: E402
    derive_nostr_private_key,
    derive_nostr_public_key,
    encode_npub,
)

HUMAN = "12" * 32
EXTRA = "34" * 32
PRIVATE = "nsec1sentinelkeepme"


def _identity(seed: int) -> tuple[str, str]:
    secret = derive_nostr_private_key(bytes([seed]) + bytes(31))
    public = derive_nostr_public_key(secret)
    return public.hex(), encode_npub(public)


OPERATOR_HEX, OPERATOR_NPUB = _identity(7)
RESEARCHER_HEX, RESEARCHER_NPUB = _identity(8)


def _bare_profile() -> bytes:
    """The reported Control starting state: no allowlist variables at all."""
    return (
        f"BUZZ_PRIVATE_KEY={PRIVATE}\n"
        "BUZZ_RELAY_URL=wss://buzz.example/relay\n"
        "OTHER=kept\n"
    ).encode()


def _profile_bytes(users: str, *, allow: str = "false") -> bytes:
    return (
        f"BUZZ_PRIVATE_KEY={PRIVATE}\n"
        f"BUZZ_RELAY_URL=wss://buzz.example/relay\n"
        f"BUZZ_ALLOW_ALL_USERS={allow}\n"
        f"BUZZ_ALLOWED_USERS={users}\n"
        "OTHER=kept\n"
    ).encode()


def _workers() -> list[dict[str, object]]:
    return [
        {
            "name": "researcher",
            "observed": {"buzz_public_key_hex": RESEARCHER_HEX, "buzz_npub": RESEARCHER_NPUB},
        },
        {
            "name": "operator",
            "buzz_public_key_hex": OPERATOR_HEX,
            "buzz_npub": OPERATOR_NPUB,
            "observed": {"buzz_public_key_hex": OPERATOR_HEX, "buzz_npub": OPERATOR_NPUB},
        },
    ]


class InboundAllowTests(unittest.TestCase):
    def _layout(self, users: str, *, allow: str = "false") -> tuple[Path, Path]:
        root = Path(self.tmp.name)
        profile = root / "ops"
        profile.mkdir()
        env = profile / ".env"
        env.write_bytes(_profile_bytes(users, allow=allow))
        os.chmod(env, 0o600)
        other = root / "other"
        other.mkdir()
        (other / ".env").write_bytes(b"BUZZ_PRIVATE_KEY=nsec1other\nBUZZ_ALLOWED_USERS=aa\n")
        return root, env

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_extra_human_is_preserved_and_apply_is_idempotent(self) -> None:
        root, env = self._layout(f"{HUMAN},{EXTRA}")
        before = env.read_bytes()
        units = ("hermes-gateway-ops.service", "hermes-gateway.service")
        first = apply_inbound_authorization(
            profiles_root=str(root),
            configured_profile="ops",
            gateway_units=units,
            documents=_workers(),
        )
        self.assertEqual(
            first["allowed_users"],
            [HUMAN, EXTRA, OPERATOR_HEX, RESEARCHER_HEX],
        )
        self.assertTrue(first["changed"])
        self.assertFalse(first["allow_all_users"])
        self.assertEqual(first["profile"], "ops")
        updated = env.read_bytes()
        self.assertIn(PRIVATE.encode(), updated)
        self.assertNotIn(PRIVATE, json.dumps(first))
        self.assertIn(b"OTHER=kept\n", updated)
        self.assertIn(EXTRA.encode(), updated)
        second = apply_inbound_authorization(
            profiles_root=str(root),
            configured_profile="ops",
            gateway_units=units,
            documents=_workers(),
        )
        self.assertFalse(second["changed"])
        self.assertEqual(env.read_bytes(), updated)
        self.assertEqual(second["allowed_users"], first["allowed_users"])
        self.assertNotEqual(updated, before)
        other = (root / "other" / ".env").read_bytes()
        self.assertEqual(other, b"BUZZ_PRIVATE_KEY=nsec1other\nBUZZ_ALLOWED_USERS=aa\n")

    def test_quoted_existing_humans_are_preserved(self) -> None:
        root = Path(self.tmp.name)
        profile = root / "ops"
        profile.mkdir()
        env = profile / ".env"
        env.write_bytes(
            (
                f"BUZZ_PRIVATE_KEY='{PRIVATE}'\n"
                "export BUZZ_ALLOW_ALL_USERS=\"false\"\n"
                f"BUZZ_ALLOWED_USERS=\"{EXTRA},{HUMAN}\"\n"
            ).encode()
        )
        os.chmod(env, 0o600)
        result = apply_inbound_authorization(
            profiles_root=str(root),
            configured_profile="ops",
            gateway_units=("hermes-gateway-ops.service",),
            documents=_workers(),
        )
        self.assertEqual(result["allowed_users"][:2], [EXTRA, HUMAN])
        updated = env.read_bytes()
        self.assertIn(f"BUZZ_PRIVATE_KEY='{PRIVATE}'".encode(), updated)
        self.assertNotIn(PRIVATE, json.dumps(result))

    def test_missing_allowlist_variables_keep_pairing_and_config_humans(self) -> None:
        root = Path(self.tmp.name)
        profile = root / "ops"
        profile.mkdir()
        env = profile / ".env"
        env.write_bytes(_bare_profile())
        os.chmod(env, 0o600)
        pairing = profile / "platforms" / "pairing"
        pairing.mkdir(parents=True)
        (pairing / "buzz-approved.json").write_text(
            json.dumps({EXTRA: {"user_name": "display-not-for-stdout", "approved_at": 1}})
        )
        config_hex, config_npub = _identity(9)
        (profile / "config.yaml").write_text(
            "gateway:\n"
            "  platforms:\n"
            "    buzz:\n"
            "      extra:\n"
            "        allow_from:\n"
            f"          - {config_npub}\n"
        )
        before = env.read_bytes()
        units = ("hermes-gateway-ops.service",)
        inspected = inspect_inbound_authorization(
            profiles_root=str(root),
            configured_profile="ops",
            gateway_units=units,
        )
        self.assertEqual(env.read_bytes(), before)
        self.assertFalse(inspected["allow_all_users"])
        self.assertEqual(inspected["allow_all_source"], "hermes_default")
        self.assertEqual(inspected["authorized_humans"], [EXTRA, config_hex])
        self.assertEqual(inspected["human_sources"], ["pairing", "config_allow_from"])
        self.assertNotIn(PRIVATE, json.dumps(inspected))
        self.assertNotIn("display-not-for-stdout", json.dumps(inspected))
        first = apply_inbound_authorization(
            profiles_root=str(root),
            configured_profile="ops",
            gateway_units=units,
            documents=_workers(),
        )
        self.assertEqual(first["allowed_users"][:2], [EXTRA, config_hex])
        self.assertEqual(first["allowed_users"][2:], [OPERATOR_HEX, RESEARCHER_HEX])
        self.assertEqual(first["allow_all_source"], "hermes_default")
        updated = env.read_bytes()
        self.assertIn(b"BUZZ_ALLOW_ALL_USERS=false\n", updated)
        self.assertIn(PRIVATE.encode(), updated)
        self.assertNotIn(PRIVATE, json.dumps(first))
        second = apply_inbound_authorization(
            profiles_root=str(root),
            configured_profile="ops",
            gateway_units=units,
            documents=_workers(),
        )
        self.assertFalse(second["changed"])
        self.assertEqual(env.read_bytes(), updated)

    def test_config_allowlist_is_not_widened_by_pairing(self) -> None:
        root = Path(self.tmp.name)
        profile = root / "ops"
        profile.mkdir()
        env = profile / ".env"
        env.write_bytes(_bare_profile())
        os.chmod(env, 0o600)
        pairing = profile / "pairing"
        pairing.mkdir()
        (pairing / "buzz-approved.json").write_text(json.dumps({EXTRA: {}}))
        config_hex, config_npub = _identity(9)
        (profile / "config.yaml").write_text(
            "platforms:\n  buzz:\n    extra:\n      allowed_users:\n"
            f"        - {config_npub}\n"
        )
        result = apply_inbound_authorization(
            profiles_root=str(root),
            configured_profile="ops",
            gateway_units=("hermes-gateway-ops.service",),
            documents=_workers(),
        )
        self.assertEqual(result["authorized_humans"], [config_hex])
        self.assertNotIn(EXTRA, result["allowed_users"])
        self.assertEqual(result["human_sources"], ["config_allowed_users"])

    def test_open_or_unreadable_authorization_does_not_write(self) -> None:
        root = Path(self.tmp.name)
        profile = root / "ops"
        profile.mkdir()
        env = profile / ".env"
        env.write_bytes(_bare_profile() + b"GATEWAY_ALLOW_ALL_USERS=true\n")
        os.chmod(env, 0o600)
        original = env.read_bytes()
        with self.assertRaises(InboundAllowError) as caught:
            apply_inbound_authorization(
                profiles_root=str(root),
                configured_profile="ops",
                gateway_units=("hermes-gateway-ops.service",),
                documents=_workers(),
            )
        self.assertIn("allow_all_users", caught.exception.public_message)
        self.assertEqual(env.read_bytes(), original)
        env.write_bytes(_bare_profile())
        (profile / "config.yaml").write_text("gateway: [\n")
        with self.assertRaises(InboundAllowError) as caught:
            apply_inbound_authorization(
                profiles_root=str(root),
                configured_profile="ops",
                gateway_units=("hermes-gateway-ops.service",),
                documents=_workers(),
            )
        self.assertIn("cannot be established", caught.exception.public_message)
        self.assertEqual(env.read_bytes(), _bare_profile())
        (profile / "config.yaml").unlink()
        pairing = profile / "platforms" / "pairing"
        pairing.mkdir(parents=True)
        (pairing / "buzz-approved.json").write_text("{")
        with self.assertRaises(InboundAllowError):
            apply_inbound_authorization(
                profiles_root=str(root),
                configured_profile="ops",
                gateway_units=("hermes-gateway-ops.service",),
                documents=_workers(),
            )
        self.assertEqual(env.read_bytes(), _bare_profile())

    def test_pairing_keys_hermes_would_not_match_do_not_write(self) -> None:
        root = Path(self.tmp.name)
        profile = root / "ops"
        profile.mkdir()
        env = profile / ".env"
        env.write_bytes(_bare_profile())
        os.chmod(env, 0o600)
        pairing = profile / "platforms" / "pairing"
        pairing.mkdir(parents=True)
        lower_hex, npub = _identity(9)
        self.assertNotEqual(lower_hex, lower_hex.upper())
        (pairing / "buzz-approved.json").write_text(
            json.dumps({lower_hex.upper(): {}, npub: {}})
        )
        with self.assertRaises(InboundAllowError) as caught:
            inspect_inbound_authorization(
                profiles_root=str(root),
                configured_profile="ops",
                gateway_units=("hermes-gateway-ops.service",),
            )
        self.assertIn("cannot be established", caught.exception.public_message)
        self.assertEqual(env.read_bytes(), _bare_profile())

    def test_gateway_allowlist_keeps_only_forms_hermes_matches(self) -> None:
        root = Path(self.tmp.name)
        profile = root / "ops"
        profile.mkdir()
        env = profile / ".env"
        kept, _kept_npub = _identity(4)
        skipped = ("ab" * 32).upper()
        other_hex, other_npub = _identity(5)
        env.write_bytes(
            _bare_profile()
            + f"GATEWAY_ALLOWED_USERS={kept},{skipped},{other_npub},telegram-42\n".encode()
        )
        os.chmod(env, 0o600)
        inspected = inspect_inbound_authorization(
            profiles_root=str(root),
            configured_profile="ops",
            gateway_units=("hermes-gateway-ops.service",),
        )
        self.assertEqual(inspected["authorized_humans"], [kept, other_hex])
        self.assertEqual(inspected["human_sources"], ["gateway_allowed_users"])
        self.assertNotIn(skipped.lower(), inspected["authorized_humans"])

    def test_profile_mismatch_and_allow_all_do_not_write(self) -> None:
        root, env = self._layout(HUMAN)
        original = env.read_bytes()
        with self.assertRaises(InboundAllowError):
            apply_inbound_authorization(
                profiles_root=str(root),
                configured_profile="control",
                gateway_units=("hermes-gateway-ops.service",),
                documents=_workers(),
            )
        with self.assertRaises(InboundAllowError):
            apply_inbound_authorization(
                profiles_root=str(root),
                configured_profile="ops",
                gateway_units=("hermes-gateway-ops.service", "hermes-gateway-other.service"),
                documents=_workers(),
            )
        self.assertEqual(env.read_bytes(), original)
        allow_all = root / "wide"
        allow_all.mkdir()
        wide = allow_all / ".env"
        wide.write_bytes(_profile_bytes(HUMAN, allow="true"))
        with self.assertRaises(InboundAllowError) as caught:
            apply_inbound_authorization(
                profiles_root=str(root),
                configured_profile="wide",
                gateway_units=("hermes-gateway-wide.service",),
                documents=_workers(),
            )
        self.assertIn("allow_all_users", caught.exception.public_message)
        self.assertEqual(wide.read_bytes(), _profile_bytes(HUMAN, allow="true"))

    def test_unverified_worker_and_private_material_do_not_write(self) -> None:
        root, env = self._layout(HUMAN)
        original = env.read_bytes()
        bad = _workers()
        bad[1]["buzz_npub"] = RESEARCHER_NPUB
        bad[1]["observed"]["buzz_npub"] = RESEARCHER_NPUB
        with self.assertRaises(InboundAllowError):
            apply_inbound_authorization(
                profiles_root=str(root),
                configured_profile="ops",
                gateway_units=("hermes-gateway-ops.service",),
                documents=bad,
            )
        with self.assertRaises(InboundAllowError):
            apply_inbound_authorization(
                profiles_root=str(root),
                configured_profile="ops",
                gateway_units=("hermes-gateway-ops.service",),
                documents=[
                    {"name": "operator", "buzz_public_key_hex": OPERATOR_HEX, "nsec": "nsec1qq"},
                    {"name": "researcher", "buzz_public_key_hex": RESEARCHER_HEX, "buzz_npub": RESEARCHER_NPUB},
                ],
            )
        self.assertEqual(env.read_bytes(), original)

    def test_cli_preserves_extra_humans_without_printing_the_private_key(self) -> None:
        root, env = self._layout(f"{EXTRA},{HUMAN}")
        venv = Path(self.tmp.name) / "venv"
        subprocess.run(
            [sys.executable, "-m", "venv", "--system-site-packages", str(venv)],
            check=True,
            capture_output=True,
        )
        python = venv / "bin" / "python"
        real = os.path.realpath(sys.executable)
        if os.path.realpath(python) != real:
            python.unlink()
            python.symlink_to(real)
        payload = json.dumps({"gateway_units": ["hermes-gateway-ops.service"], "workers": _workers()})
        proc = subprocess.run(
            [sys.executable, str(ROOT / "fleet-allow-inbound")],
            input=payload.encode(),
            env={
                "PATH": "/usr/bin:/bin",
                "FLEET_CONTROL_PYTHON": str(python),
                "FLEET_CONTROL_HERMES_PROFILE": "ops",
                "FLEET_CONTROL_PROFILES_ROOT": str(root),
            },
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        body = json.loads(proc.stdout)
        self.assertEqual(body["allowed_users"][:2], [EXTRA, HUMAN])
        self.assertEqual(body["allowed_users"][2:], [OPERATOR_HEX, RESEARCHER_HEX])
        self.assertNotIn(PRIVATE, proc.stdout.decode())
        self.assertIn(PRIVATE.encode(), env.read_bytes())
        poisoned = subprocess.run(
            [sys.executable, str(ROOT / "fleet-allow-inbound")],
            input=payload.encode(),
            env={
                "PATH": "/usr/bin:/bin",
                "FLEET_CONTROL_PYTHON": str(python),
                "FLEET_CONTROL_HERMES_PROFILE": "ops",
                "FLEET_CONTROL_PROFILES_ROOT": str(root),
                "PVE_TOKEN_SECRET": "not-a-real-secret",
            },
            capture_output=True,
            check=False,
        )
        self.assertEqual(poisoned.returncode, 1)
        self.assertNotIn(b"not-a-real-secret", poisoned.stdout)
        self.assertNotIn(b"not-a-real-secret", poisoned.stderr)
        env.write_bytes(_bare_profile())
        pairing = root / "ops" / "platforms" / "pairing"
        pairing.mkdir(parents=True)
        (pairing / "buzz-approved.json").write_text(json.dumps({EXTRA: {"user_name": "hidden-name"}}))
        (root / "ops" / "config.yaml").write_text("gateway:\n  allow_all_users: false\n")
        before = env.read_bytes()
        diagnosed = subprocess.run(
            [sys.executable, str(ROOT / "fleet-allow-inbound")],
            input=json.dumps({"diagnose": True, "gateway_units": ["hermes-gateway-ops.service"]}).encode(),
            env={
                "PATH": "/usr/bin:/bin",
                "FLEET_CONTROL_PYTHON": str(python),
                "FLEET_CONTROL_HERMES_PROFILE": "ops",
                "FLEET_CONTROL_PROFILES_ROOT": str(root),
            },
            capture_output=True,
            check=False,
        )
        self.assertEqual(diagnosed.returncode, 0, diagnosed.stderr.decode())
        body = json.loads(diagnosed.stdout)
        self.assertTrue(body["diagnose"])
        self.assertEqual(body["allow_all_source"], "config")
        self.assertEqual(body["authorized_humans"], [EXTRA])
        self.assertNotIn(PRIVATE, diagnosed.stdout.decode())
        self.assertNotIn("hidden-name", diagnosed.stdout.decode())
        self.assertEqual(env.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
