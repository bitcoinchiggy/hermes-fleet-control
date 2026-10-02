"""Read-only profile .env access. No writer and no symlink follow."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fleet_control.support.profile_env import (
    ERR_INVALID_DESTINATION,
    ERR_PROFILE_NOT_FOUND,
    ERR_UNSAFE_ENV_TARGET,
    ProfileEnvError,
    open_named_profile,
    validate_profile_name,
)


class ProfileEnvTests(unittest.TestCase):
    def test_profile_name_rejects_paths(self):
        self.assertEqual(validate_profile_name("control"), "control")
        self.assertEqual(validate_profile_name("a..b"), "a..b")
        for name in ("", ".", "..", "/tmp", "a/b", "a\\b", "has space", "-no", None, 1):
            with self.subTest(name=name):
                with self.assertRaises(ProfileEnvError) as caught:
                    validate_profile_name(name)
                self.assertEqual(caught.exception.public_message, ERR_INVALID_DESTINATION)

    def test_reads_regular_env_and_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "control"
            profile.mkdir()
            payload = b"BUZZ_RELAY_URL=wss://buzz.example/\n"
            (profile / ".env").write_bytes(payload)
            os.chmod(profile / ".env", 0o600)
            with open_named_profile("control", profiles_root=root) as opened:
                self.assertEqual(opened.read_env(), payload)
            empty = root / "other"
            empty.mkdir()
            with open_named_profile("other", profiles_root=root) as opened:
                self.assertEqual(opened.read_env(), b"")

    def test_refuses_symlink_profile_and_symlink_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real"
            real.mkdir()
            (real / ".env").write_bytes(b"A=1\n")
            (root / "link").symlink_to(real, target_is_directory=True)
            with self.assertRaises(ProfileEnvError) as caught:
                open_named_profile("link", profiles_root=root)
            self.assertEqual(caught.exception.public_message, ERR_UNSAFE_ENV_TARGET)

            profile = root / "control"
            profile.mkdir()
            outside = root / "outside"
            outside.write_bytes(b"SECRET=1\n")
            (profile / ".env").symlink_to(outside)
            with self.assertRaises(ProfileEnvError) as caught:
                with open_named_profile("control", profiles_root=root) as opened:
                    opened.read_env()
            self.assertEqual(caught.exception.public_message, ERR_UNSAFE_ENV_TARGET)
            self.assertNotIn(b"SECRET", caught.exception.public_message.encode())

    def test_missing_profile_is_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ProfileEnvError) as caught:
                open_named_profile("missing", profiles_root=tmp)
            self.assertEqual(caught.exception.public_message, ERR_PROFILE_NOT_FOUND)

    def test_delegation_modules_do_not_replace_the_profile(self):
        root = Path(__file__).resolve().parents[1]
        for rel in (
            "fleet_control/delegate.py",
            "fleet_control/identity.py",
            "fleet_control/status.py",
            "fleet_control/ensure.py",
        ):
            text = (root / rel).read_text()
            self.assertNotIn("atomic_" + "replace_env", text, rel)

    def test_module_writer_is_the_pinned_replace(self):
        source = (
            Path(__file__).resolve().parents[1] / "fleet_control" / "support" / "profile_env.py"
        ).read_text()
        self.assertEqual(source.count("os.replace("), 1)
        self.assertIn("O_NOFOLLOW", source)


if __name__ == "__main__":
    unittest.main()
