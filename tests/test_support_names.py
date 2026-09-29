"""Worker name checks. No declaration schema."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fleet_control.support.names import NAME_RE, InvalidNameError, validate_worker_name


class NameTests(unittest.TestCase):
    def test_accepts_a_single_component(self):
        for name in ("a", "operator", "worker_1", "a.b", "a-b"):
            self.assertEqual(validate_worker_name(name), name)
            self.assertTrue(NAME_RE.fullmatch(name))

    def test_rejects_paths_and_empty(self):
        for name in ("", ".", "..", "../etc", "/tmp", "a/b", "Bad Name", "-lead"):
            with self.subTest(name=name):
                with self.assertRaises(InvalidNameError):
                    validate_worker_name(name)

    def test_rejects_overlong_names(self):
        with self.assertRaises(InvalidNameError):
            validate_worker_name("a" * 64)
        self.assertEqual(validate_worker_name("a" * 63), "a" * 63)


if __name__ == "__main__":
    unittest.main()
