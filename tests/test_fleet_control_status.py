#!/usr/bin/env python3
"""Control fleet-status and fleet-ensure. Fake HTTP only."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fleet_control.config import load_fleet_api_settings
from fleet_control.ensure import ensure_worker
from fleet_control.errors import ControlError
from fleet_control.status import main as status_main
from fleet_control.status import worker_status


FLEET_FILE = (
    b"FLEET_PROVISIONER_URL=https://fleet.example\n"
    b"FLEET_PROVISIONER_CALLER_TOKEN=test-caller-token\n"
)
ENV = {"LANG": "C"}


class RecordingTransport:
    def __init__(self, status: int, body: dict):
        self.status = status
        self.body = body
        self.calls: list[tuple] = []

    def __call__(self, method, url, headers, payload):
        self.calls.append((method, url, dict(headers), payload))
        return self.status, json.dumps(self.body).encode("utf-8")


class FleetStatusTests(unittest.TestCase):
    def test_list_and_one_worker_are_gets(self):
        listed = {"api_version": "v1", "kind": "WorkerList", "workers": []}
        transport = RecordingTransport(200, listed)
        body = worker_status(environ=ENV, file_bytes=FLEET_FILE, transport=transport)
        self.assertEqual(body["kind"], "WorkerList")
        method, url, headers, payload = transport.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://fleet.example/v1/workers")
        self.assertEqual(payload, None)
        self.assertEqual(headers["Authorization"], "Bearer test-caller-token")
        self.assertNotIn("test-caller-token", url)

        one = RecordingTransport(200, {"api_version": "v1", "kind": "Worker", "name": "operator"})
        worker_status("operator", environ=ENV, file_bytes=FLEET_FILE, transport=one)
        self.assertEqual(one.calls[0][0], "GET")
        self.assertEqual(one.calls[0][1], "https://fleet.example/v1/workers/operator")

    def test_unknown_worker_and_invalid_name(self):
        missing = RecordingTransport(404, {"error": {"code": "undeclared_worker", "message": "missing"}})
        with self.assertRaises(ControlError) as caught:
            worker_status("missing", environ=ENV, file_bytes=FLEET_FILE, transport=missing)
        self.assertEqual(caught.exception.code, "undeclared_worker")
        self.assertNotIn("missing", str(caught.exception))

        transport = RecordingTransport(200, {})
        with self.assertRaises(ControlError) as caught:
            worker_status("../etc", environ=ENV, file_bytes=FLEET_FILE, transport=transport)
        self.assertEqual(caught.exception.code, "invalid_name")
        self.assertEqual(transport.calls, [])

    def test_secret_response_is_not_returned(self):
        transport = RecordingTransport(200, {"nsec": "nope"})
        with self.assertRaises(ControlError) as caught:
            worker_status(environ=ENV, file_bytes=FLEET_FILE, transport=transport)
        self.assertEqual(caught.exception.code, "fleet_response_unsafe")
        self.assertNotIn("nsec", caught.exception.message)

    def test_cli_rejects_extra_args_without_network(self):
        code_out = []

        class _Stdout:
            def write(self, text):
                code_out.append(text)

        real = sys.stdout
        sys.stdout = _Stdout()
        try:
            code = status_main(["one", "two"])
        finally:
            sys.stdout = real
        self.assertEqual(code, 1)
        self.assertEqual(json.loads("".join(code_out))["error"]["code"], "invalid_name")

    def test_script_boots_and_refuses_a_missing_env_file(self):
        env = {"PATH": os.environ.get("PATH", "/usr/bin"), "HOME": "/tmp"}
        proc = subprocess.run(
            [sys.executable, str(REPO / "fleet-status")],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["error"]["code"], "invalid_control_env")
        self.assertEqual(proc.stderr, "")


class FleetEnsureTests(unittest.TestCase):
    def test_ensure_puts_empty_object(self):
        transport = RecordingTransport(200, {"api_version": "v1", "kind": "Worker", "name": "operator"})
        body = ensure_worker("operator", environ=ENV, file_bytes=FLEET_FILE, transport=transport)
        self.assertEqual(body["name"], "operator")
        method, url, _headers, payload = transport.calls[0]
        self.assertEqual((method, url, payload), ("PUT", "https://fleet.example/v1/workers/operator/ensure", b"{}"))

    def test_script_boots(self):
        env = {"PATH": os.environ.get("PATH", "/usr/bin"), "HOME": "/tmp"}
        proc = subprocess.run(
            [sys.executable, str(REPO / "fleet-ensure"), "operator"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["error"]["code"], "invalid_control_env")


class FleetEnvTests(unittest.TestCase):
    def test_https_origin_and_forbidden_material(self):
        settings, token = load_fleet_api_settings(environ=ENV, file_bytes=FLEET_FILE)
        self.assertEqual(settings.url, "https://fleet.example")
        self.assertEqual(token, "test-caller-token")
        self.assertNotIn("token", repr(settings))

        with self.assertRaises(ControlError) as caught:
            load_fleet_api_settings(
                environ=ENV,
                file_bytes=b"FLEET_PROVISIONER_URL=http://fleet.example\n"
                b"FLEET_PROVISIONER_CALLER_TOKEN=test-caller-token\n",
            )
        self.assertEqual(caught.exception.code, "invalid_fleet_url")

        with self.assertRaises(ControlError) as caught:
            load_fleet_api_settings(
                environ=ENV,
                file_bytes=FLEET_FILE + b"BUZZ_FLEET_MEMBERSHIP_TOKEN=not-used\n",
            )
        self.assertEqual(caught.exception.code, "forbidden_environment")
        self.assertNotIn("not-used", str(caught.exception))

        with self.assertRaises(ControlError) as caught:
            load_fleet_api_settings(
                environ={"BUZZ_FLEET_MEMBERSHIP_TOKEN": "present", "LANG": "C"},
                file_bytes=FLEET_FILE,
            )
        self.assertEqual(caught.exception.code, "forbidden_environment")

    def test_env_file_mode_is_not_required_to_log_the_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fleet.env"
            path.write_bytes(FLEET_FILE)
            os.chmod(path, 0o600)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            settings, _token = load_fleet_api_settings(
                environ={"FLEET_CONTROL_ENV_FILE": str(path), "LANG": "C"},
            )
            self.assertEqual(settings.url, "https://fleet.example")


if __name__ == "__main__":
    unittest.main()
