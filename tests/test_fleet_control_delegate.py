#!/usr/bin/env python3
"""Control delegate_worker. Fake Fleet HTTP and a fake Buzz CLI. No network."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from io import BytesIO, StringIO
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fleet_control.buzz_exec import BuzzTimeout, delegation_stdin, send_argv
from fleet_control.delegate import DELEGATION_ID_RE, delegate_worker, main as delegate_main
from fleet_control.errors import ControlError, MESSAGES
from fleet_control.journal import fresh_record, write_record
from fleet_control.support.nostr_codec import (
    derive_nostr_private_key,
    derive_nostr_public_key,
    encode_npub,
    encode_nsec,
)

CONTROL_SECRET = derive_nostr_private_key(bytes([1]) + bytes(31))
WORKER_SECRET = derive_nostr_private_key(bytes([2]) + bytes(31))
OTHER_SECRET = derive_nostr_private_key(bytes([3]) + bytes(31))
CONTROL_HEX = derive_nostr_public_key(CONTROL_SECRET).hex()
WORKER_HEX = derive_nostr_public_key(WORKER_SECRET).hex()
OTHER_HEX = derive_nostr_public_key(OTHER_SECRET).hex()
CONTROL_NSEC = encode_nsec(CONTROL_SECRET)
WORKER_NPUB = encode_npub(derive_nostr_public_key(WORKER_SECRET))
CONTROL_NPUB = encode_npub(derive_nostr_public_key(CONTROL_SECRET))
OTHER_NPUB = encode_npub(derive_nostr_public_key(OTHER_SECRET))
DM_ID = "11111111-1111-4111-8111-111111111111"
EVENT_ID = "ab" * 32
SUPPLIED_ID = "dlg_" + "cd" * 16
FLEET_FILE = (
    b"FLEET_PROVISIONER_URL=https://fleet.example\n"
    b"FLEET_PROVISIONER_CALLER_TOKEN=test-caller-token\n"
)
TASK = "Summarize the queue"


def assert_absent(blob: str, secret: str) -> None:
    if secret and secret in blob:
        raise AssertionError("secret material appeared in a public artifact")


def profile_bytes(nsec: str = CONTROL_NSEC, relay: str = "wss://buzz.example/") -> bytes:
    return f"BUZZ_PRIVATE_KEY={nsec}\nBUZZ_RELAY_URL={relay}\n".encode("utf-8")


def public_worker(**overrides) -> dict:
    """Literal public worker document. No private observed fields."""
    observed = {
        "state": "ready",
        "buzz_npub": WORKER_NPUB,
        "buzz_public_key_hex": WORKER_HEX,
        "buzz_configured": True,
        "buzz_relay_url": "wss://buzz.example/",
        "buzz_profile_published": True,
        "buzz_gateway_active": True,
        "buzz_relay_member": True,
    }
    observed.update(overrides.pop("observed", {}))
    reconciliation = {
        "id": None,
        "request_id": None,
        "status": "idle",
        "last_success_at": None,
        "last_attempt_at": None,
        "last_error": None,
    }
    reconciliation.update(overrides.pop("reconciliation", {}))
    requested = overrides.pop("requested", {"state": "ready"})
    body = {
        "api_version": "v1",
        "kind": "Worker",
        "name": "operator",
        "declared": True,
        "requested": requested,
        "observed": observed,
        "reconciliation": reconciliation,
        "tombstone": None,
    }
    body.update(overrides)
    return body


class FleetHTTP:
    def __init__(self, body: dict, status: int = 200):
        self.body = body
        self.status = status
        self.calls: list[tuple] = []

    def __call__(self, method, url, headers, payload):
        self.calls.append((method, url, dict(headers), payload))
        return self.status, json.dumps(self.body).encode("utf-8")


class Buzz:
    def __init__(self, *, created: bool = True, open_code: int = 0, open_stdout: bytes | None = None, send=None):
        self.created = created
        self.open_code = open_code
        self.open_stdout = open_stdout
        self.send = send
        self.calls: list[dict] = []

    def __call__(self, argv, env, stdin, on_started=None):
        self.calls.append({"argv": list(argv), "env": dict(env), "stdin": bytes(stdin)})
        if argv[1:3] == ["dms", "open"]:
            stdout = self.open_stdout if self.open_stdout is not None else dm_stdout(self.created)
            return self.open_code, stdout, b"child-stderr"
        if on_started is not None:
            on_started()
        action = self.send() if callable(self.send) else self.send
        if isinstance(action, Exception):
            raise action
        code, stdout = action if action is not None else (0, send_stdout())
        return code, stdout, b"child-stderr"


def dm_stdout(created: bool, dm_id: str = DM_ID) -> bytes:
    message = "response:" + json.dumps({"channel_id": dm_id, "created": created}, separators=(",", ":"))
    return json.dumps(
        {"accepted": True, "dm_id": dm_id, "message": message},
        separators=(",", ":"),
    ).encode("utf-8")


def send_stdout(accepted: bool = True, event_id: str = EVENT_ID) -> bytes:
    body = {"accepted": accepted, "message": "stored" if accepted else "rejected"}
    if accepted:
        body["event_id"] = event_id
    return json.dumps(body).encode("utf-8")


class DelegateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = Path(self.tmp.name) / "delegations"
        self.http = FleetHTTP(public_worker())
        self.buzz = Buzz()
        self.env = {
            "FLEET_CONTROL_HERMES_PROFILE": "control",
            "FLEET_CONTROL_BUZZ_BIN": "/usr/local/bin/buzz",
            "PATH": "/tmp/parent-path-must-not-leak",
            "LANG": "C.UTF-8",
            "SECRET_PARENT": "parent-secret",
            "FLEET_PROVISIONER_CALLER_TOKEN": "test-caller-token",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def delegate(self, payload=None, **kwargs):
        defaults = {
            "environ": self.env,
            "fleet_file_bytes": FLEET_FILE,
            "profile_env_bytes": profile_bytes(),
            "transport": self.http,
            "buzz_runner": self.buzz,
            "journal_dir": self.journal,
        }
        defaults.update(kwargs)
        return delegate_worker(payload if payload is not None else {"worker": "operator", "task": TASK}, **defaults)

    def test_public_document_is_the_authorization_source(self):
        body = public_worker()
        for field in (
            "buzz_npub",
            "buzz_public_key_hex",
            "buzz_configured",
            "buzz_relay_url",
            "buzz_profile_published",
            "buzz_gateway_active",
            "buzz_relay_member",
            "state",
        ):
            self.assertIn(field, body["observed"])
        self.assertNotIn("litellm_key_token", json.dumps(body))
        self.assertTrue(body["declared"])
        self.assertEqual(body["observed"]["buzz_public_key_hex"], WORKER_HEX)

    def test_valid_delegate_new_and_existing_dm(self):
        for created in (True, False):
            with self.subTest(created=created):
                self.buzz = Buzz(created=created)
                result = self.delegate(profile_reader=lambda *_a: (_ for _ in ()).throw(AssertionError("opened")))
                self.assertEqual(
                    result,
                    {
                        "accepted": True,
                        "delivery": "relay_accepted",
                        "delegation_id": result["delegation_id"],
                        "worker": "operator",
                        "channel_id": DM_ID,
                        "event_id": EVENT_ID,
                    },
                )
                self.assertTrue(DELEGATION_ID_RE.fullmatch(result["delegation_id"]))
                self.assertEqual(result["delivery"], "relay_accepted")
                self.assertNotIn("completed", json.dumps(result))
                self._assert_buzz_contract(result["delegation_id"])
                self._assert_journal_private(result["delegation_id"])

    def test_supplied_id_prefix_and_idempotent_retry(self):
        payload = {"worker": "operator", "task": "/hide", "delegation_id": SUPPLIED_ID}
        opened = {"n": 0}

        def reader(_profile, _root):
            opened["n"] += 1
            return profile_bytes()

        first = self.delegate(payload, profile_env_bytes=None, profile_reader=reader)
        self.assertEqual(first["delegation_id"], SUPPLIED_ID)
        stdin = self.buzz.calls[1]["stdin"].decode("utf-8")
        self.assertEqual(stdin, f"[fleet-delegation {SUPPLIED_ID}]\n/hide")
        self.assertTrue(stdin.startswith("[fleet-delegation "))
        self.assertNotIn("/hide", self.buzz.calls[1]["argv"])
        calls = len(self.buzz.calls)
        second = self.delegate(payload, profile_env_bytes=None, profile_reader=reader)
        self.assertEqual(second, first)
        self.assertEqual(len(self.buzz.calls), calls)
        self.assertEqual(len(self.http.calls), 1)
        self.assertEqual(opened["n"], 1)

    def test_generated_id_and_real_process_argv(self):
        script = Path(self.tmp.name) / "buzz"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import hashlib, json, os, sys\n"
            "from pathlib import Path\n"
            "key = os.environ.get('BUZZ_PRIVATE_KEY', '')\n"
            "record = {\n"
            "  'argv': sys.argv,\n"
            "  'stdin': sys.stdin.read(),\n"
            "  'env_names': sorted(os.environ),\n"
            "  'key_sha256': hashlib.sha256(key.encode()).hexdigest(),\n"
            "  'key_in_argv': any('nsec' in part or 'BUZZ_PRIVATE_KEY' in part for part in sys.argv),\n"
            "}\n"
            "Path(sys.argv[0]).with_suffix('.log').open('a').write(json.dumps(record) + '\\n')\n"
            "if sys.argv[1:3] == ['dms', 'open']:\n"
            f"    print({dm_stdout(True).decode()!r})\n"
            "elif sys.argv[1:3] == ['messages', 'send']:\n"
            f"    print({send_stdout().decode()!r})\n"
            "else:\n"
            "    raise SystemExit(2)\n"
        )
        os.chmod(script, 0o755)
        env = dict(self.env)
        env["FLEET_CONTROL_BUZZ_BIN"] = str(script)
        result = self.delegate(environ=env, buzz_runner=None)
        lines = [json.loads(line) for line in script.with_suffix(".log").read_text().splitlines()]
        self.assertEqual(lines[0]["argv"][1:], ["dms", "open", "--pubkey", WORKER_HEX])
        self.assertEqual(
            lines[1]["argv"][1:],
            ["messages", "send", "--channel", DM_ID, "--mention", WORKER_HEX, "--content", "-"],
        )
        self.assertEqual(lines[1]["stdin"], delegation_stdin(result["delegation_id"], TASK).decode())
        self.assertFalse(lines[0]["key_in_argv"])
        self.assertFalse(lines[1]["key_in_argv"])
        self.assertEqual(lines[1]["key_sha256"], hashlib.sha256(CONTROL_NSEC.encode()).hexdigest())
        self.assertNotIn("SECRET_PARENT", lines[1]["env_names"])
        self.assertNotIn("BUZZ_FLEET_MEMBERSHIP_TOKEN", lines[1]["env_names"])
        self.assertNotIn("FLEET_PROVISIONER_CALLER_TOKEN", lines[1]["env_names"])
        self.assertEqual(
            [name for name in lines[1]["env_names"] if name.startswith("BUZZ_")],
            ["BUZZ_PRIVATE_KEY", "BUZZ_RELAY_URL"],
        )
        source = (REPO / "fleet_control" / "buzz_exec.py").read_text()
        self.assertIn("shell=False", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", (REPO / "fleet_control" / "delegate.py").read_text())

    def test_send_addresses_only_the_fleet_resolved_worker(self):
        """The message p-tag is the authorized worker key, never caller text."""
        other_task = f"note --mention {OTHER_HEX}"
        result = self.delegate(
            {
                "worker": "operator",
                "task": other_task,
                "delegation_id": "dlg_" + "44" * 16,
            }
        )
        self.assertEqual(result["worker"], "operator")
        sent = self.buzz.calls[1]
        self.assertEqual(
            sent["argv"],
            [
                "/usr/local/bin/buzz",
                "messages",
                "send",
                "--channel",
                DM_ID,
                "--mention",
                WORKER_HEX,
                "--content",
                "-",
            ],
        )
        self.assertNotIn(OTHER_HEX, sent["argv"])
        self.assertIn(OTHER_HEX, sent["stdin"].decode())
        self.assertEqual(self.buzz.calls[0]["argv"][-1], WORKER_HEX)

        steered = Buzz()
        with self.assertRaises(ControlError) as caught:
            self.delegate(
                {
                    "worker": "operator",
                    "task": TASK,
                    "mention": OTHER_HEX,
                    "pubkey": OTHER_HEX,
                    "channel": DM_ID,
                },
                buzz_runner=steered,
            )
        self.assertEqual(caught.exception.code, "invalid_request")
        self.assertEqual(steered.calls, [])

        alternate = public_worker(
            observed={"buzz_public_key_hex": OTHER_HEX, "buzz_npub": OTHER_NPUB}
        )
        alternate_buzz = Buzz()
        self.delegate(
            {
                "worker": "operator",
                "task": "use the fleet identity",
                "delegation_id": "dlg_" + "55" * 16,
            },
            transport=FleetHTTP(alternate),
            buzz_runner=alternate_buzz,
        )
        self.assertEqual(
            alternate_buzz.calls[0]["argv"],
            ["/usr/local/bin/buzz", "dms", "open", "--pubkey", OTHER_HEX],
        )
        self.assertEqual(
            alternate_buzz.calls[1]["argv"],
            [
                "/usr/local/bin/buzz",
                "messages",
                "send",
                "--channel",
                DM_ID,
                "--mention",
                OTHER_HEX,
                "--content",
                "-",
            ],
        )
        self.assertNotIn(WORKER_HEX, alternate_buzz.calls[1]["argv"])
        with self.assertRaises(ControlError) as caught:
            send_argv("/usr/local/bin/buzz", DM_ID, OTHER_HEX.upper())
        self.assertEqual(caught.exception.code, "helper_failed")
        with self.assertRaises(ControlError) as caught:
            send_argv("/usr/local/bin/buzz", "--channel", WORKER_HEX)
        self.assertEqual(caught.exception.code, "helper_failed")

    def test_closed_failures_do_not_send(self):
        cases = {
            "undeclared": (FleetHTTP(public_worker(declared=False)), "undeclared_worker"),
            "missing": (FleetHTTP({}, status=404), "undeclared_worker"),
            "renaming": (FleetHTTP(public_worker(observed={"state": "renaming"})), "worker_not_ready"),
            "not_requested": (FleetHTTP(public_worker(requested={"state": "absent"})), "worker_not_ready"),
            "reconciling": (FleetHTTP(public_worker(reconciliation={"status": "running"})), "reconciliation_unsafe"),
            "failed_recon": (FleetHTTP(public_worker(reconciliation={"status": "failed"})), "reconciliation_unsafe"),
            "gateway": (FleetHTTP(public_worker(observed={"buzz_gateway_active": False})), "gateway_inactive"),
            "gateway_string": (FleetHTTP(public_worker(observed={"buzz_gateway_active": "true"})), "gateway_inactive"),
            "member": (FleetHTTP(public_worker(observed={"buzz_relay_member": False})), "buzz_not_converged"),
            "profile": (FleetHTTP(public_worker(observed={"buzz_profile_published": False})), "buzz_not_converged"),
            "tombstone": (FleetHTTP(public_worker(tombstone={"name": "operator"})), "worker_not_ready"),
            "unconfigured": (FleetHTTP(public_worker(observed={"buzz_configured": False})), "buzz_identity_incomplete"),
            "bad_hex": (FleetHTTP(public_worker(observed={"buzz_public_key_hex": WORKER_HEX.upper()})), "buzz_identity_incomplete"),
            "bad_npub": (FleetHTTP(public_worker(observed={"buzz_npub": OTHER_NPUB})), "buzz_identity_incomplete"),
        }
        for name, (transport, code) in cases.items():
            with self.subTest(name=name):
                buzz = Buzz()
                with self.assertRaises(ControlError) as caught:
                    self.delegate(transport=transport, buzz_runner=buzz)
                self.assertEqual(caught.exception.code, code)
                self.assertTrue(DELEGATION_ID_RE.fullmatch(caught.exception.delegation_id or ""))
                self.assertEqual(caught.exception.public_body()["delegation_id"], caught.exception.delegation_id)
                self.assertEqual(buzz.calls, [])
                assert_absent(str(caught.exception), CONTROL_NSEC)
                assert_absent(repr(caught.exception), CONTROL_NSEC)
        mismatched = public_worker()
        mismatched["name"] = "someone"
        with self.assertRaises(ControlError) as caught:
            self.delegate(transport=FleetHTTP(mismatched))
        self.assertEqual(caught.exception.code, "undeclared_worker")

    def test_relay_mismatch_and_self_target_and_bad_profile(self):
        buzz = Buzz()
        with self.assertRaises(ControlError) as caught:
            self.delegate(profile_env_bytes=profile_bytes(relay="https://other.example"), buzz_runner=buzz)
        self.assertEqual(caught.exception.code, "relay_mismatch")
        self.assertTrue(DELEGATION_ID_RE.fullmatch(caught.exception.delegation_id or ""))
        self.assertEqual(buzz.calls, [])

        self_body = public_worker(observed={"buzz_public_key_hex": CONTROL_HEX, "buzz_npub": CONTROL_NPUB})
        with self.assertRaises(ControlError) as caught:
            self.delegate(transport=FleetHTTP(self_body), buzz_runner=buzz)
        self.assertEqual(caught.exception.code, "self_target")
        self.assertTrue(DELEGATION_ID_RE.fullmatch(caught.exception.delegation_id or ""))
        self.assertEqual(buzz.calls, [])

        with self.assertRaises(ControlError) as caught:
            self.delegate(profile_env_bytes=b"BUZZ_RELAY_URL=wss://buzz.example/\n", buzz_runner=buzz)
        self.assertEqual(caught.exception.code, "control_profile_unusable")

        with self.assertRaises(ControlError) as caught:
            self.delegate(profile_env_bytes=b"BUZZ_PRIVATE_KEY=not-a-key\nBUZZ_RELAY_URL=wss://buzz.example/\n")
        self.assertEqual(caught.exception.code, "control_profile_unusable")
        assert_absent(str(caught.exception), "not-a-key")

    def test_dm_and_send_outcomes(self):
        with self.assertRaises(ControlError) as caught:
            self.delegate(buzz_runner=Buzz(open_code=1, open_stdout=b""))
        self.assertEqual(caught.exception.code, "dm_open_failed")
        self.assertEqual(caught.exception.message, MESSAGES["dm_open_failed"])
        self.assertTrue(DELEGATION_ID_RE.fullmatch(caught.exception.delegation_id or ""))
        self.assertEqual(json.loads((self.journal / f"{self._only_record().name}").read_text())["state"], "failed")

        buzz = Buzz(open_stdout=b'{"accepted": true}')
        with self.assertRaises(ControlError) as caught:
            self.delegate(buzz_runner=buzz, payload={"worker": "operator", "task": "again", "delegation_id": "dlg_" + "11" * 16})
        self.assertEqual(caught.exception.code, "dm_open_malformed")
        self.assertEqual(caught.exception.delegation_id, "dlg_" + "11" * 16)
        self.assertEqual(len(buzz.calls), 1)

        rejected = self._retry_send(send_stdout(False), "send_rejected", "failed")
        self.assertEqual(rejected, "failed")
        ambiguous = self._retry_send(b"not-json", "send_ambiguous", "ambiguous")
        self.assertEqual(ambiguous, "ambiguous")

    def test_retry_after_clear_failure_and_not_after_ambiguous(self):
        sends = {"n": 0}

        def send():
            sends["n"] += 1
            if sends["n"] == 1:
                return 0, send_stdout(False)
            return 0, send_stdout()

        payload = {"worker": "operator", "task": TASK, "delegation_id": SUPPLIED_ID}
        buzz = Buzz(send=send)
        with self.assertRaises(ControlError) as caught:
            self.delegate(payload, buzz_runner=buzz)
        self.assertEqual(caught.exception.code, "send_rejected")
        self.assertEqual(caught.exception.delegation_id, SUPPLIED_ID)
        result = self.delegate(payload, buzz_runner=buzz)
        self.assertEqual(result["event_id"], EVENT_ID)
        self.assertEqual(sends["n"], 2)

        other = "dlg_" + "22" * 16
        buzz2 = Buzz(send=BuzzTimeout())
        with self.assertRaises(ControlError) as caught:
            self.delegate(
                {"worker": "operator", "task": TASK, "delegation_id": other},
                buzz_runner=buzz2,
            )
        self.assertEqual(caught.exception.code, "send_ambiguous")
        self.assertEqual(caught.exception.delegation_id, other)
        calls = len(buzz2.calls)
        with self.assertRaises(ControlError) as caught:
            self.delegate(
                {"worker": "operator", "task": TASK, "delegation_id": other},
                buzz_runner=buzz2,
            )
        self.assertEqual(caught.exception.code, "delegation_ambiguous")
        self.assertEqual(caught.exception.delegation_id, other)
        self.assertEqual(len(buzz2.calls), calls)

    def test_conflict_and_concurrent_suppression(self):
        payload = {"worker": "operator", "task": TASK, "delegation_id": SUPPLIED_ID}
        first = self.delegate(payload)
        with self.assertRaises(ControlError) as caught:
            self.delegate({**payload, "task": "different body"})
        self.assertEqual(caught.exception.code, "delegation_conflict")
        self.assertEqual(caught.exception.delegation_id, SUPPLIED_ID)
        with self.assertRaises(ControlError) as caught:
            self.delegate({**payload, "worker": "other"})
        self.assertEqual(caught.exception.code, "delegation_conflict")
        self.assertEqual(caught.exception.delegation_id, SUPPLIED_ID)
        self.assertEqual(len(self.buzz.calls), 2)
        self.assertEqual(self.delegate(payload)["event_id"], first["event_id"])

        held = threading.Event()
        release = threading.Event()

        def runner(argv, env, stdin, on_started=None):
            if argv[1:3] == ["messages", "send"]:
                held.set()
                self.assertTrue(release.wait(5))
            return Buzz(created=False)(argv, env, stdin, on_started)

        ident = "dlg_" + "33" * 16
        results: list = []

        def run():
            try:
                results.append(self.delegate({"worker": "operator", "task": "one", "delegation_id": ident}, buzz_runner=runner))
            except ControlError as exc:
                results.append(exc)

        thread = threading.Thread(target=run)
        thread.start()
        self.assertTrue(held.wait(5))
        with self.assertRaises(ControlError) as caught:
            self.delegate({"worker": "operator", "task": "one", "delegation_id": ident}, buzz_runner=runner)
        self.assertEqual(caught.exception.code, "delegation_in_flight")
        self.assertEqual(caught.exception.delegation_id, ident)
        self.assertEqual(caught.exception.public_body()["delegation_id"], ident)
        release.set()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertTrue(results[0]["accepted"])

    def test_journal_permissions_and_no_secret_material(self):
        previous = os.umask(0o022)
        try:
            result = self.delegate()
        finally:
            os.umask(previous)
        record = self.journal / f"{result['delegation_id']}.json"
        lock = self.journal / f"{result['delegation_id']}.lock"
        self.assertEqual(stat.S_IMODE(self.journal.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(record.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o600)
        blob = record.read_text()
        stored = json.loads(blob)
        self.assertEqual(stored["state"], "accepted")
        self.assertNotIn("task", stored)
        self.assertNotIn(TASK, blob)
        assert_absent(blob, CONTROL_NSEC)
        assert_absent(blob, "test-caller-token")
        assert_absent(json.dumps(result), CONTROL_NSEC)
        self.assertTrue(all(call[0] == "GET" for call in self.http.calls))
        self.assertTrue(all(call[1].endswith("/v1/workers/operator") for call in self.http.calls))

    def test_pending_crash_is_not_retried(self):
        task_hash = hashlib.sha256(TASK.encode()).hexdigest()
        self.journal.mkdir(mode=0o700)
        record = fresh_record(
            delegation_id=SUPPLIED_ID,
            worker="operator",
            worker_public_key_hex=WORKER_HEX,
            task_sha256=task_hash,
            state="pending",
        )
        write_record(self.journal, record)
        with self.assertRaises(ControlError) as caught:
            self.delegate({"worker": "operator", "task": TASK, "delegation_id": SUPPLIED_ID})
        self.assertEqual(caught.exception.code, "delegation_ambiguous")
        self.assertEqual(caught.exception.delegation_id, SUPPLIED_ID)
        self.assertEqual(self.buzz.calls, [])
        self.assertEqual(json.loads((self.journal / f"{SUPPLIED_ID}.json").read_text())["state"], "ambiguous")

    def test_request_validation_and_secret_task_rejection(self):
        with self.assertRaises(ControlError) as caught:
            self.delegate({"worker": "operator", "task": TASK, "channel": DM_ID})
        self.assertEqual(caught.exception.code, "invalid_request")
        self.assertIsNone(caught.exception.delegation_id)
        self.assertNotIn("delegation_id", caught.exception.public_body())
        for extra in ("mention", "pubkey", "channel", "relay", "platform", "profile"):
            with self.assertRaises(ControlError) as caught:
                self.delegate({"worker": "operator", "task": TASK, extra: OTHER_HEX})
            self.assertEqual(caught.exception.code, "invalid_request")
            self.assertEqual(self.buzz.calls, [])
        with self.assertRaises(ControlError) as caught:
            self.delegate({"worker": "operator", "task": "   "})
        self.assertEqual(caught.exception.code, "invalid_task")
        self.assertIsNone(caught.exception.delegation_id)
        with self.assertRaises(ControlError) as caught:
            self.delegate({"worker": "operator", "task": "   ", "delegation_id": SUPPLIED_ID})
        self.assertEqual(caught.exception.code, "invalid_task")
        self.assertEqual(caught.exception.delegation_id, SUPPLIED_ID)
        self.assertEqual(self.http.calls, [])
        with self.assertRaises(ControlError) as caught:
            self.delegate({"worker": "Bad Name", "task": TASK})
        self.assertEqual(caught.exception.code, "invalid_name")
        with self.assertRaises(ControlError) as caught:
            self.delegate({"worker": "operator", "task": TASK, "delegation_id": "dlg_ZZ"})
        self.assertEqual(caught.exception.code, "invalid_delegation_id")
        self.assertIsNone(caught.exception.delegation_id)
        self.assertNotIn("delegation_id", caught.exception.public_body())
        with self.assertRaises(ControlError) as caught:
            self.delegate({"worker": "operator", "task": "token BUZZ_PRIVATE_KEY=value"})
        self.assertEqual(caught.exception.code, "task_rejected")
        self.assertEqual(self.http.calls, [])
        with self.assertRaises(ControlError) as caught:
            self.delegate({"worker": "operator", "task": "see nsec1qqqqqqqq please"})
        self.assertEqual(caught.exception.code, "task_rejected")
        assert_absent(str(caught.exception), "nsec1qqqqqqqq")

    def test_membership_token_and_worker_key_are_not_used(self):
        env = dict(self.env)
        env["BUZZ_FLEET_MEMBERSHIP_TOKEN"] = "membership-test-token"
        with self.assertRaises(ControlError) as caught:
            self.delegate(environ=env)
        self.assertEqual(caught.exception.code, "forbidden_environment")
        self.assertEqual(self.http.calls, [])
        assert_absent(str(caught.exception), "membership-test-token")

        poisoned = profile_bytes() + b"BUZZ_FLEET_MEMBERSHIP_TOKEN=membership-test-token\n"
        with self.assertRaises(ControlError) as caught:
            self.delegate(profile_env_bytes=poisoned)
        self.assertEqual(caught.exception.code, "forbidden_environment")
        self.assertEqual(self.buzz.calls, [])
        self.assertNotIn("membership-test-token", self.http.calls[0][1])
        self.assertNotIn("membership-test-token", self.http.calls[0][2]["Authorization"])

    def test_cli_prints_a_fixed_error(self):
        real = sys.stdout
        sys.stdout = collected = StringIO()
        try:
            code = delegate_main([], stdin=BytesIO(b'{"channel":"nope"}'))
        finally:
            sys.stdout = real
        self.assertEqual(code, 1)
        body = json.loads(collected.getvalue())
        self.assertEqual(body["error"]["code"], "invalid_request")
        self.assertNotIn("delegation_id", body)

    def test_delegate_script_boots(self):
        env = {"PATH": os.environ.get("PATH", "/usr/bin"), "HOME": self.tmp.name}
        proc = subprocess.run(
            [sys.executable, str(REPO / "fleet-delegate")],
            input=b'{"worker":"operator","task":"hello"}',
            env=env,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["error"]["code"], "control_profile_unusable")
        self.assertEqual(proc.stderr, b"")

    def _assert_buzz_contract(self, delegation_id: str):
        opened, sent = self.buzz.calls
        self.assertEqual(opened["argv"], ["/usr/local/bin/buzz", "dms", "open", "--pubkey", WORKER_HEX])
        self.assertEqual(opened["stdin"], b"")
        self.assertEqual(
            sent["argv"],
            [
                "/usr/local/bin/buzz",
                "messages",
                "send",
                "--channel",
                DM_ID,
                "--mention",
                WORKER_HEX,
                "--content",
                "-",
            ],
        )
        self.assertEqual(sent["argv"].count("--mention"), 1)
        self.assertTrue(sent["stdin"].decode().startswith(f"[fleet-delegation {delegation_id}]\n"))
        self.assertNotIn(TASK, sent["argv"])
        self.assertNotIn("SECRET_PARENT", opened["env"])
        self.assertNotIn("FLEET_PROVISIONER_CALLER_TOKEN", opened["env"])
        self.assertEqual(opened["env"]["PATH"], "/usr/local/bin:/usr/bin:/bin")
        self.assertEqual(opened["env"]["BUZZ_RELAY_URL"], "https://buzz.example")
        if opened["env"].get("BUZZ_PRIVATE_KEY") != CONTROL_NSEC:
            raise AssertionError("buzz child did not receive the control signing key")
        joined = " ".join(opened["argv"] + sent["argv"])
        assert_absent(joined, CONTROL_NSEC)
        self.assertEqual(self.http.calls[0][0], "GET")

    def _assert_journal_private(self, delegation_id: str):
        blob = (self.journal / f"{delegation_id}.json").read_text()
        assert_absent(blob, CONTROL_NSEC)
        assert_absent(blob, WORKER_SECRET.hex())
        self.assertNotIn(TASK, blob)

    def _only_record(self) -> Path:
        records = list(self.journal.glob("dlg_*.json"))
        self.assertEqual(len(records), 1)
        return records[0]

    def _retry_send(self, stdout: bytes, code: str, state: str) -> str:
        ident = "dlg_" + hashlib.sha256(stdout).hexdigest()[:32]
        buzz = Buzz(send=(0, stdout))
        with self.assertRaises(ControlError) as caught:
            self.delegate(
                {"worker": "operator", "task": f"body-{state}", "delegation_id": ident},
                buzz_runner=buzz,
            )
        self.assertEqual(caught.exception.code, code)
        stored = json.loads((self.journal / f"{ident}.json").read_text())
        self.assertEqual(stored["state"], state)
        self.assertEqual(caught.exception.delegation_id, ident)
        return stored["state"]

    def test_presubmit_exits_retry_and_postsubmit_stays_ambiguous(self):
        """Bind send classification to delegate_worker, not a test-only helper."""
        self._assert_presubmit_retry(1, "pre-submit exit 1")
        self._assert_presubmit_retry(4, "pre-submit exit 4")
        self._assert_presubmit_retry(4, "ask @hermes before continuing")

        generated = self._assert_ambiguous_send(BuzzTimeout(), task="timeout stays uncertain")
        self._assert_no_resend(generated, "timeout stays uncertain")

        delivery_unknown = self._assert_ambiguous_send((2, b""), task="delivery unknown")
        self._assert_no_resend(delivery_unknown, "delivery unknown")

        lost = self._assert_ambiguous_send((0, b"not-json"), task="lost acceptance")
        self._assert_no_resend(lost, "lost acceptance")
        missing_event = self._assert_ambiguous_send(
            (0, b'{"accepted": true}'),
            task="acceptance without event id",
        )
        self._assert_no_resend(missing_event, "acceptance without event id")

        auth_after_request = self._assert_ambiguous_send((3, b""), task="auth exit is not pre-submit")
        self._assert_no_resend(auth_after_request, "auth exit is not pre-submit")
        receipt = json.dumps({"accepted": True, "event_id": EVENT_ID}).encode()
        carried = self._assert_ambiguous_send((1, receipt), task="exit 1 still carrying a receipt")
        self._assert_no_resend(carried, "exit 1 still carrying a receipt")

    def test_send_child_is_not_pending_before_start(self):
        ident = "dlg_" + "a1" * 16
        payload = {"worker": "operator", "task": TASK, "delegation_id": ident}

        def runner(argv, env, stdin, on_started=None):
            if argv[1:3] == ["dms", "open"]:
                return 0, dm_stdout(True), b""
            stored = json.loads((self.journal / f"{ident}.json").read_text())
            self.assertEqual(stored["state"], "bound")
            self.assertIsNotNone(on_started)
            raise RuntimeError("exec failed before the child existed")

        with self.assertRaises(ControlError) as caught:
            self.delegate(payload, buzz_runner=runner)
        self.assertEqual(caught.exception.code, "helper_failed")
        self.assertEqual(caught.exception.delegation_id, ident)
        self.assertEqual(json.loads((self.journal / f"{ident}.json").read_text())["state"], "failed")

        retried = self.delegate(payload, buzz_runner=Buzz())
        self.assertTrue(retried["accepted"])
        self.assertEqual(retried["delegation_id"], ident)

    def _assert_presubmit_retry(self, exit_code: int, task: str) -> None:
        ident = "dlg_" + hashlib.sha256(f"{exit_code}:{task}".encode()).hexdigest()[:32]
        payload = {"worker": "operator", "task": task, "delegation_id": ident}
        observed: list[str] = []

        def runner(argv, env, stdin, on_started=None):
            if argv[1:3] != ["messages", "send"]:
                return 0, dm_stdout(True), b""
            stored = json.loads((self.journal / f"{ident}.json").read_text())
            self.assertEqual(stored["state"], "bound")
            self.assertIsNotNone(on_started)
            on_started()
            observed.append(json.loads((self.journal / f"{ident}.json").read_text())["state"])
            return exit_code, b"", b""

        with self.assertRaises(ControlError) as caught:
            self.delegate(payload, buzz_runner=runner)
        self.assertEqual(caught.exception.code, "send_rejected")
        self.assertEqual(caught.exception.delegation_id, ident)
        self.assertEqual(caught.exception.public_body()["delegation_id"], ident)
        self.assertEqual(observed, ["pending"])
        self.assertEqual(json.loads((self.journal / f"{ident}.json").read_text())["state"], "failed")

        retry = Buzz()
        result = self.delegate(payload, buzz_runner=retry)
        self.assertEqual(result["delegation_id"], ident)
        self.assertEqual(result["event_id"], EVENT_ID)
        self.assertEqual(sum(1 for call in retry.calls if call["argv"][1:3] == ["messages", "send"]), 1)

    def _assert_ambiguous_send(self, send, task: str) -> str:
        buzz = Buzz(send=send)
        with self.assertRaises(ControlError) as caught:
            self.delegate({"worker": "operator", "task": task}, buzz_runner=buzz)
        self.assertEqual(caught.exception.code, "send_ambiguous")
        delegation_id = caught.exception.delegation_id
        self.assertTrue(DELEGATION_ID_RE.fullmatch(delegation_id or ""))
        body = caught.exception.public_body()
        self.assertEqual(body["delegation_id"], delegation_id)
        self.assertEqual(body["error"]["code"], "send_ambiguous")
        self.assertEqual(json.loads((self.journal / f"{delegation_id}.json").read_text())["state"], "ambiguous")
        self.assertEqual(sum(1 for call in buzz.calls if call["argv"][1:3] == ["messages", "send"]), 1)
        return delegation_id

    def _assert_no_resend(self, delegation_id: str, task: str) -> None:
        buzz = Buzz()
        with self.assertRaises(ControlError) as caught:
            self.delegate(
                {"worker": "operator", "task": task, "delegation_id": delegation_id},
                buzz_runner=buzz,
            )
        self.assertEqual(caught.exception.code, "delegation_ambiguous")
        self.assertEqual(caught.exception.delegation_id, delegation_id)
        self.assertEqual(buzz.calls, [])


class McpSourceTests(unittest.TestCase):
    def test_server_exposes_only_the_three_tools(self):
        text = (REPO / "fleet-mcp" / "index.js").read_text()
        self.assertEqual(text.count('server.registerTool('), 3)
        for name in ("worker_status", "ensure_worker", "delegate_worker"):
            self.assertIn(name, text)
        self.assertNotIn('registerTool(\n  "send_message"', text)
        self.assertNotIn("delegate_task", text)
        description = text.split('server.registerTool(\n  "delegate_worker",', 1)[1].split("inputSchema:", 1)[0]
        self.assertIn("MUST reuse that exact delegation_id", description)
        self.assertIn(
            "must not create a new delegation merely because delivery outcome was uncertain",
            description,
        )
        self.assertIn("does not send the message again", description)
        self.assertNotIn("new delegation_id", description)
        self.assertNotIn("BUZZ_PRIVATE_KEY=", text)
        self.assertNotIn("shell: true", text)
        self.assertIn("shell: false", text)
        schema = text.split('server.registerTool(\n  "delegate_worker",', 1)[1].split(
            "async ({ worker, task, delegation_id }) => {", 1
        )[0]
        self.assertNotIn("mention", schema)
        self.assertNotIn("pubkey", schema)
        self.assertNotIn("channel", schema)
        handler = text.split("async ({ worker, task, delegation_id }) => {", 1)[1].split(
            "return textResult", 1
        )[0]
        self.assertIn("const payload = { worker, task };", handler)
        self.assertIn("payload.delegation_id = delegation_id;", handler)
        self.assertNotIn("mention", handler)
        self.assertNotIn("--mention", text)
        proc = subprocess.run(
            ["node", "--check", str(REPO / "fleet-mcp" / "index.js")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
