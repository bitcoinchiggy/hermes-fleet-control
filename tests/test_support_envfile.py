"""Env assignment parsing. Quotes stay literal and nothing is written."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fleet_control.support.envfile import EnvFileError, env_assignment_values


class EnvFileTests(unittest.TestCase):
    def test_preserves_order_duplicates_and_export(self):
        raw = b"OTHER=skip\nFOO=one\n  export FOO=two\nFOO=three\n"
        self.assertEqual(env_assignment_values(raw, "FOO"), ["one", "two", "three"])
        self.assertEqual(env_assignment_values(raw, "OTHER"), ["skip"])
        self.assertEqual(env_assignment_values(raw, "MISSING"), [])

    def test_does_not_strip_quotes(self):
        raw = b"FOO='quoted'\nFOO=\"double\"\n"
        self.assertEqual(env_assignment_values(raw, "FOO"), ["'quoted'", '"double"'])

    def test_rejects_bad_input(self):
        with self.assertRaises(EnvFileError):
            env_assignment_values(b"FOO=1\n", "foo")
        with self.assertRaises(EnvFileError):
            env_assignment_values("FOO=1\n", "FOO")  # type: ignore[arg-type]
        with self.assertRaises(EnvFileError):
            env_assignment_values(b"\xff", "FOO")
        with self.assertRaises(EnvFileError):
            env_assignment_values(b"FOO=1\x00\n", "FOO")


if __name__ == "__main__":
    unittest.main()
