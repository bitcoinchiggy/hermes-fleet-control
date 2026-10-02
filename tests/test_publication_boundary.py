"""The public tree must not carry private Fleet internals."""

from __future__ import annotations

import importlib
import re
import stat
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
# Needles are concatenated so this file can be scanned too.
FORBIDDEN = (
    "fleet_" + "provisioner",
    "identity_" + "tree",
    "chiggy" + ".io",
    "10." + "21.",
    "/etc/" + "hermes-fleet",
    "xp" + "rv",
    "bip" + "85",
    "8369" + "6968",
    "guest_" + "exec",
    "guest-" + "exec",
    "secret_" + "input",
    "atomic_" + "replace_env",
    "update_" + "env_secret",
    "Worker" + "Declaration",
    "Git" + "Snapshot",
    "proxm" + "ox",
    "qe" + "mu",
)
RUNTIME_MODULES = (
    "fleet_control",
    "fleet_control.authorize",
    "fleet_control.buzz_exec",
    "fleet_control.config",
    "fleet_control.delegate",
    "fleet_control.delegation_reply",
    "fleet_control.ensure",
    "fleet_control.errors",
    "fleet_control.hermes_authz",
    "fleet_control.http",
    "fleet_control.identity",
    "fleet_control.inbound_allow",
    "fleet_control.journal",
    "fleet_control.output",
    "fleet_control.runtime",
    "fleet_control.status",
    "fleet_control.support.bech32",
    "fleet_control.support.envfile",
    "fleet_control.support.names",
    "fleet_control.support.nostr_codec",
    "fleet_control.support.profile_env",
    "fleet_control.support.redact",
)


def _tracked_files() -> list[Path]:
    found: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        found.append(path)
    return found


def _contains(text: str, needle: str) -> bool:
    """Match a whole identifier, or a literal when the needle is not one."""
    if re.fullmatch(r"[a-z0-9_]+", needle):
        return re.search(rf"\b{re.escape(needle)}\b", text) is not None
    return needle in text


class PublicationBoundaryTests(unittest.TestCase):
    def test_tree_omits_private_fleet_material(self):
        hits: list[str] = []
        for path in _tracked_files():
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for needle in FORBIDDEN:
                if _contains(text, needle.lower()):
                    hits.append(f"{path.relative_to(ROOT)}:{needle}")
        self.assertEqual(hits, [])

    def test_runtime_imports_do_not_load_private_packages(self):
        for name in RUNTIME_MODULES:
            importlib.import_module(name)
        loaded = set(sys.modules)
        private_pkg = "fleet_" + "provisioner"
        identity_pkg = "identity_" + "tree"
        self.assertFalse(any(name == private_pkg or name.startswith(private_pkg + ".") for name in loaded))
        self.assertFalse(any(name == identity_pkg or name.startswith(identity_pkg + ".") for name in loaded))

    def test_helpers_insert_only_the_clone_root(self):
        for name in ("fleet-status", "fleet-ensure", "fleet-delegate", "fleet-allow-inbound", "install-control-runtime"):
            path = ROOT / name
            text = path.read_text()
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(mode, 0o755, name)
            self.assertEqual(text.count("sys.path.insert"), 1, name)
            self.assertIn("Path(__file__).resolve().parent", text)
            self.assertNotIn(".parent.parent", text)
            self.assertNotIn("fleet_" + "provisioner", text)


if __name__ == "__main__":
    unittest.main()
