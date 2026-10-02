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


if __name__ == "__main__":
    unittest.main()
