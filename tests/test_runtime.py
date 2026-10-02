"""Managed helper interpreter. Does not install packages and does not use PATH."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fleet_control.runtime import (  # noqa: E402
    HERMES_AGENT_VENV,
    RuntimePlanError,
    execute_runtime_install,
    managed_python,
    plan_runtime_install,
    resolve_helper_python,
)

HERMES_PYTHON = str(Path(HERMES_AGENT_VENV) / "bin" / "python")
HELPERS = ("fleet-status", "fleet-ensure", "fleet-delegate")


class RuntimePlanTests(unittest.TestCase):
    def test_relative_interpreter_is_rejected(self) -> None:
        with self.assertRaises(RuntimePlanError) as caught:
            plan_runtime_install("python3", ROOT)
        self.assertIn("absolute", caught.exception.public_message)

    def test_hermes_agent_venv_is_rejected(self) -> None:
        with self.assertRaises(RuntimePlanError) as caught:
            plan_runtime_install(HERMES_PYTHON, ROOT)
        self.assertIn("Hermes agent", caught.exception.public_message)
        with self.assertRaises(RuntimePlanError):
            plan_runtime_install("/usr/bin/python3.12", HERMES_AGENT_VENV)

    def test_plan_uses_the_explicit_interpreter_and_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("cryptography>=41.0.7\n")
            plan = plan_runtime_install("/usr/bin/python3.12", root)
        self.assertEqual(plan.interpreter, "/usr/bin/python3.12")
        self.assertEqual(plan.create_argv, ("/usr/bin/python3.12", "-m", "venv", plan.venv_dir))
        self.assertEqual(plan.venv_python, managed_python(root))
        self.assertEqual(
            plan.install_argv,
            (
                plan.venv_python,
                "-m",
                "pip",
                "install",
                "--require-virtualenv",
                "-r",
                plan.requirements,
            ),
        )
        joined = " ".join(plan.create_argv + plan.install_argv)
        self.assertNotIn("apt-get", joined)
        self.assertNotIn("python3-cryptography", joined)
        self.assertNotEqual(plan.create_argv[0], "python3")

    def test_override_must_be_absolute_and_outside_the_agent_venv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(resolve_helper_python(root, {}), managed_python(root))
            with self.assertRaises(RuntimePlanError):
                resolve_helper_python(root, {"FLEET_CONTROL_PYTHON": "python3"})
            with self.assertRaises(RuntimePlanError):
                resolve_helper_python(root, {"FLEET_CONTROL_PYTHON": HERMES_PYTHON})
            chosen = "/usr/bin/python3.12"
            self.assertEqual(
                resolve_helper_python(root, {"FLEET_CONTROL_PYTHON": chosen}),
                chosen,
            )

    def test_execute_invokes_only_the_planned_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "checkout"
            root.mkdir()
            (root / "requirements.txt").write_text("cryptography>=41.0.7\n")
            interpreter = Path(tmp) / "python3.12"
            interpreter.write_text("#!/bin/sh\nexit 0\n")
            interpreter.chmod(0o755)
            plan = plan_runtime_install(str(interpreter), root)
            calls: list[list[str]] = []

            def runner(argv: object) -> None:
                values = [str(item) for item in argv]  # type: ignore[union-attr]
                calls.append(values)
                if values[1:3] == ["-m", "venv"]:
                    python = Path(values[3]) / "bin" / "python"
                    python.parent.mkdir(parents=True)
                    python.write_text("#!/bin/sh\nexit 0\n")
                    python.chmod(0o755)

            execute_runtime_install(plan, runner=runner)
        self.assertEqual(calls[0][0], str(interpreter))
        self.assertEqual(calls[0][1:3], ["-m", "venv"])
        self.assertEqual(calls[1][0], plan.venv_python)
        self.assertIn("--require-virtualenv", calls[1])
        self.assertIn(str(root / "requirements.txt"), calls[1])
        self.assertNotIn("apt-get", " ".join(calls[0] + calls[1]))

    def test_symlink_into_the_agent_venv_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "python"
            link.symlink_to(HERMES_PYTHON)
            with self.assertRaises(RuntimePlanError):
                plan_runtime_install(str(link), tmp)


class HelperBootstrapTests(unittest.TestCase):
    def test_helpers_reexec_before_importing_their_mains(self) -> None:
        mains = {
            "fleet-status": "fleet_control.status",
            "fleet-ensure": "fleet_control.ensure",
            "fleet-delegate": "fleet_control.delegate",
        }
        for name, module in mains.items():
            text = (ROOT / name).read_text()
            self.assertLess(text.index("reexec_managed_python()"), text.index(f"from {module} import main"))
            self.assertEqual(text.count("sys.path.insert"), 1, name)

    def test_direct_helper_does_not_stay_on_path_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / "managed-python"
            wrapper.write_text("#!/bin/sh\necho REEXEC\n")
            wrapper.chmod(0o755)
            env = os.environ.copy()
            env["FLEET_CONTROL_PYTHON"] = str(wrapper)
            env.pop("BUZZ_PRIVATE_KEY", None)
            proc = subprocess.run(
                [sys.executable, str(ROOT / "fleet-delegate")],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "REEXEC")
        self.assertNotIn("cryptography", proc.stderr)
        self.assertNotIn("ModuleNotFoundError", proc.stderr)

    def test_missing_managed_python_fails_before_cryptography(self) -> None:
        env = os.environ.copy()
        env.pop("FLEET_CONTROL_PYTHON", None)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "fleet-delegate")],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("managed python is unavailable", proc.stderr)
        self.assertNotIn("ModuleNotFoundError", proc.stderr)
        self.assertNotIn("cryptography", proc.stderr)

    def test_installer_script_is_executable_stdlib_bootstrap(self) -> None:
        path = ROOT / "install-control-runtime"
        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o755)
        text = path.read_text()
        self.assertIn("from fleet_control.runtime import main", text)
        self.assertNotIn("reexec_managed_python", text)
        self.assertNotIn("import cryptography", text)


if __name__ == "__main__":
    unittest.main()
