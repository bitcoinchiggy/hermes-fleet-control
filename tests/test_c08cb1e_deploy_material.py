"""Focused checks for the c08cb1e deploy helpers. No host contact."""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
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
        self.assertEqual(
            material.classify_mcp_args(["--token", "sk-test-value"]),
            "flag:--token,redacted",
        )
        self.assertEqual(
            material.classify_mcp_args(["--password", "hunter2"]),
            "flag:--password,redacted",
        )
        self.assertEqual(material.classify_mcp_args(["--token", "node"]), "flag:--token,redacted")
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
            "origin-embedded-token": "absent",
            "guest-node-signals": "absent",
            "provisioner-on-host": "no",
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
        usage = subprocess.run(
            [str(ROOT / "docs" / "deploy" / "c08cb1e_material.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(usage.returncode, 2)
        for name in material.COMMANDS:
            self.assertIn(name, usage.stderr)
        self.assertEqual(material.main(["c08cb1e_material.py", "not-a-command"]), 2)
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

    def test_config_rewrite_and_atomic_replace(self):
        import tempfile

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
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("old", encoding="utf-8")
            os.chmod(path, 0o640)
            before = path.stat()
            material.atomic_replace(path, b"new")
            self.assertEqual(path.read_bytes(), b"new")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
            self.assertEqual(path.stat().st_uid, before.st_uid)
            self.assertFalse((Path(tmp) / "config.yaml.c08cb1e-tmp").exists())

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


if __name__ == "__main__":
    unittest.main()
