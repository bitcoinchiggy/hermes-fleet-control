"""Focused checks for the c08cb1e deploy helpers. No host contact."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fleet_control.journal import JOURNAL_DIR_KEY, resolve_journal_dir
from fleet_control.onboard import ONBOARD_JOURNAL_DIR
from fleet_control.onboard import _resolve_dir as onboard_resolve
from fleet_control.retire import RETIRE_JOURNAL_DIR
from fleet_control.retire import _resolve_dir as retire_resolve
from fleet_control.support.profile_env import HERMES_PROFILES_DIR

_SPEC = importlib.util.spec_from_file_location(
    "c08cb1e_material",
    ROOT / "docs" / "deploy" / "c08cb1e_material.py",
)
assert _SPEC is not None and _SPEC.loader is not None
material = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(material)


class DeployMaterialTests(unittest.TestCase):
    def test_manual_restart_does_not_need_nrestarts_increment(self):
        blockers = material.restart_blockers(
            40,
            {"ActiveState": "active", "SubState": "running", "MainPID": "41", "NRestarts": "0"},
            {"HERMES_FLEET_CONTROL_ROOT": "/opt/hermes-fleet-control/new"},
            "/opt/hermes-fleet-control/new",
            ["fleet-delegation.conf", "fleet-retirement.conf"],
            expect_retirement=True,
        )
        self.assertEqual(blockers, [])
        self.assertIn("does not increment", material.NRESTARTS_MEASURES)

    def test_same_pid_is_not_healthy_even_if_nrestarts_increases(self):
        blockers = material.restart_blockers(
            40,
            {"ActiveState": "active", "SubState": "running", "MainPID": "40", "NRestarts": "1"},
            {"HERMES_FLEET_CONTROL_ROOT": "/opt/hermes-fleet-control/new"},
            "/opt/hermes-fleet-control/new",
            ["fleet-delegation.conf", "fleet-retirement.conf"],
            expect_retirement=True,
        )
        self.assertIn("mainpid", blockers)

    def test_mcp_args_redact_secret_shapes_and_flag_values(self):
        self.assertEqual(material.classify_mcp_text("sk-test-value"), "redacted")
        self.assertEqual(material.classify_mcp_text("nsec1qqqqqqqqqqqqqq"), "redacted")
        self.assertEqual(material.classify_mcp_text("Bearer test-token"), "redacted")
        token = material.classify_mcp_args(["--token", "sk-test-value"])
        self.assertEqual(token, "redacted,redacted")
        self.assertNotIn("sk-test-value", token)
        password = material.classify_mcp_args(["--password", "hunter2"])
        self.assertEqual(password, "redacted,redacted")
        self.assertNotIn("hunter2", password)
        pasted = material.classify_mcp_args(["-pHunter2secret"])
        self.assertEqual(pasted, "redacted")
        self.assertNotIn("Hunter2secret", pasted)
        access = material.classify_mcp_args(["--access-token", "-abcSECRET"])
        self.assertEqual(access, "redacted,redacted")
        self.assertNotIn("abcSECRET", access)
        self.assertEqual(material.classify_mcp_args(["--token", "node"]), "redacted,redacted")
        self.assertEqual(material.classify_mcp_args(["--password", "python3"]), "redacted,redacted")
        self.assertNotIn("python3", material.classify_mcp_args(["--password", "python3"]))
        self.assertEqual(material.classify_mcp_args(["--version", "node"]), "flag:--version,public:node")
        self.assertNotIn("sk-test-value", material.classify_mcp_args(["--api-key=sk-test-value"]))
        self.assertEqual(material.classify_mcp_text("node"), "public:node")
        self.assertEqual(material.classify_mcp_text("index.js"), "redacted")

    def test_credential_origin_is_not_copied(self):
        secret = "https://user:sk-test-value@example.test/org/repo.git"
        copied: list[str] = []
        with self.assertRaises(material.Stop):
            material.bind_origin(secret, copied.append)
        self.assertEqual(copied, [])
        lines = "\n".join(material.report_origin_decision(secret))
        self.assertIn("origin-embedded-token=present", lines)
        self.assertIn("origin-copied=no", lines)
        self.assertNotIn("sk-test-value", lines)
        self.assertNotIn("user:", lines)
        query = "https://example.test/r.git?access_token=query-secret"
        self.assertEqual(material.origin_credential(query), "unknown")
        query_lines = "\n".join(material.report_origin_decision(query))
        self.assertIn("origin-copied=no", query_lines)
        self.assertNotIn("query-secret", query_lines)
        ssh = "ssh://git@example.test/org/repo.git"
        self.assertEqual(material.origin_credential(ssh), "absent")
        self.assertEqual(material.origin_form(ssh)[0], "ssh://example.test")
        semi = "https://example.test/r.git;tok=semicolon-secret"
        self.assertEqual(material.origin_credential(semi), "unknown")
        semi_lines = "\n".join(material.report_origin_decision(semi))
        self.assertIn("origin-copied=no", semi_lines)
        self.assertNotIn("semicolon-secret", semi_lines)
        refused: list[str] = []
        with self.assertRaises(material.Stop):
            material.bind_origin(semi, refused.append)
        self.assertEqual(refused, [])

    def test_onboarding_json_is_state_not_a_filename_search(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            (state / "onboarding").mkdir(mode=0o700)
            (state / "tombstones").mkdir(mode=0o700)
            (state / "onboarding" / "alpha.json").write_text('{"secret":"sk-test-value"}', encoding="utf-8")
            (state / "tombstones" / "beta.json").write_text('{"body":"not-printed"}', encoding="utf-8")
            (state / "notes-journal.txt").write_text("tombstone journal decoy", encoding="utf-8")
            os.chmod(state / "onboarding", 0o700)
            inventory = material.inventory_state(state)
            report = "\n".join(material.state_report_lines(inventory))
            self.assertIn("onboarding-count=1", report)
            self.assertIn("tombstone-count=1", report)
            self.assertNotIn("sk-test-value", report)
            self.assertNotIn("not-printed", report)
            self.assertNotIn("notes-journal", report)
            manifest = material.manifest_line(state / "onboarding" / "alpha.json")
            self.assertNotIn("sk-test-value", manifest)

    def test_state_loader_calls_deployed_resolver(self):
        import types

        name = "fleet_" + "provisioner.worker_identity"
        parent = "fleet_" + "provisioner"
        module = types.ModuleType(name)
        seen = {}

        def resolve_state_dir(env):
            seen["env"] = env
            return "/var/lib/example-state"

        module.resolve_state_dir = resolve_state_dir
        sys.modules[parent] = types.ModuleType(parent)
        sys.modules[name] = module
        try:
            found = material.deployed_state_dir({"FLEET_PROVISIONER_STATE_DIR": "/var/lib/example-state"}, "/opt/checkout")
        finally:
            sys.modules.pop(name, None)
            sys.modules.pop(parent, None)
        self.assertEqual(found, "/var/lib/example-state")
        self.assertEqual(seen["env"]["FLEET_PROVISIONER_STATE_DIR"], "/var/lib/example-state")

    def test_journal_dirs_match_control_loaders(self):
        import tempfile

        self.assertEqual(material.DELEGATION_JOURNAL_KEY, JOURNAL_DIR_KEY)
        self.assertEqual(material.ONBOARD_JOURNAL_KEY, ONBOARD_JOURNAL_DIR)
        self.assertEqual(material.RETIRE_JOURNAL_KEY, RETIRE_JOURNAL_DIR)
        self.assertEqual(material.PROFILES_ROOT_DEFAULT, HERMES_PROFILES_DIR)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            env = {
                JOURNAL_DIR_KEY: str(root / "fleet-delegations"),
                ONBOARD_JOURNAL_DIR: str(root / "fleet-onboarding"),
                RETIRE_JOURNAL_DIR: str(root / "fleet-retirements"),
            }
            delegation = material.control_journal_dir(env, "delegations")
            self.assertFalse(delegation.exists())
            self.assertEqual(delegation, resolve_journal_dir(env))
            self.assertEqual(material.control_journal_dir(env, "onboarding"), onboard_resolve(env, None))
            self.assertEqual(material.control_journal_dir(env, "retirements"), retire_resolve(env, None))

    def _ready_facts(self) -> dict[str, str]:
        return {
            "hostname": "control",
            "unit-scope": "system",
            "system-active": "active",
            "system-process": "live",
            "system-FLEET_CONTROL_PYTHON": "absent",
            "system-HERMES_FLEET_CONTROL_INTEGRATION": "1",
            "system-mcp-command": "absolute-checkout:/opt/hermes-fleet-control/dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a/fleet-mcp",
            "system-mcp-cwd": "interpolated",
            "system-mcp-args": "absent",
            "system-skill-load": "home-skills",
            "stable-dir-count": "1",
            "stable-head-is-dcb3f950": "yes",
            "stable-tree-is-pinned": "yes",
            "origin-embedded-token": "absent",
            "guest-node-signals": "absent",
            "provisioner-on-host": "no",
            "pyyaml": "present",
            "node": "ok",
            "npm": "present",
            "git": "present",
            "python312": "outside-venv",
            "system-running-root-is-stable": "yes",
            "system-delegation-loaded": "yes",
            "system-dropin-order": "ok",
            "system-retirement-absent": "yes",
            "system-fleet-env-file": "regular",
            "system-journals": "private-nonempty",
            "system-need-daemon-reload": "no",
            "system-effective-unit": "ok",
            "system-delegation-location": "system-config",
            "system-euid-root": "yes",
        }

    def test_ready_exit_is_not_a_pass_for_unknowns(self):
        facts = self._ready_facts()
        facts["origin-embedded-token"] = "unknown"
        blockers = material.host_ready_blockers(facts)
        self.assertIn("origin-embedded-token", blockers)
        self.assertEqual(material.preflight_exit(blockers), 4)
        facts["origin-embedded-token"] = "absent"
        self.assertEqual(material.host_ready_blockers(facts), [])
        self.assertEqual(material.preflight_exit([]), 0)

    def test_redacted_mcp_args_are_not_configuration_validation(self):
        hidden = material.classify_mcp_args(
            ["node", "--token", "sk-test-value", "--password", "nsec1qqqqqqqqqqqqqq", "Bearer test-token"]
        )
        self.assertNotIn("sk-test-value", hidden)
        self.assertNotIn("nsec1qqqqqqqqqqqqqq", hidden)
        self.assertNotIn("Bearer", hidden)
        self.assertIn("redacted", hidden.split(","))
        self.assertFalse(material.mcp_args_configuration_ok(hidden))
        facts = self._ready_facts()
        facts["system-mcp-args"] = hidden
        blockers = material.host_ready_blockers(facts)
        self.assertEqual(blockers, ["system-mcp-args"])
        self.assertEqual(material.preflight_exit(blockers), 4)
        validated = material.classify_mcp_args(
            [
                "node",
                "--version",
                "${HERMES_FLEET_CONTROL_ROOT}/fleet-mcp/index.js",
                "/opt/hermes-fleet-control/dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a/fleet-mcp/index.js",
            ]
        )
        self.assertTrue(material.mcp_args_configuration_ok(validated))
        facts["system-mcp-args"] = validated
        self.assertEqual(material.host_ready_blockers(facts), [])
        self.assertFalse(material.mcp_args_configuration_ok("public:sk-test-value"))
        self.assertFalse(material.mcp_args_configuration_ok("flag:--token"))

    def test_runbook_commands_match_executable_entry_points(self):
        plan = (ROOT / "docs" / "deploy" / "c08cb1e-deploy-plan.md").read_text(encoding="utf-8")
        blocks: list[str] = []
        capture = False
        chunk: list[str] = []
        for line in plan.splitlines():
            if line.startswith("```"):
                if capture:
                    blocks.append("\n".join(chunk))
                    chunk = []
                capture = not capture
                continue
            if capture:
                chunk.append(line)
        commands = [line.strip() for block in blocks for line in block.splitlines() if line.strip()]
        self.assertGreaterEqual(len(commands), 9)
        for command in commands:
            path_text, _, verb = command.partition(" ")
            path = ROOT / path_text
            self.assertTrue(path.is_file(), command)
            self.assertTrue(os.access(path, os.X_OK), command)
            if path.name == "c08cb1e_material.py":
                self.assertIn(verb, material.COMMANDS)
                self.assertTrue(path.read_text(encoding="utf-8").startswith("#!/usr/bin/python3.12\n"))
            else:
                self.assertEqual(verb, "")
                self.assertIn(path.name, {
                    "c08cb1e-preflight.sh",
                    "c08cb1e-provisioner-witness.sh",
                    "c08cb1e-guest-node-witness.sh",
                })
                if path.name != "c08cb1e-guest-node-witness.sh":
                    wrapper = path.read_text(encoding="utf-8")
                    self.assertIn("py=/usr/bin/python3.12", wrapper)
                    self.assertNotIn("\npy=python3\n", wrapper)
        self.assertEqual(material.main(["c08cb1e_material.py"]), 2)
        self.assertEqual(material.main(["c08cb1e_material.py", "not-a-command"]), 2)
        if os.access("/usr/bin/python3.12", os.X_OK):
            usage = subprocess.run(
                [str(ROOT / "docs" / "deploy" / "c08cb1e_material.py")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(usage.returncode, 2)
            for name in material.COMMANDS:
                self.assertIn(name, usage.stderr)
        else:
            for name in material.COMMANDS:
                self.assertIn(name, material.COMMANDS)
        for wrapper in ("c08cb1e-preflight.sh", "c08cb1e-provisioner-witness.sh"):
            refused = subprocess.run(
                ["bash", str(ROOT / "docs" / "deploy" / wrapper), "extra"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(refused.returncode, 2, wrapper)
            self.assertIn("STOP:", refused.stderr)

    def test_guest_node_witness_names_its_host_writes(self):
        witness = ROOT / "docs" / "deploy" / "c08cb1e-guest-node-witness.sh"
        stub = Path(tempfile.mkdtemp())
        (stub / "qm").write_text(
            "#!/bin/sh\necho 'VMID NAME STATUS'\necho '101 alpha running'\necho '102 beta stopped'\n",
            encoding="utf-8",
        )
        (stub / "systemctl").write_text("#!/bin/sh\necho not-found\nexit 0\n", encoding="utf-8")
        os.chmod(stub / "qm", 0o755)
        os.chmod(stub / "systemctl", 0o755)
        path = str(stub) + ":" + os.environ["PATH"]
        inner = textwrap.dedent(
            f"""\
            set -euo pipefail
            saved=$(mktemp -d)
            out=$(mktemp -d)
            mount --bind /etc/alternatives "$saved"
            newetc=$(mktemp -d)
            mount -t tmpfs tmpfs "$newetc"
            mount --bind "$newetc" /etc
            mkdir -p /etc/pve /etc/alternatives
            mount --bind "$saved" /etc/alternatives
            mount -t tmpfs tmpfs /var/lib
            export PATH={path}
            bash {witness} > "$out/first.out"
            echo first-baseline=$(stat -c %a /var/lib/hermes-control-deploy/c08cb1e-guest-node-witness/qm-baseline.txt)
            echo first-dir=$(stat -c %a /var/lib/hermes-control-deploy/c08cb1e-guest-node-witness)
            echo first-lock=$(stat -c %a /var/lib/hermes-control-deploy/c08cb1e-guest-node-witness/lock)
            cp /var/lib/hermes-control-deploy/c08cb1e-guest-node-witness/qm-baseline.txt "$out/baseline.txt"
            bash {witness} > "$out/second.out"
            cmp -s "$out/baseline.txt" /var/lib/hermes-control-deploy/c08cb1e-guest-node-witness/qm-baseline.txt
            echo baseline-unchanged=yes
            cat "$out/first.out"
            echo '--- second ---'
            cat "$out/second.out"
            """
        )
        completed = subprocess.run(
            ["unshare", "--user", "--mount", "--map-root-user", "bash", "-c", inner],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("host-mutation=yes", completed.stdout)
        self.assertIn("read-only=no", completed.stdout)
        self.assertIn("mutation-dir=/var/lib/hermes-control-deploy/c08cb1e-guest-node-witness mode=0700", completed.stdout)
        self.assertIn("mutation-file=/var/lib/hermes-control-deploy/c08cb1e-guest-node-witness/lock action=create-or-truncate", completed.stdout)
        self.assertIn("mutation-file=/var/lib/hermes-control-deploy/c08cb1e-guest-node-witness/qm-now.txt action=replace", completed.stdout)
        self.assertIn("mutation-file=/var/lib/hermes-control-deploy/c08cb1e-guest-node-witness/qm-baseline.txt action=create-once-then-compare mode=0600", completed.stdout)
        self.assertIn("guests=not-started-stopped-or-destroyed", completed.stdout)
        self.assertIn("baseline=created lines=2", completed.stdout)
        self.assertIn("baseline=matched lines=2", completed.stdout)
        self.assertIn("first-dir=700", completed.stdout)
        self.assertIn("first-baseline=600", completed.stdout)
        self.assertIn("baseline-unchanged=yes", completed.stdout)
        self.assertNotIn("read-only=yes", completed.stdout)
        self.assertFalse(Path("/var/lib/hermes-control-deploy").exists())

    def test_config_rewrite(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML is not installed")
        stable = "/opt/hermes-fleet-control/dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a"
        new = "/opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688"
        text = (
            "mcp_servers:\n"
            "  fleet:\n"
            f"    command: {stable}/fleet-mcp/index.js\n"
            "    args:\n"
            "      - node\n"
            f"    cwd: {stable}/fleet-mcp\n"
            "other: leave\n"
        )
        updated, status = material.rewrite_config(text, stable, new, "fleet")
        self.assertEqual(status, "rewritten")
        self.assertNotIn(stable, updated)
        self.assertIn("other: leave", updated)
        shortcut = (
            "mcp_servers:\n"
            "  fleet:\n"
            "    command: node\n"
            "  other:\n"
            "    command: ${HERMES_FLEET_CONTROL_ROOT}/fleet-mcp\n"
        )
        with self.assertRaises(material.Stop):
            material.rewrite_config(shortcut, stable, new, "fleet")

    def test_atomic_replace_keeps_mode_and_survives_short_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("old", encoding="utf-8")
            os.chmod(path, 0o640)
            before = path.stat()
            order: list[str] = []
            real_write = os.write
            real_chown = os.chown
            real_chmod = os.chmod

            def short_write(fd, data):
                return real_write(fd, data[:3])

            def record_chown(*args, **kwargs):
                order.append("chown")
                return real_chown(*args, **kwargs)

            def record_chmod(*args, **kwargs):
                order.append("chmod")
                return real_chmod(*args, **kwargs)

            with unittest.mock.patch("os.write", short_write), unittest.mock.patch(
                "os.chown", record_chown
            ), unittest.mock.patch("os.chmod", record_chmod):
                material.atomic_replace(path, b"new-bytes")
            self.assertEqual(path.read_bytes(), b"new-bytes")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
            self.assertEqual(path.stat().st_uid, before.st_uid)
            self.assertLess(order.index("chown"), order.index("chmod"))
            self.assertFalse((Path(tmp) / "config.yaml.c08cb1e-tmp").exists())

            def fail_fsync(_fd):
                raise OSError("fsync failed")

            path.write_bytes(b"keep")
            with unittest.mock.patch("os.fsync", fail_fsync):
                with self.assertRaises(OSError):
                    material.atomic_replace(path, b"lost")
            self.assertEqual(path.read_bytes(), b"keep")
            self.assertFalse((Path(tmp) / "config.yaml.c08cb1e-tmp").exists())
            dangling = Path(tmp) / "dangling"
            dangling.symlink_to(Path(tmp) / "missing")
            with self.assertRaises(material.Stop):
                material.atomic_replace(dangling, b"nope")
            self.assertTrue(dangling.is_symlink())

    def test_dropin_refuses_secret_path_and_keeps_header(self):
        stable = "/opt/hermes-fleet-control/stable"
        new = "/opt/hermes-fleet-control/new"
        text = (
            "[Service]\n"
            f"Environment=HERMES_FLEET_CONTROL_ROOT={stable}\n"
            f"Environment=PATH={stable}/bin\n"
        )
        dropin = material.retirement_dropin(text, stable, new)
        self.assertIn("Environment=HERMES_FLEET_CONTROL_ROOT=" + str(material.NEW), dropin)
        self.assertIn(f"Environment=PATH={new}/bin", dropin)
        self.assertNotIn("Environment=HERMES_FLEET_CONTROL_ROOT=" + stable, dropin)
        secret = text + f"Environment=FLEET_PROVISIONER_CALLER_TOKEN={stable}/token\n"
        with self.assertRaises(material.Stop):
            material.retirement_dropin(secret, stable, new)

    def test_tools_and_projection(self):
        material.require_tools(
            {"worker_status", "ensure_worker", "onboard_worker", "delegate_worker", "retire_worker"}
        )
        with self.assertRaises(material.Stop):
            material.require_tools(
                {
                    "worker_status",
                    "ensure_worker",
                    "onboard_worker",
                    "delegate_worker",
                    "retire_worker",
                    "send_message",
                }
            )
        projected = material.project_workers(
            {
                "api_version": "v1",
                "kind": "WorkerList",
                "workers": [
                    {
                        "name": "alpha",
                        "declared": True,
                        "retained": False,
                        "observed": {"state": "ready", "vmid": 1, "buzz_public_key_hex": "ab"},
                        "tombstone": None,
                        "onboarding": {"id": "onb_1", "status": "complete"},
                        "note": "sk-test-value",
                    }
                ],
            }
        )
        self.assertEqual(projected[0]["onboarding_id"], "onb_1")
        self.assertNotIn("note", projected[0])
        self.assertNotIn("sk-test-value", str(projected))

    def test_env_key_report_hides_multiline_secrets(self):
        secret = "MIIabc+/xyz,qqq"
        text = "OK_NAME=value\n" + secret + "=not-a-name\n-----BEGIN\nTOKEN=hidden-value\n"
        report = "\n".join(material.env_key_report(text))
        self.assertIn("fleet-env-name-count=2", report)
        self.assertIn("fleet-env-unparsed-lines=2", report)
        self.assertIn("FLEET_PROVISIONER_URL=absent", report)
        self.assertIn("FLEET_PROVISIONER_CALLER_TOKEN=absent", report)
        digest = hashlib.sha256(b"OK_NAME\nTOKEN\n").hexdigest()
        self.assertIn("fleet-env-names-sha256=" + digest, report)
        for hidden in (secret, "BEGIN", "hidden-value", "not-a-name", "OK_NAME"):
            self.assertNotIn(hidden, report)
        allowed = ("fleet-env-", "FLEET_PROVISIONER_URL=", "FLEET_PROVISIONER_CALLER_TOKEN=")
        self.assertTrue(all(line.startswith(allowed) for line in report.splitlines()))
        pem = (
            'SSL_KEY="-----BEGIN PRIVATE KEY-----\n'
            "q83vEiZZtopSecretTail==\n"
            '-----END PRIVATE KEY-----"\n'
            "GOOD=1\n"
            "OK_NAME=1\n"
        )
        pem_report = "\n".join(material.env_key_report(pem))
        self.assertIn("fleet-env-name-count=3", pem_report)
        self.assertIn(hashlib.sha256(b"GOOD\nOK_NAME\nSSL_KEY\n").hexdigest(), pem_report)
        for hidden in ("q83vEiZZtopSecretTail", "SSL_KEY", "GOOD", "OK_NAME", "PRIVATE KEY"):
            self.assertNotIn(hidden, pem_report)
        quoted = 'A="line1\nSECRETWORD=abc"\nOK_NAME=1\n'
        quoted_report = "\n".join(material.env_key_report(quoted))
        self.assertIn(hashlib.sha256(b"A\nOK_NAME\n").hexdigest(), quoted_report)
        self.assertNotIn("SECRETWORD", quoted_report)
        self.assertNotIn("abc", quoted_report)
        standalone = "GOOD=1\nq83vEiZZtopSecretTail==\n"
        standalone_report = "\n".join(material.env_key_report(standalone))
        self.assertNotIn("q83vEiZZtopSecretTail", standalone_report)
        self.assertNotIn("GOOD", standalone_report)
        required = "FLEET_PROVISIONER_URL=https://secret.example/token-value\n"
        required_report = "\n".join(material.env_key_report(required))
        self.assertIn("FLEET_PROVISIONER_URL=present", required_report)
        self.assertNotIn("secret.example", required_report)
        self.assertNotIn("token-value", required_report)
        self.assertEqual(material.env_key_report(pem), material.env_key_report(pem))

    def test_relative_script_rejects_escape_symlink_and_wrong_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "checkout"
            mcp = root / "fleet-mcp"
            mcp.mkdir(parents=True)
            script = mcp / "index.js"
            script.write_text("console.log(1)\n", encoding="utf-8")
            outside = Path(tmp) / "node"
            outside.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(outside, 0o755)
            linked = Path(tmp) / "node-link"
            linked.symlink_to(outside)

            def resolve(name, target=outside):
                return str(target) if name == "node" else None

            with unittest.mock.patch.object(material, "resolve_fixed_tool", resolve):
                good = material.relative_script_fact("node", str(mcp), "index.js", str(root))
                self.assertEqual(good, "relative-script:index.js")
                outside_mcp = Path(tmp) / "outside-mcp"
                outside_mcp.mkdir()
                (outside_mcp / "index.js").write_text("console.log(1)\n", encoding="utf-8")
                linked_root = Path(tmp) / "linked-root"
                linked_root.mkdir()
                linked_cwd = linked_root / "fleet-mcp"
                linked_cwd.symlink_to(outside_mcp)
                self.assertIsNone(
                    material.relative_script_fact("node", str(linked_cwd), "index.js", str(linked_root))
                )
                self.assertIsNone(material.relative_script_fact("node", str(mcp), "../x.js", str(root)))
                self.assertIsNone(material.relative_script_fact("node", str(root), "index.js", str(root)))
                script.unlink()
                alias = mcp / "index.js"
                alias.symlink_to(outside)
                self.assertIsNone(material.relative_script_fact("node", str(mcp), "index.js", str(root)))

            inside = mcp / "node"
            inside.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(inside, 0o755)
            script_file = mcp / "real.js"
            script_file.write_text("console.log(1)\n", encoding="utf-8")
            with unittest.mock.patch.object(material, "resolve_fixed_tool", lambda name: str(inside)):
                self.assertIsNone(material.relative_script_fact("node", str(mcp), "real.js", str(root)))
            with unittest.mock.patch.object(material, "resolve_fixed_tool", lambda name: str(linked)):
                self.assertEqual(
                    material.relative_script_fact("node", str(mcp), "real.js", str(root)),
                    "relative-script:real.js",
                )

    def test_dropin_order_and_environment_file_precedence(self):
        self.assertFalse(material.dropin_order_ok(["fleet-delegation.conf", "override.conf"]))
        self.assertTrue(material.dropin_order_ok(["fleet-delegation.conf"]))
        self.assertEqual(
            material.delegation_location(Path("/run/systemd/system/x/fleet-delegation.conf"), False),
            "rejected",
        )
        self.assertEqual(
            material.delegation_location(Path("/etc/systemd/system/unit.d/fleet-delegation.conf"), False),
            "system-config",
        )
        self.assertEqual(
            material.delegation_location(Path("/tmp/evil/.config/systemd/user/fleet-delegation.conf"), True),
            "rejected",
        )
        with tempfile.TemporaryDirectory() as tmp:
            secret = "MIIabc+/xyz,qqq"
            env_file = Path(tmp) / "fleet.env"
            env_file.write_text(
                "PLAIN=1\n" + secret + "=nope\nHERMES_FLEET_CONTROL_ROOT=/opt/other\n",
                encoding="utf-8",
            )
            shown = {prop: "" for prop in material.SHOW_PROPS}
            shown["ExecStart"] = "/usr/bin/node"
            shown["WorkingDirectory"] = "/tmp"
            shown["EnvironmentFiles"] = str(env_file) + " (ignore_errors)"
            self.assertTrue(material.env_assigns_root_or_stable(env_file.read_text(encoding="utf-8"), "/opt/stable"))
            self.assertFalse(material.effective_unit_ok(shown, "/opt/stable"))
            self.assertNotIn(secret, str(shown.values()))
            shown["EnvironmentFiles"] = ""
            shown["ExecStart"] = "/opt/stable/bin/node"
            self.assertFalse(material.effective_unit_ok(shown, "/opt/stable"))
            shown["ExecStart"] = "/usr/bin/node"
            shown["WorkingDirectory"] = "/opt/stable"
            self.assertFalse(material.effective_unit_ok(shown, "/opt/stable"))
            shown["WorkingDirectory"] = "/tmp"
            missing = Path(tmp) / "missing.env"
            shown["EnvironmentFiles"] = "-" + str(missing) + " (ignore_errors)"
            self.assertTrue(material.effective_unit_ok(shown, "/opt/stable"))
            shown["EnvironmentFiles"] = str(missing)
            self.assertFalse(material.effective_unit_ok(shown, "/opt/stable"))
            optional = Path(tmp) / "optional.env"
            optional.write_text("HERMES_FLEET_CONTROL_ROOT=/opt/new\n", encoding="utf-8")
            shown["EnvironmentFiles"] = "-" + str(optional) + " (ignore_errors)"
            self.assertFalse(material.effective_unit_ok(shown, "/opt/stable"))
            link_env = Path(tmp) / "link.env"
            link_env.symlink_to(optional)
            shown["EnvironmentFiles"] = "-" + str(link_env)
            self.assertFalse(material.effective_unit_ok(shown, "/opt/stable"))
            shown["EnvironmentFiles"] = "-/opt/stable/fleet.env"
            self.assertFalse(material.effective_unit_ok(shown, "/opt/stable"))
            quoted_root = Path(tmp) / "quoted.env"
            quoted_root.write_text('OTHER="\n/opt/stable\n"\n', encoding="utf-8")
            shown["EnvironmentFiles"] = str(quoted_root)
            self.assertFalse(material.effective_unit_ok(shown, "/opt/stable"))

    def test_private_write_and_shared_lock_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note"
            old = os.umask(0)
            try:
                material._private_write(path, b"abc")
            finally:
                os.umask(old)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            material._private_write(path, b"abc")
            with self.assertRaises(material.Stop):
                material._private_write(path, b"other")
            lock = Path(tmp) / "journal.lock"
            lock.write_text("x", encoding="utf-8")
            seen = {}
            real_flock = material.fcntl.flock

            def record(fd, op):
                seen.setdefault("ops", []).append(op)
                return real_flock(fd, op)

            with unittest.mock.patch.object(material.fcntl, "flock", record):
                material.probe_lock(lock, "delegations")
            self.assertIn(material.fcntl.LOCK_SH | material.fcntl.LOCK_NB, seen["ops"])
            link = Path(tmp) / "lock-link"
            link.symlink_to(lock)
            with self.assertRaises(material.Stop):
                material.probe_lock(link, "delegations")
            self.assertEqual(lock.read_text(encoding="utf-8"), "x")

    def test_restart_held_requires_the_same_process(self):
        first = {"ActiveState": "active", "SubState": "running", "MainPID": "41", "NRestarts": "0"}
        self.assertEqual(material.restart_held(first, dict(first), 41), [])
        changed = dict(first)
        changed["NRestarts"] = "1"
        self.assertIn("settled-nrestarts", material.restart_held(first, changed, 41))
        moved = dict(first)
        moved["MainPID"] = "42"
        self.assertIn("settled-pid", material.restart_held(first, moved, 41))
        self.assertEqual(material.gateway_before_pid({"ActiveState": "failed", "SubState": "failed", "MainPID": "0"}), 0)

    def test_preflight_writes_nothing(self):
        writes: list[str] = []
        real_open = os.open

        def guard(path, flags, *args, **kwargs):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC):
                writes.append(str(path))
            return real_open(path, flags, *args, **kwargs)

        def fake_run(argv, cwd=None):
            if argv[:2] == ["hostname", "-s"]:
                return 0, "control\n"
            if argv[:2] == ["hostname", "-f"]:
                return 0, "control.example\n"
            return 0, "not-loaded\n"

        def forbidden(*_args, **_kwargs):
            raise AssertionError("provisioner import")

        stdout = io.StringIO()
        with unittest.mock.patch("os.open", guard), unittest.mock.patch.object(
            material, "_run", fake_run
        ), unittest.mock.patch.object(material, "stable_dirs", lambda: []), unittest.mock.patch.object(
            material, "provisioner_units", lambda: []
        ), unittest.mock.patch.object(material, "deployed_state_dir", forbidden), contextlib.redirect_stdout(
            stdout
        ):
            code = material.cmd_preflight()
        self.assertEqual(writes, [])
        self.assertEqual(code, 4)
        self.assertIn("read-only=yes", stdout.getvalue())
        self.assertIn("onboarding-dir=not-on-this-host", stdout.getvalue())
        self.assertNotIn("MIIabc", stdout.getvalue())

    def _show(self, **overrides) -> dict[str, str]:
        shown = {prop: "" for prop in material.SHOW_PROPS}
        shown.update(
            {
                "LoadState": "loaded",
                "ActiveState": "active",
                "SubState": "running",
                "MainPID": "40",
                "NRestarts": "0",
                "NeedDaemonReload": "no",
                "FragmentPath": "/etc/systemd/system/hermes-gateway-control.service",
                "DropInPaths": "",
                "EnvironmentFiles": "",
                "ExecStart": "/usr/bin/node",
                "WorkingDirectory": "/tmp",
            }
        )
        shown.update(overrides)
        return shown

    def _evidence(self, root: Path) -> tuple[Path, Path, Path]:
        evidence = root / "evidence"
        live = root / "live"
        evidence.mkdir(mode=0o700)
        live.mkdir(mode=0o700)
        journal = root / "journal.txt"
        journal.write_text("journal-v1", encoding="utf-8")
        os.chmod(journal, 0o600)
        delegation = live / "fleet-delegation.conf"
        delegation.write_text("[Service]\nEnvironment=PATH=/usr/bin\n", encoding="utf-8")
        config = live / "config.yaml"
        config.write_bytes(b"deployed-config\n")
        os.chmod(config, 0o640)
        profile = live / "profile.env"
        profile.write_text("A=1\n", encoding="utf-8")
        os.chmod(profile, 0o600)
        fleet = live / "fleet.env"
        fleet.write_text("B=2\n", encoding="utf-8")
        os.chmod(fleet, 0o600)
        fragment = live / "unit.fragment"
        fragment.write_text("[Unit]\n", encoding="utf-8")
        stable = "/opt/hermes-fleet-control/stable"
        files = {
            "journals.manifest": (material.manifest_line(journal) + "\n").encode(),
            "fleet-delegation.conf": delegation.read_bytes(),
            "config.yaml": b"baseline-config\n",
            "config.mode": b"416",
            "config.yaml.deployed": b"deployed-config\n",
            "fleet-retirement.conf.desired": b"retirement-v1\n",
            "fleet.env": fleet.read_bytes(),
            "profile.env": profile.read_bytes(),
            "unit.fragment": fragment.read_bytes(),
            "stable_dir": (stable + "\n").encode(),
            "scope": b"user\n",
            "config.path": (str(config) + "\n").encode(),
            "profile.env.path": (str(profile) + "\n").encode(),
            "fleet.env.path": (str(fleet) + "\n").encode(),
            "unit.fragment.path": (str(fragment) + "\n").encode(),
            "delegation.path": (str(delegation) + "\n").encode(),
        }
        for name, data in files.items():
            material._private_write(evidence / name, data)
        return evidence, live, journal

    def test_configure_writes_evidence_before_live_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence, live, _journal = self._evidence(Path(tmp))
            config = live / "config.yaml"
            unchanged = str(material.NEW) + "/fleet-mcp/index.js\n"
            config.write_text(unchanged, encoding="utf-8")
            (evidence / "config.yaml").write_bytes(unchanged.encode())
            (evidence / "config.yaml.deployed").unlink()
            (evidence / "fleet-retirement.conf.desired").unlink()
            delegation = live / "fleet-delegation.conf"
            shown = self._show(DropInPaths=str(delegation))
            env = {"HERMES_FLEET_CONTROL_ROOT": "/opt/hermes-fleet-control/stable"}

            def explode(*_args, **_kwargs):
                raise RuntimeError("edit failed")

            stdout = io.StringIO()
            with unittest.mock.patch.object(material, "evidence_root", lambda: evidence), unittest.mock.patch.object(
                material, "selected_scope", lambda: ("user", True)
            ), unittest.mock.patch.object(
                material, "_live_gateway", lambda _user: (shown, env, 40)
            ), unittest.mock.patch.object(material, "_require_manifest", lambda _env: None), unittest.mock.patch.object(
                material, "delegation_location", lambda _path, _user: "user-config"
            ), unittest.mock.patch.object(material, "atomic_replace", explode), contextlib.redirect_stdout(stdout):
                with self.assertRaises(RuntimeError):
                    material.cmd_configure()
            self.assertEqual(config.read_text(encoding="utf-8"), unchanged)
            self.assertFalse((live / "fleet-retirement.conf").exists())
            self.assertTrue((evidence / "fleet-retirement.conf.desired").is_file())
            self.assertEqual((evidence / "config.status").read_text(encoding="utf-8"), "unchanged")
            self.assertEqual((evidence / "config.yaml.deployed").read_bytes(), unchanged.encode())

    def test_rollback_inactive_unit_warns_and_keeps_journals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, live, journal = self._evidence(root)
            journal.write_text("journal-v2", encoding="utf-8")
            dropin = live / "fleet-retirement.conf"
            dropin.write_bytes(b"retirement-v1\n")
            delegation = live / "fleet-delegation.conf"
            failed = self._show(
                ActiveState="failed",
                SubState="failed",
                MainPID="0",
                ExecStart="/opt/hermes-fleet-control/stable/bin/node",
                DropInPaths=str(delegation) + " " + str(dropin),
            )
            reloaded = self._show(
                ActiveState="failed",
                SubState="failed",
                MainPID="0",
                ExecStart="/opt/hermes-fleet-control/stable/bin/node",
                DropInPaths=str(delegation),
            )
            running = self._show(MainPID="77", NRestarts="0", DropInPaths=str(delegation))
            shows = [failed, reloaded, running, dict(running)]
            commands: list[list[str]] = []

            def fake_show(_user):
                return shows.pop(0)

            def fake_run(argv, cwd=None):
                commands.append(argv)
                return 0, ""

            def fake_env(pid):
                if pid == 77:
                    return {"HERMES_FLEET_CONTROL_ROOT": "/opt/hermes-fleet-control/stable"}
                return None

            stdout = io.StringIO()
            with unittest.mock.patch.object(material, "evidence_root", lambda: evidence), unittest.mock.patch.object(
                material, "systemctl_show", fake_show
            ), unittest.mock.patch.object(material, "_run", fake_run), unittest.mock.patch.object(
                material, "read_environ", fake_env
            ), unittest.mock.patch.object(material.time, "sleep", lambda seconds: None), contextlib.redirect_stdout(
                stdout
            ):
                code = material.cmd_rollback()
            text = stdout.getvalue()
            self.assertEqual(code, 0, text)
            self.assertIn("WARNING: journal manifest changed; rollback will not modify journals", text)
            self.assertIn("journal-warning=changed", text)
            self.assertIn("rollback=done", text)
            self.assertEqual(journal.read_text(encoding="utf-8"), "journal-v2")
            self.assertEqual((live / "config.yaml").read_bytes(), b"baseline-config\n")
            self.assertFalse(dropin.exists())
            removed = evidence / "fleet-retirement.conf.removed"
            self.assertEqual(removed.read_bytes(), b"retirement-v1\n")
            self.assertFalse((live / "fleet-retirement.conf.removed").exists())
            flat = [" ".join(argv) for argv in commands]
            self.assertGreaterEqual(sum("daemon-reload" in item for item in flat), 2)
            self.assertTrue(any(item.endswith("restart " + material.UNIT) for item in flat))
            self.assertEqual(material.RESTART_SETTLE_SECONDS, 10)

    def _failed_rollback(self, evidence: Path, live: Path, *, shows: list[dict[str, str]] | None = None):
        delegation = live / "fleet-delegation.conf"
        dropin = live / "fleet-retirement.conf"
        failed = self._show(
            ActiveState="failed",
            SubState="failed",
            MainPID="0",
            ExecStart="/opt/hermes-fleet-control/stable/bin/node",
            DropInPaths=str(delegation) + (" " + str(dropin) if dropin.exists() else ""),
        )
        reloaded = self._show(
            ActiveState="failed",
            SubState="failed",
            MainPID="0",
            ExecStart="/opt/hermes-fleet-control/stable/bin/node",
            DropInPaths=str(delegation),
        )
        running = self._show(MainPID="77", NRestarts="0", DropInPaths=str(delegation))
        queued = shows if shows is not None else [failed, reloaded, running, dict(running)]
        commands: list[list[str]] = []

        def fake_show(_user):
            return queued.pop(0)

        def fake_run(argv, cwd=None):
            commands.append(argv)
            return 0, ""

        def fake_env(pid):
            if pid == 77:
                return {"HERMES_FLEET_CONTROL_ROOT": "/opt/hermes-fleet-control/stable"}
            return None

        stdout = io.StringIO()
        stderr = io.StringIO()
        with unittest.mock.patch.object(material, "evidence_root", lambda: evidence), unittest.mock.patch.object(
            material, "systemctl_show", fake_show
        ), unittest.mock.patch.object(material, "_run", fake_run), unittest.mock.patch.object(
            material, "read_environ", fake_env
        ), unittest.mock.patch.object(material.time, "sleep", lambda seconds: None), contextlib.redirect_stdout(
            stdout
        ), contextlib.redirect_stderr(stderr):
            try:
                code = material.cmd_rollback()
            except material.Stop:
                code = 1
        return code, stdout.getvalue(), stderr.getvalue(), commands

    def test_rollback_warns_on_side_file_drift_and_keeps_those_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence, live, journal = self._evidence(Path(tmp))
            (live / "profile.env").write_text("A=changed\n", encoding="utf-8")
            os.chmod(live / "profile.env", 0o600)
            (live / "fleet.env").write_text("B=drift\n", encoding="utf-8")
            (live / "unit.fragment").write_text("[Unit]\nDrift=1\n", encoding="utf-8")
            (live / "fleet-delegation.conf").write_text("[Service]\nEnvironment=PATH=/usr/bin\nDrift=1\n", encoding="utf-8")
            dropin = live / "fleet-retirement.conf"
            dropin.write_bytes(b"retirement-v1\n")
            code, text, _err, commands = self._failed_rollback(evidence, live)
            self.assertEqual(code, 0, text)
            self.assertIn("side-file-drift=profile.env.path,fleet.env.path,unit.fragment.path", text)
            self.assertIn("WARNING: side file differs from baseline; rollback will not modify it", text)
            self.assertIn("delegation-drift=changed", text)
            self.assertIn("WARNING: delegation file differs from baseline; rollback will not modify it", text)
            self.assertIn("config-rollback=restored", text)
            self.assertIn("rollback=done", text)
            self.assertEqual((live / "profile.env").read_text(encoding="utf-8"), "A=changed\n")
            self.assertEqual((live / "fleet.env").read_text(encoding="utf-8"), "B=drift\n")
            self.assertEqual((live / "unit.fragment").read_text(encoding="utf-8"), "[Unit]\nDrift=1\n")
            self.assertIn("Drift=1", (live / "fleet-delegation.conf").read_text(encoding="utf-8"))
            self.assertEqual((live / "config.yaml").read_bytes(), b"baseline-config\n")
            self.assertFalse(dropin.exists())
            self.assertEqual(journal.read_text(encoding="utf-8"), "journal-v1")
            flat = [" ".join(argv) for argv in commands]
            self.assertTrue(any(item.endswith("restart " + material.UNIT) for item in flat))

    def test_rollback_already_stable_still_reloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, live, journal = self._evidence(root)
            (live / "config.yaml").write_bytes(b"baseline-config\n")
            delegation = live / "fleet-delegation.conf"
            for kind, leaf in (
                ("delegations", "fleet-delegations"),
                ("onboarding", "fleet-onboarding"),
                ("retirements", "fleet-retirements"),
            ):
                directory = root / leaf
                directory.mkdir(mode=0o700)
                os.chmod(directory, 0o700)
                (directory / "row.json").write_text("{}\n", encoding="utf-8")
            env = {
                "HERMES_FLEET_CONTROL_ROOT": "/opt/hermes-fleet-control/stable",
                "FLEET_CONTROL_HERMES_PROFILE": "control",
                "FLEET_DELEGATION_JOURNAL_DIR": str(root / "fleet-delegations"),
                "FLEET_ONBOARD_JOURNAL_DIR": str(root / "fleet-onboarding"),
                "FLEET_RETIRE_JOURNAL_DIR": str(root / "fleet-retirements"),
            }
            (evidence / "journals.manifest").write_bytes(material.journal_manifest(env).encode())
            shown = self._show(
                MainPID="12",
                ExecStart="/opt/hermes-fleet-control/stable/bin/node",
                DropInPaths=str(delegation),
            )
            shows = [dict(shown), dict(shown)]
            commands: list[list[str]] = []

            def fake_show(_user):
                return shows.pop(0)

            def fake_run(argv, cwd=None):
                commands.append(argv)
                return 0, ""

            stdout = io.StringIO()
            with unittest.mock.patch.object(material, "evidence_root", lambda: evidence), unittest.mock.patch.object(
                material, "systemctl_show", fake_show
            ), unittest.mock.patch.object(material, "_run", fake_run), unittest.mock.patch.object(
                material, "read_environ", lambda _pid: env
            ), contextlib.redirect_stdout(stdout):
                code = material.cmd_rollback()
            text = stdout.getvalue()
            self.assertEqual(code, 0, text)
            self.assertIn("rollback=already-stable", text)
            self.assertIn("journal-warning=none", text)
            self.assertEqual(journal.read_text(encoding="utf-8"), "journal-v1")
            flat = [" ".join(argv) for argv in commands]
            self.assertTrue(any("daemon-reload" in item for item in flat))
            self.assertFalse(any("restart" in item for item in flat))

    def test_guest_node_witness_rejects_args_and_symlinks(self):
        witness = ROOT / "docs" / "deploy" / "c08cb1e-guest-node-witness.sh"
        refused = subprocess.run(
            ["bash", str(witness), "extra"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(refused.returncode, 2)
        self.assertIn("STOP:", refused.stderr)
        stub = Path(tempfile.mkdtemp())
        (stub / "qm").write_text("#!/bin/sh\necho 'VMID NAME STATUS'\necho '101 alpha running'\n", encoding="utf-8")
        (stub / "systemctl").write_text("#!/bin/sh\necho not-found\nexit 0\n", encoding="utf-8")
        os.chmod(stub / "qm", 0o755)
        os.chmod(stub / "systemctl", 0o755)
        path = str(stub) + ":" + os.environ["PATH"]
        inner = textwrap.dedent(
            f"""\
            set -euo pipefail
            saved=$(mktemp -d)
            out=$(mktemp -d)
            mount --bind /etc/alternatives "$saved"
            newetc=$(mktemp -d)
            mount -t tmpfs tmpfs "$newetc"
            mount --bind "$newetc" /etc
            mkdir -p /etc/pve /etc/alternatives
            mount --bind "$saved" /etc/alternatives
            mount -t tmpfs tmpfs /var/lib
            export PATH={path}
            mkdir -p /var/lib/safe
            ln -s /var/lib/safe /var/lib/hermes-control-deploy
            set +e
            bash {witness} > "$out/symlink.out" 2> "$out/symlink.err"
            status=$?
            set -e
            echo status=$status
            echo wrote=$(test -e /var/lib/safe/c08cb1e-guest-node-witness && echo yes || echo no)
            cat "$out/symlink.err"
            """
        )
        completed = subprocess.run(
            ["unshare", "--user", "--mount", "--map-root-user", "bash", "-c", inner],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("status=1", completed.stdout)
        self.assertIn("STOP: evidence path is a symlink", completed.stdout)
        self.assertIn("wrote=no", completed.stdout)

    def test_rollback_reverses_config_drift_and_preserves_unrelated_keys(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML is not installed")
        stable = "/opt/hermes-fleet-control/stable"
        new = str(material.NEW)
        deployed = (
            "mcp_servers:\n"
            "  fleet:\n"
            f"    command: {new}/fleet-mcp/index.js\n"
            "    args:\n"
            "      - index.js\n"
            f"    cwd: {new}/fleet-mcp\n"
            "note: keep\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            evidence, live, journal = self._evidence(Path(tmp))
            (evidence / "config.yaml.deployed").write_bytes(deployed.encode())
            drifted = deployed + "extra: operator\n"
            config = live / "config.yaml"
            config.write_text(drifted, encoding="utf-8")
            dropin = live / "fleet-retirement.conf"
            dropin.write_bytes(b"retirement-v1\n")
            code, text, _err, _commands = self._failed_rollback(evidence, live)
            self.assertEqual(code, 0, text)
            self.assertIn("config-rollback=reversed", text)
            self.assertIn("rollback=done", text)
            restored = config.read_text(encoding="utf-8")
            self.assertNotIn(new, restored)
            self.assertIn(stable + "/fleet-mcp", restored)
            self.assertIn("extra: operator", restored)
            self.assertIn("note: keep", restored)
            self.assertEqual(journal.read_text(encoding="utf-8"), "journal-v1")
            self.assertFalse(dropin.exists())

    def test_rollback_preserves_unsafe_config_and_does_not_restart(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML is not installed")
        new = str(material.NEW)
        deployed = (
            "mcp_servers:\n"
            "  fleet:\n"
            f"    command: {new}/fleet-mcp/index.js\n"
            "    args:\n"
            "      - index.js\n"
            f"    cwd: {new}/fleet-mcp\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            evidence, live, journal = self._evidence(Path(tmp))
            (evidence / "config.yaml.deployed").write_bytes(deployed.encode())
            drifted = deployed + f"elsewhere: {new}/outside\n"
            config = live / "config.yaml"
            config.write_text(drifted, encoding="utf-8")
            before = config.read_bytes()
            dropin = live / "fleet-retirement.conf"
            dropin.write_bytes(b"retirement-v1\n")
            delegation = live / "fleet-delegation.conf"
            failed = self._show(
                ActiveState="inactive",
                SubState="dead",
                MainPID="0",
                DropInPaths=str(delegation) + " " + str(dropin),
            )
            reloaded = self._show(ActiveState="inactive", SubState="dead", MainPID="0", DropInPaths=str(delegation))
            code, text, err, commands = self._failed_rollback(evidence, live, shows=[failed, reloaded])
            self.assertEqual(code, 1, text + err)
            self.assertIn("config-rollback=incomplete", text)
            self.assertIn("rollback=incomplete", text)
            self.assertIn("operator intervention required", err)
            self.assertNotIn("rollback=done", text)
            self.assertNotIn("STEP 10 OK", text)
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse(dropin.exists())
            self.assertEqual(journal.read_text(encoding="utf-8"), "journal-v1")
            flat = [" ".join(argv) for argv in commands]
            self.assertFalse(any("restart" in item for item in flat))

    def test_confirm_reports_journal_drift_and_rejects_new_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, live, journal = self._evidence(root)
            for leaf in ("fleet-delegations", "fleet-onboarding", "fleet-retirements"):
                directory = root / leaf
                directory.mkdir(mode=0o700)
                os.chmod(directory, 0o700)
                (directory / "row.json").write_text("{}\n", encoding="utf-8")
            env = {
                "HERMES_FLEET_CONTROL_ROOT": "/opt/hermes-fleet-control/stable",
                "FLEET_DELEGATION_JOURNAL_DIR": str(root / "fleet-delegations"),
                "FLEET_ONBOARD_JOURNAL_DIR": str(root / "fleet-onboarding"),
                "FLEET_RETIRE_JOURNAL_DIR": str(root / "fleet-retirements"),
            }
            (evidence / "journals.manifest").write_bytes(material.journal_manifest(env).encode())
            journal.write_text("journal-v2", encoding="utf-8")
            (root / "fleet-delegations" / "row.json").write_text('{"added":true}\n', encoding="utf-8")
            (live / "fleet.env").write_text("B=drift\n", encoding="utf-8")
            (live / "config.yaml").write_bytes(b"baseline-config\nextra: kept\n")
            delegation = live / "fleet-delegation.conf"
            shown = self._show(MainPID="12", DropInPaths=str(delegation))
            stdout = io.StringIO()
            with unittest.mock.patch.object(material, "evidence_root", lambda: evidence), unittest.mock.patch.object(
                material, "selected_scope", lambda: ("user", True)
            ), unittest.mock.patch.object(
                material, "_live_gateway", lambda _user: (shown, env, 12)
            ), unittest.mock.patch.object(material, "require_pins", lambda *_args: None), unittest.mock.patch.object(
                material, "_cwd_under", lambda *_args: False
            ), contextlib.redirect_stdout(stdout):
                code = material.cmd_confirm()
            text = stdout.getvalue()
            self.assertEqual(code, 0, text)
            self.assertIn("journal-warning=changed", text)
            self.assertIn("WARNING: journal manifest changed; confirm will not modify journals", text)
            self.assertIn("side-file-drift=fleet.env.path", text)
            self.assertIn("STEP 11 OK", text)
            self.assertEqual((root / "fleet-delegations" / "row.json").read_text(encoding="utf-8"), '{"added":true}\n')
            self.assertEqual((live / "fleet.env").read_text(encoding="utf-8"), "B=drift\n")
            self.assertEqual((live / "config.yaml").read_bytes(), b"baseline-config\nextra: kept\n")
            config = live / "config.yaml"
            config.write_text("root: " + str(material.NEW) + "\n", encoding="utf-8")
            stderr = io.StringIO()
            with unittest.mock.patch.object(material, "evidence_root", lambda: evidence), unittest.mock.patch.object(
                material, "selected_scope", lambda: ("user", True)
            ), unittest.mock.patch.object(
                material, "_live_gateway", lambda _user: (shown, env, 12)
            ), unittest.mock.patch.object(material, "require_pins", lambda *_args: None), unittest.mock.patch.object(
                material, "_cwd_under", lambda *_args: False
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                with self.assertRaises(material.Stop):
                    material.cmd_confirm()
            self.assertIn("names the new checkout", stderr.getvalue())
            self.assertEqual(config.read_text(encoding="utf-8"), "root: " + str(material.NEW) + "\n")

    def test_shared_lock_stops_conflicting_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, live, journal = self._evidence(root)
            before = {path: path.read_bytes() for path in live.rglob("*") if path.is_file()}
            journal_before = journal.read_bytes()
            holder = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import fcntl, os, sys, time\n"
                    "fd = os.open(sys.argv[1], os.O_RDONLY | os.O_DIRECTORY)\n"
                    "fcntl.flock(fd, fcntl.LOCK_EX)\n"
                    "sys.stdout.write('held\\n')\n"
                    "sys.stdout.flush()\n"
                    "time.sleep(30)\n",
                    str(evidence.parent),
                ],
                stdout=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertEqual(holder.stdout.readline(), "held\n")
                for command in (
                    material.cmd_baseline,
                    material.cmd_configure,
                    material.cmd_restart,
                    material.cmd_verify,
                    material.cmd_rollback,
                    material.cmd_confirm,
                ):
                    stderr = io.StringIO()
                    with unittest.mock.patch.object(
                        material, "evidence_root", lambda evidence=evidence: evidence
                    ), unittest.mock.patch.object(
                        material, "LOCK_WAIT_SECONDS", 0
                    ), contextlib.redirect_stderr(stderr):
                        with self.assertRaises(material.Stop):
                            command()
                    self.assertIn("another deploy command holds the evidence lock", stderr.getvalue())
            finally:
                holder.kill()
                holder.wait(timeout=5)
                if holder.stdout is not None:
                    holder.stdout.close()
            self.assertEqual(journal.read_bytes(), journal_before)
            for path, data in before.items():
                self.assertEqual(path.read_bytes(), data)

    def test_partial_baseline_is_rewritten_and_journals_stay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "sha"
            journal = root / "journal.txt"
            journal.write_text("journal-body", encoding="utf-8")
            os.chmod(journal, 0o600)
            files = {
                "journals.manifest": b"manifest-v1\n",
                "config.yaml": b"config-v1\n",
                "scope": b"user\n",
            }
            order: list[str] = []
            real_write = material._private_write

            def boom(path, data):
                order.append(path.name)
                if path.name == "config.yaml":
                    raise OSError("interrupted")
                return real_write(path, data)

            with unittest.mock.patch.object(material, "_private_write", boom):
                with self.assertRaises(OSError):
                    material._save_baseline(evidence, files)
            self.assertEqual(order, ["config.yaml"])
            self.assertFalse(evidence.exists())
            self.assertFalse((root / "sha.staging").exists())
            self.assertEqual(journal.read_text(encoding="utf-8"), "journal-body")
            evidence.mkdir()
            (evidence / "journals.manifest").write_bytes(b"partial\n")
            (evidence / "extra").write_text("leave-me", encoding="utf-8")
            with self.assertRaises(material.Stop):
                material._save_baseline(evidence, files)
            self.assertEqual((evidence / "extra").read_text(encoding="utf-8"), "leave-me")
            self.assertEqual((evidence / "journals.manifest").read_bytes(), b"partial\n")
            (evidence / "extra").unlink()
            self.assertEqual(material._save_baseline(evidence, files), "created")
            self.assertEqual((evidence / "journals.manifest").read_bytes(), b"manifest-v1\n")
            self.assertEqual((evidence / "config.yaml").read_bytes(), b"config-v1\n")
            self.assertEqual(stat.S_IMODE(evidence.stat().st_mode) & 0o077, 0)
            self.assertEqual(material._save_baseline(evidence, files), "matched")
            changed = dict(files)
            changed["scope"] = b"system\n"
            with self.assertRaises(material.Stop):
                material._save_baseline(evidence, changed)
            self.assertEqual((evidence / "scope").read_bytes(), b"user\n")
            self.assertEqual(journal.read_text(encoding="utf-8"), "journal-body")

    def test_preflight_loaded_unit_still_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stable = root / "dcb3f950-checkout"
            stable.mkdir()
            home = root / "home"
            delegation = home / ".config" / "systemd" / "user" / "hermes.service.d" / "fleet-delegation.conf"
            delegation.parent.mkdir(parents=True)
            delegation.write_text("[Service]\n", encoding="utf-8")
            profiles = root / "profiles"
            config = profiles / "control" / "config.yaml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "mcp_servers:\n  fleet:\n    command: node\n    args: []\n    cwd: /tmp\n",
                encoding="utf-8",
            )
            fleet_env = root / "fleet.env"
            fleet_env.write_text("PLAIN=1\nenv-body-secret=hidden\n", encoding="utf-8")
            journals = {}
            for leaf, key in (
                ("fleet-delegations", "FLEET_DELEGATION_JOURNAL_DIR"),
                ("fleet-onboarding", "FLEET_ONBOARD_JOURNAL_DIR"),
                ("fleet-retirements", "FLEET_RETIRE_JOURNAL_DIR"),
            ):
                directory = root / leaf
                directory.mkdir(mode=0o700)
                os.chmod(directory, 0o700)
                (directory / "row.json").write_text("journal-body-secret\n", encoding="utf-8")
                journals[key] = str(directory)
            pid = str(os.getpid())
            props = {
                "LoadState": "loaded",
                "ActiveState": "active",
                "SubState": "running",
                "MainPID": pid,
                "NRestarts": "0",
                "FragmentPath": "/etc/systemd/system/hermes-gateway-control.service",
                "DropInPaths": str(delegation),
                "NeedDaemonReload": "no",
                "EnvironmentFiles": str(fleet_env) + " (ignore_errors)",
                "ExecStart": "/usr/bin/node",
                "WorkingDirectory": "/tmp",
            }
            show_text = "".join(key + "=" + value + "\n" for key, value in props.items())
            seen: list[list[str]] = []

            def fake_run(argv, cwd=None):
                seen.append(argv)
                if argv[:2] == ["hostname", "-s"]:
                    return 0, "control\n"
                if argv[:2] == ["hostname", "-f"]:
                    return 0, "control.example\n"
                if argv and argv[0] == "git":
                    if argv[-2:] == ["rev-parse", "HEAD"]:
                        return 0, material.STABLE_SHA + "\n"
                    if argv[-1] == "HEAD^{tree}":
                        return 0, material.STABLE_TREE + "\n"
                    if "get-url" in argv:
                        return 0, "https://example.test/org/repo.git\n"
                    return 0, ""
                if argv and argv[0] == "systemctl":
                    if "list-units" in argv:
                        return 0, ""
                    if "LoadState" in argv:
                        return (0, "loaded\n") if "--user" in argv else (0, "not-loaded\n")
                    if "--user" in argv:
                        return 0, show_text
                    return 0, "not-loaded\n"
                if argv and argv[0].endswith("node"):
                    return 0, "22\n"
                return 0, ""

            env = {
                "HERMES_FLEET_CONTROL_ROOT": str(stable),
                "HERMES_FLEET_CONTROL_INTEGRATION": "1",
                "HERMES_FLEET_MCP_SERVER": "fleet",
                "FLEET_CONTROL_HERMES_PROFILE": "control",
                "FLEET_CONTROL_PROFILES_ROOT": str(profiles),
                "HERMES_HOME": str(home),
                "FLEET_CONTROL_ENV_FILE": str(fleet_env),
            }
            env.update(journals)
            writes: list[str] = []
            real_open = os.open

            def guard(path, flags, *args, **kwargs):
                if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC):
                    writes.append(str(path))
                return real_open(path, flags, *args, **kwargs)

            stdout = io.StringIO()
            with unittest.mock.patch("os.open", guard), unittest.mock.patch.object(
                material, "_run", fake_run
            ), unittest.mock.patch.object(material, "stable_dirs", lambda: [stable]), unittest.mock.patch.object(
                material, "read_environ", lambda _pid: env
            ), unittest.mock.patch.object(material.Path, "home", lambda: home), contextlib.redirect_stdout(stdout):
                code = material.cmd_preflight()
            text = stdout.getvalue()
            self.assertEqual(writes, [])
            self.assertIn(code, (0, 4))
            self.assertIn("user-unit=loaded", text)
            self.assertIn("system-unit=not-loaded", text)
            self.assertTrue("user-mcp-command=public:node" in text or "user-mcp-config=unparsed" in text)
            self.assertIn("user-journals=private-nonempty", text)
            self.assertNotIn("env-body-secret", text)
            self.assertNotIn("journal-body-secret", text)
            self.assertTrue(any(argv[0] == "systemctl" and "--user" in argv for argv in seen))
            self.assertFalse(any(argv[0] == "systemctl" and argv[1:3] == ["start", material.UNIT] for argv in seen))

    def test_guest_node_witness_reports_a_held_lock(self):
        witness = ROOT / "docs" / "deploy" / "c08cb1e-guest-node-witness.sh"
        stub = Path(tempfile.mkdtemp())
        (stub / "qm").write_text("#!/bin/sh\necho 'VMID NAME STATUS'\necho '101 alpha running'\n", encoding="utf-8")
        (stub / "systemctl").write_text("#!/bin/sh\necho not-found\nexit 0\n", encoding="utf-8")
        os.chmod(stub / "qm", 0o755)
        os.chmod(stub / "systemctl", 0o755)
        path = str(stub) + ":" + os.environ["PATH"]
        inner = textwrap.dedent(
            f"""\
            set -euo pipefail
            saved=$(mktemp -d)
            mount --bind /etc/alternatives "$saved"
            newetc=$(mktemp -d)
            mount -t tmpfs tmpfs "$newetc"
            mount --bind "$newetc" /etc
            mkdir -p /etc/pve /etc/alternatives
            mount --bind "$saved" /etc/alternatives
            mount -t tmpfs tmpfs /var/lib
            export PATH={path}
            bash {witness}
            evidence=/var/lib/hermes-control-deploy/c08cb1e-guest-node-witness
            digest=$(sha256sum "$evidence/qm-baseline.txt")
            flock -n "$evidence/lock" sleep 30 &
            holder=$!
            held=no
            for _try in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
              if ! flock -n "$evidence/lock" true; then
                held=yes
                break
              fi
              sleep 0.05
            done
            set +e
            bash {witness} >/var/lib/second.out 2>/var/lib/second.err
            status=$?
            set -e
            echo status=$status
            echo held=$held
            echo digest-same=$(test "$(sha256sum "$evidence/qm-baseline.txt")" = "$digest" && echo yes || echo no)
            cat /var/lib/second.err
            kill "$holder"
            """
        )
        completed = subprocess.run(
            ["unshare", "--user", "--mount", "--map-root-user", "bash", "-c", inner],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("status=1", completed.stdout)
        self.assertIn("held=yes", completed.stdout)
        self.assertIn("STOP: evidence lock is held", completed.stdout)
        self.assertIn("digest-same=yes", completed.stdout)


if __name__ == "__main__":
    unittest.main()
