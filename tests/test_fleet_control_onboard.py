#!/usr/bin/env python3
"""Control onboard_worker. Fake HTTP only. No provisioner and no network."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fleet_control.errors import ControlError
from fleet_control.onboard import main as onboard_main
from fleet_control.onboard import onboard_worker


FLEET_FILE = (
    b"FLEET_PROVISIONER_URL=https://fleet.example\n"
    b"FLEET_PROVISIONER_CALLER_TOKEN=test-caller-token\n"
)
ENV = {"LANG": "C"}
TOKEN = "test-caller-token"
SERVER_SENTINEL = "UNIQUE_SERVER_MESSAGE"


def onboarding(**overrides) -> dict:
    body = {
        "id": "onb_" + "cd" * 16,
        "status": "running",
        "stage": "ensuring",
        "identity": "absent",
        "expected_public_key_hex": None,
        "expected_npub": None,
        "vmid": None,
        "git_sha": None,
        "retired_reason": None,
        "error": None,
        "updated_at": "2026-10-14T00:00:00Z",
    }
    body.update(overrides)
    return body


def worker_document(**overrides) -> dict:
    body = {
        "api_version": "v1",
        "kind": "Worker",
        "name": "operator",
        "declared": True,
        "requested": {"state": "ready"},
        "observed": {"state": "absent"},
        "reconciliation": {"status": "accepted"},
        "tombstone": None,
        "onboarding": onboarding(),
    }
    body.update(overrides)
    return body


def refusal(code: str, *, message: str = SERVER_SENTINEL, progress: dict | None = None) -> dict:
    body = {
        "api_version": "v1",
        "error": {
            "code": code,
            "message": message,
            "retryable": False,
            "worker": "operator",
        },
    }
    if progress is not None:
        body["onboarding"] = progress
    return body


class Scripted:
    def __init__(self, responses: list):
        self.responses = list(responses)
        self.calls: list[tuple] = []

    def __call__(self, method, url, headers, payload):
        self.calls.append((method, url, dict(headers), payload))
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        status, body = item
        if isinstance(body, BaseException):
            raise body
        raw = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        return status, raw


class OnboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = Path(self.tmp.name) / "onboarding"

    def tearDown(self):
        self.tmp.cleanup()

    def onboard(self, transport, name: str = "operator", **kwargs):
        defaults = {
            "environ": ENV,
            "file_bytes": FLEET_FILE,
            "transport": transport,
            "journal_dir": self.journal,
        }
        defaults.update(kwargs)
        return onboard_worker(name, **defaults)

    def record(self, name: str = "operator") -> dict:
        return json.loads((self.journal / f"{name}.json").read_text())

    def test_one_post_then_get_only_including_after_restart(self):
        document = worker_document()
        later = worker_document(onboarding=onboarding(status="complete", stage="complete"))
        transport = Scripted([(202, document), (200, later), (200, later)])
        first = self.onboard(transport)
        self.assertEqual(first["onboarding"]["status"], "running")
        self.assertEqual(self.record()["state"], "accepted")
        self.assertIsNone(self.record()["refusal_code"])
        second = self.onboard(transport)
        third = self.onboard(transport)
        self.assertEqual(second["onboarding"]["status"], "complete")
        self.assertEqual(third["onboarding"]["status"], "complete")
        methods = [call[0] for call in transport.calls]
        self.assertEqual(methods, ["POST", "GET", "GET"])
        self.assertEqual(transport.calls[0][1], "https://fleet.example/v1/workers/operator/onboard")
        self.assertEqual(transport.calls[0][3], b"{}")
        self.assertEqual(transport.calls[1][1], "https://fleet.example/v1/workers/operator")
        self.assertIsNone(transport.calls[1][3])
        self.assertEqual(transport.calls[0][2]["Authorization"], "Bearer test-caller-token")
        self.assertNotIn(TOKEN, transport.calls[0][1])
        self.assertNotIn("/ensure", transport.calls[0][1])
        self.assertNotIn(TOKEN, self.journal.joinpath("operator.json").read_text())
        self.assertEqual(stat.S_IMODE((self.journal / "operator.json").stat().st_mode), 0o600)

    def test_reservation_is_durable_before_the_post(self):
        seen = {}

        def transport(method, url, headers, payload):
            seen["method"] = method
            seen["body"] = payload
            seen["journal"] = (self.journal / "operator.json").read_text()
            return 202, json.dumps(worker_document()).encode("utf-8")

        self.onboard(transport)
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["body"], b"{}")
        self.assertIn('"state":"reserved"', seen["journal"])
        self.assertEqual(self.record()["state"], "accepted")

    def test_interrupted_reservation_is_not_posted_again(self):
        def crash(method, url, headers, payload):
            self.assertEqual(method, "POST")
            self.assertIn('"state":"reserved"', (self.journal / "operator.json").read_text())
            raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            self.onboard(crash)
        self.assertEqual(self.record()["state"], "reserved")

        follow = Scripted([(200, worker_document())])
        with self.assertRaises(ControlError) as caught:
            self.onboard(follow)
        self.assertEqual(caught.exception.code, "onboard_ambiguous")
        self.assertEqual([call[0] for call in follow.calls], ["GET"])
        self.assertEqual(self.record()["state"], "reserved")
        self.assertNotIn(SERVER_SENTINEL, json.dumps(caught.exception.public_body()))

    def test_concurrent_call_does_not_post(self):
        entered = threading.Event()
        release = threading.Event()
        calls: list[str] = []
        results: dict = {}

        def transport(method, url, headers, payload):
            calls.append(method)
            entered.set()
            if not release.wait(3):
                raise TimeoutError()
            return 202, json.dumps(worker_document()).encode("utf-8")

        def first():
            try:
                results["body"] = self.onboard(transport)
            except BaseException as exc:
                results["error"] = exc

        worker = threading.Thread(target=first)
        worker.start()
        self.assertTrue(entered.wait(3))
        with self.assertRaises(ControlError) as caught:
            self.onboard(transport)
        self.assertEqual(caught.exception.code, "onboard_in_flight")
        release.set()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(calls, ["POST"])
        self.assertEqual(results["body"]["kind"], "Worker")
        self.assertNotIn("error", results)

    def test_uncertain_outcomes_are_not_retried(self):
        cases = {
            "timeout": TimeoutError(),
            "connection": ConnectionError("reset"),
            "server": (
                503,
                {
                    "api_version": "v1",
                    "error": {
                        "code": "git_unavailable",
                        "message": SERVER_SENTINEL,
                        "retryable": True,
                    },
                },
            ),
            "malformed": (200, b"{"),
            "unsafe": (200, {"nsec": "nsec1qqqqqqqqqqqqqq", "kind": "Worker", "name": "operator"}),
        }
        for name, first in cases.items():
            with self.subTest(name=name):
                self.journal = Path(self.tmp.name) / name
                transport = Scripted([first, (200, worker_document())])
                with self.assertRaises(ControlError) as caught:
                    self.onboard(transport)
                if name in ("malformed", "unsafe"):
                    self.assertEqual(caught.exception.code, "fleet_response_unsafe")
                else:
                    self.assertEqual(caught.exception.code, "onboard_ambiguous")
                self.assertNotIn(SERVER_SENTINEL, caught.exception.message)
                self.assertNotIn("nsec1", caught.exception.message)
                self.assertNotIn(TOKEN, caught.exception.message)
                self.assertEqual(self.record()["state"], "ambiguous")
                journal = (self.journal / "operator.json").read_text()
                self.assertNotIn(TOKEN, journal)
                self.assertNotIn("nsec1", journal)
                self.assertNotIn(SERVER_SENTINEL, journal)
                with self.assertRaises(ControlError) as again:
                    self.onboard(transport)
                self.assertEqual(again.exception.code, "onboard_ambiguous")
                self.assertEqual([call[0] for call in transport.calls], ["POST", "GET"])

    def test_token_in_the_body_is_not_kept(self):
        transport = Scripted(
            [
                (202, {"api_version": "v1", "kind": "Worker", "note": TOKEN}),
                (200, worker_document()),
            ]
        )
        with self.assertRaises(ControlError) as caught:
            self.onboard(transport)
        self.assertEqual(caught.exception.code, "fleet_response_unsafe")
        self.assertNotIn(TOKEN, caught.exception.message)
        self.assertNotIn(TOKEN, json.dumps(caught.exception.public_body()))
        self.assertNotIn(TOKEN, (self.journal / "operator.json").read_text())
        with self.assertRaises(ControlError) as again:
            self.onboard(transport)
        self.assertEqual(again.exception.code, "onboard_ambiguous")
        self.assertEqual([call[0] for call in transport.calls], ["POST", "GET"])

    def test_recognized_refusals_stick_and_keep_their_codes(self):
        codes = ("onboarding_retired", "tombstone_present", "existing_worker")
        for code in codes:
            with self.subTest(code=code):
                self.journal = Path(self.tmp.name) / code
                progress = onboarding(status="retired", stage="retired", retired_reason="deprovision_accepted")
                transport = Scripted(
                    [
                        (409, refusal(code, progress=progress)),
                        (200, worker_document()),
                    ]
                )
                with self.assertRaises(ControlError) as caught:
                    self.onboard(transport)
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn(SERVER_SENTINEL, caught.exception.message)
                self.assertNotIn(SERVER_SENTINEL, json.dumps(caught.exception.public_body()))
                self.assertEqual(self.record()["state"], "refused")
                self.assertEqual(self.record()["refusal_code"], code)
                with self.assertRaises(ControlError) as again:
                    self.onboard(transport)
                self.assertEqual(again.exception.code, code)
                self.assertEqual([call[0] for call in transport.calls], ["POST", "GET"])

    def test_malformed_refusal_is_ambiguous(self):
        body = refusal("onboarding_retired")
        body["onboarding"] = {"status": "retired"}
        transport = Scripted([(409, body), (200, worker_document())])
        with self.assertRaises(ControlError) as caught:
            self.onboard(transport)
        self.assertEqual(caught.exception.code, "onboard_ambiguous")
        self.assertEqual(self.record()["state"], "ambiguous")
        self.assertIsNone(self.record()["refusal_code"])
        with self.assertRaises(ControlError) as again:
            self.onboard(transport)
        self.assertEqual(again.exception.code, "onboard_ambiguous")
        self.assertEqual(transport.calls[1][0], "GET")

    def test_undeclared_name_is_a_definite_rejection(self):
        missing = {
            "api_version": "v1",
            "error": {
                "code": "undeclared_worker",
                "message": SERVER_SENTINEL,
                "retryable": False,
                "worker": "operator",
            },
        }
        transport = Scripted([(404, missing), (404, missing)])
        with self.assertRaises(ControlError) as caught:
            self.onboard(transport)
        self.assertEqual(caught.exception.code, "undeclared_worker")
        self.assertNotIn(SERVER_SENTINEL, caught.exception.message)
        self.assertFalse((self.journal / "operator.json").exists())
        with self.assertRaises(ControlError) as again:
            self.onboard(transport)
        self.assertEqual(again.exception.code, "undeclared_worker")
        self.assertEqual([call[0] for call in transport.calls], ["POST", "POST"])
        self.assertFalse((self.journal / "operator.json").exists())

    def test_unauthorized_does_not_stick(self):
        transport = Scripted([(401, b""), (401, b"")])
        with self.assertRaises(ControlError) as caught:
            self.onboard(transport)
        self.assertEqual(caught.exception.code, "fleet_unauthorized")
        self.assertFalse((self.journal / "operator.json").exists())
        with self.assertRaises(ControlError):
            self.onboard(transport)
        self.assertEqual([call[0] for call in transport.calls], ["POST", "POST"])

    def test_invalid_name_does_not_send(self):
        transport = Scripted([])
        with self.assertRaises(ControlError) as caught:
            self.onboard(transport, name="../etc")
        self.assertEqual(caught.exception.code, "invalid_name")
        self.assertEqual(transport.calls, [])
        self.assertEqual(list(self.journal.glob("*")), [])

    def test_journal_is_separate_from_delegations(self):
        root = Path(self.tmp.name) / "profiles"
        (root / "control").mkdir(parents=True)
        env = {
            "LANG": "C",
            "FLEET_CONTROL_HERMES_PROFILE": "control",
            "FLEET_CONTROL_PROFILES_ROOT": str(root),
            "FLEET_DELEGATION_JOURNAL_DIR": str(root / "delegations"),
        }
        transport = Scripted([(202, worker_document())])
        self.onboard(transport, environ=env, journal_dir=None)
        stored = root / "control" / "fleet-onboarding" / "operator.json"
        self.assertTrue(stored.is_file())
        self.assertFalse((root / "control" / "fleet-delegations").exists())
        self.assertFalse((root / "delegations").exists())
        self.assertNotIn(TOKEN, stored.read_text())

    def test_cli_rejects_extra_args_without_sending(self):
        captured = []

        class _Stdout:
            def write(self, text):
                captured.append(text)

        real = sys.stdout
        sys.stdout = _Stdout()
        try:
            code = onboard_main(["operator", "extra"])
        finally:
            sys.stdout = real
        self.assertEqual(code, 1)
        self.assertEqual(json.loads("".join(captured))["error"]["code"], "invalid_name")
        self.assertNotIn(TOKEN, "".join(captured))

    def test_script_boots_and_refuses_a_missing_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            venv = Path(tmp) / "boot-venv"
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
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin"),
                "HOME": "/tmp",
                "FLEET_CONTROL_PYTHON": str(python),
            }
            proc = subprocess.run(
                [sys.executable, str(REPO / "fleet-onboard"), "operator"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["error"]["code"], "invalid_control_env")
        self.assertEqual(proc.stderr, "")
        self.assertNotIn(TOKEN, proc.stdout)

    def test_docs_keep_declaration_and_ensure_limits(self):
        readme = " ".join((REPO / "README.md").read_text().split())
        skill = " ".join((REPO / "skills" / "fleet-delegation" / "SKILL.md").read_text().split())
        raw_server = (REPO / "fleet-mcp" / "index.js").read_text()
        server = " ".join(raw_server.split())
        for text in (readme, skill, server):
            self.assertIn("deployed reconciliation revision", text)
            self.assertIn("not a substitute", text)
        self.assertIn("cannot create an arbitrary worker name", readme)
        self.assertIn("cannot create a worker name", skill)
        self.assertIn("cannot create a worker name", server)
        self.assertIn("does not submit again", server)
        self.assertIn("Do not retry an uncertain onboarding", server)
        chunk = raw_server.split('server.registerTool(\n  "onboard_worker",', 1)[1]
        schema = chunk.split("inputSchema:", 1)[1].split("async ({ name })", 1)[0]
        self.assertIn("name:", schema)
        for banned in ("task", "delegation_id", "pubkey", "channel", "token", "nsec"):
            self.assertNotIn(banned, schema)
        self.assertIn("await runHelper(onboardBin, [name])", raw_server)


if __name__ == "__main__":
    unittest.main()
