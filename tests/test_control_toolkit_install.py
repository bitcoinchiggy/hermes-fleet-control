"""Sandbox checks for the permanent Control toolkit installer. No host contact."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "docs" / "deploy" / "install-control-toolkit.sh"
MANIFEST = ROOT / "docs" / "deploy" / "control-toolkit-manifest.sha256"
SOURCE = "30e64213d353a487fb84d84443449461b7a76944"
NAMES = (
    "c08cb1e-deploy-plan.md",
    "c08cb1e-guest-node-witness.sh",
    "c08cb1e-preflight.sh",
    "c08cb1e-provisioner-witness.sh",
    "c08cb1e_material.py",
)
MODES = {
    "c08cb1e-deploy-plan.md": "644",
    "c08cb1e-guest-node-witness.sh": "755",
    "c08cb1e-preflight.sh": "755",
    "c08cb1e-provisioner-witness.sh": "755",
    "c08cb1e_material.py": "755",
}


def _manifest_hashes() -> dict[str, str]:
    found: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        found[name] = digest
    return found


def _git_bytes(name: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{SOURCE}:docs/deploy/{name}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def _stage_files(staging: Path, mutate: str | None = None) -> None:
    staging.mkdir(mode=0o700, exist_ok=True)
    os.chmod(staging, 0o700)
    for name in NAMES:
        target = staging / name
        target.write_bytes(_git_bytes(name))
        os.chmod(target, 0o644)
    if mutate is not None:
        path = staging / mutate
        path.write_bytes(path.read_bytes() + b"\n")


def _run(inner: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["unshare", "--user", "--mount", "--map-root-user", "bash", "-c", inner],
        capture_output=True,
        text=True,
        check=False,
    )


def _install_script(staging: Path, root: Path, extra: str = "") -> str:
    opt = root / "opt"
    return textwrap.dedent(
        f"""\
        set -euo pipefail
        mkdir -p {opt}
        chmod 755 {opt}
        bash {INSTALLER} --staging {staging} --dest {opt}/hermes-control-deploy --walk-root {root} {extra}
        """
    )


class ControlToolkitInstallTests(unittest.TestCase):
    def test_manifest_matches_approved_revision_bytes(self):
        hashes = _manifest_hashes()
        self.assertEqual(list(hashes), list(NAMES))
        self.assertEqual(
            hashes["c08cb1e-preflight.sh"],
            "78634901d4e7c3335adf8f5c231503ddbc9322b13313178b0088f971e863cff7",
        )
        self.assertEqual(
            hashes["c08cb1e_material.py"],
            "2f54b671e58120178bfa7c84ee2d3d86c0e2df236911866b246450c9abaad60d",
        )
        for name, digest in hashes.items():
            self.assertEqual(hashlib.sha256(_git_bytes(name)).hexdigest(), digest)
            worktree = ROOT / "docs" / "deploy" / name
            self.assertEqual(hashlib.sha256(worktree.read_bytes()).hexdigest(), digest)

    def test_clean_install_is_root_owned_and_does_not_execute_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            _stage_files(staging)
            marker = root / "executed"
            planted = staging / "json.py"
            planted.write_text(
                f"open({str(marker)!r}, 'w').write('ran')\n",
                encoding="utf-8",
            )
            os.chmod(staging, 0o700)
            completed = _run(_install_script(staging, root))
            self.assertNotEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("STOP:", completed.stderr)
            self.assertNotIn("toolkit=ready", completed.stdout)
            self.assertFalse(marker.exists())
            shutil.rmtree(staging)
            _stage_files(staging)
            sibling = root / "opt" / "hermes-fleet-control"
            sibling.mkdir(parents=True)
            (sibling / "keep").write_text("gateway", encoding="utf-8")
            before = (sibling / "keep").read_bytes()
            completed = _run(_install_script(staging, root))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("toolkit=ready", completed.stdout)
            self.assertIn("toolkit-action=created", completed.stdout)
            self.assertIn("toolkit-class=state-changing", completed.stdout)
            self.assertNotIn("preflight=", completed.stdout)
            deploy = root / "opt" / "hermes-control-deploy" / "docs" / "deploy"
            self.assertEqual(sorted(path.name for path in deploy.iterdir()), list(NAMES))
            self.assertEqual((sibling / "keep").read_bytes(), before)
            self.assertFalse(Path("/opt/hermes-control-deploy").exists())
            checked = _run(
                textwrap.dedent(
                    f"""\
                    set -euo pipefail
                    stat -c '%U:%G %a %n' {deploy}/*
                    """
                )
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            for name, mode in MODES.items():
                self.assertIn(f"root:root {mode} {deploy / name}", checked.stdout)
                if name.endswith(".md"):
                    self.assertFalse(os.access(deploy / name, os.X_OK))
                else:
                    self.assertTrue(os.access(deploy / name, os.X_OK))

    def test_repeat_install_does_not_replace_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            _stage_files(staging)
            completed = _run(
                _install_script(staging, root)
                + textwrap.dedent(
                    f"""\
                    deploy={root}/opt/hermes-control-deploy/docs/deploy
                    stat -c '%i' "$deploy/c08cb1e-preflight.sh" "$deploy/c08cb1e_material.py"
                    bash {INSTALLER} --staging {staging} --dest {root}/opt/hermes-control-deploy --walk-root {root}
                    echo second-ok
                    stat -c '%i' "$deploy/c08cb1e-preflight.sh" "$deploy/c08cb1e_material.py"
                    """
                )
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("toolkit-action=unchanged", completed.stdout)
            inodes = [line for line in completed.stdout.splitlines() if line.isdigit()]
            self.assertEqual(inodes[:2], inodes[2:])

    def test_wrong_staging_hash_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            _stage_files(staging, mutate="c08cb1e-preflight.sh")
            completed = _run(_install_script(staging, root))
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("staging hash mismatch", completed.stderr)
            self.assertFalse((root / "opt" / "hermes-control-deploy").exists())

    def test_unexpected_destination_file_is_left_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            _stage_files(staging)
            deploy = root / "opt" / "hermes-control-deploy" / "docs" / "deploy"
            deploy.mkdir(parents=True)
            os.chmod(root / "opt", 0o755)
            for path in (
                root / "opt" / "hermes-control-deploy",
                root / "opt" / "hermes-control-deploy" / "docs",
                deploy,
            ):
                os.chmod(path, 0o755)
            extra = deploy / "notes.txt"
            extra.write_text("leave-me", encoding="utf-8")
            completed = _run(
                f"bash {INSTALLER} --staging {staging} --dest {root}/opt/hermes-control-deploy --walk-root {root}"
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("unexpected file", completed.stderr)
            self.assertEqual(extra.read_text(encoding="utf-8"), "leave-me")
            self.assertEqual([path.name for path in deploy.iterdir()], ["notes.txt"])

    def test_symlink_destination_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            _stage_files(staging)
            elsewhere = root / "elsewhere"
            elsewhere.mkdir()
            (elsewhere / "kept").write_text("untouched", encoding="utf-8")
            os.chmod(root / "opt", 0o755) if (root / "opt").exists() else None
            (root / "opt").mkdir(mode=0o755, exist_ok=True)
            os.chmod(root / "opt", 0o755)
            link = root / "opt" / "hermes-control-deploy"
            link.symlink_to(elsewhere, target_is_directory=True)
            completed = _run(
                f"bash {INSTALLER} --staging {staging} --dest {link} --walk-root {root}"
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("symlink", completed.stderr)
            self.assertTrue(link.is_symlink())
            self.assertEqual((elsewhere / "kept").read_text(encoding="utf-8"), "untouched")
            self.assertFalse((elsewhere / "docs").exists())

    def test_symlinked_toolkit_file_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            _stage_files(staging)
            deploy = root / "opt" / "hermes-control-deploy" / "docs" / "deploy"
            deploy.mkdir(parents=True)
            target = root / "outside-target"
            target.write_text("outside", encoding="utf-8")
            for path in (
                root / "opt",
                root / "opt" / "hermes-control-deploy",
                root / "opt" / "hermes-control-deploy" / "docs",
                deploy,
            ):
                os.chmod(path, 0o755)
            planted = deploy / "c08cb1e-preflight.sh"
            planted.symlink_to(target)
            completed = _run(
                f"bash {INSTALLER} --staging {staging} --dest {root}/opt/hermes-control-deploy --walk-root {root}"
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("symlink", completed.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), "outside")
            self.assertTrue(planted.is_symlink())

    def test_unsafe_parent_permissions_are_not_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            _stage_files(staging)
            opt = root / "opt"
            opt.mkdir()
            os.chmod(opt, 0o777)
            completed = _run(
                f"bash {INSTALLER} --staging {staging} --dest {opt}/hermes-control-deploy --walk-root {root}"
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("writable", completed.stderr)
            self.assertEqual(stat.S_IMODE(opt.stat().st_mode), 0o777)
            self.assertFalse((opt / "hermes-control-deploy").exists())

    def test_partial_install_completes_without_claiming_ready_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            _stage_files(staging)
            deploy = root / "opt" / "hermes-control-deploy" / "docs" / "deploy"
            deploy.mkdir(parents=True)
            for path in (
                root / "opt",
                root / "opt" / "hermes-control-deploy",
                root / "opt" / "hermes-control-deploy" / "docs",
                deploy,
            ):
                os.chmod(path, 0o755)
            for name in ("c08cb1e-deploy-plan.md", "c08cb1e-preflight.sh"):
                shutil.copy2(staging / name, deploy / name)
                os.chmod(deploy / name, 0o755 if name.endswith(".sh") else 0o644)
            completed = _run(
                f"bash {INSTALLER} --staging {staging} --dest {root}/opt/hermes-control-deploy --walk-root {root}"
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("toolkit-action=completed", completed.stdout)
            ready_at = completed.stdout.index("toolkit=ready")
            self.assertLess(ready_at, completed.stdout.index("toolkit-file=c08cb1e_material.py"))
            self.assertEqual(sorted(path.name for path in deploy.iterdir()), list(NAMES))

    def test_mode_repair_keeps_verified_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            _stage_files(staging)
            first = _run(_install_script(staging, root))
            self.assertEqual(first.returncode, 0, first.stderr)
            deploy = root / "opt" / "hermes-control-deploy" / "docs" / "deploy"
            preflight = deploy / "c08cb1e-preflight.sh"
            before = preflight.read_bytes()
            os.chmod(preflight, 0o700)
            second = _run(
                f"bash {INSTALLER} --staging {staging} --dest {root}/opt/hermes-control-deploy --walk-root {root}"
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("toolkit-action=modes-repaired", second.stdout)
            self.assertEqual(preflight.read_bytes(), before)
            self.assertEqual(stat.S_IMODE(preflight.stat().st_mode), 0o755)

    def test_host_and_user_checks_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            _stage_files(staging)
            stub = root / "bin"
            stub.mkdir()
            (stub / "hostname").write_text("#!/bin/sh\necho other-host\n", encoding="utf-8")
            (stub / "hostnamectl").write_text("#!/bin/sh\necho other-host\n", encoding="utf-8")
            os.chmod(stub / "hostname", 0o755)
            os.chmod(stub / "hostnamectl", 0o755)
            host = _run(
                f"export PATH={stub}:$PATH\n"
                + _install_script(staging, root, extra="--require-host hermes-control")
            )
            self.assertNotEqual(host.returncode, 0)
            self.assertIn("approved FQDN", host.stderr)
            self.assertNotIn("toolkit=ready", host.stdout)
            user = _run(
                _install_script(staging, root, extra="--require-user hermes")
            )
            self.assertNotEqual(user.returncode, 0)
            self.assertIn("invoking user", user.stderr)
            self.assertFalse((root / "opt" / "hermes-control-deploy").exists())

    def test_refuses_production_dest_override_without_a_private_walk_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            _stage_files(staging)
            completed = _run(
                f"bash {INSTALLER} --staging {staging} --dest /tmp/not-the-toolkit"
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("refusing a destination", completed.stderr)
            self.assertFalse(Path("/tmp/not-the-toolkit").exists())


if __name__ == "__main__":
    unittest.main()
