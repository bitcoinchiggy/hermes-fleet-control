"""Safe JSON and timestamp helpers."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fleet_control.support.redact import (
    NSEC_RE,
    SECRET_KEYS,
    SK_KEY_RE,
    UnsafeJsonError,
    dump_safe_json,
    utc_rfc3339,
)


class RedactTests(unittest.TestCase):
    def test_accepts_an_ordinary_document(self):
        text = dump_safe_json({"kind": "Worker", "name": "operator", "ok": True})
        self.assertEqual(text, '{"kind":"Worker","name":"operator","ok":true}')

    def test_rejects_secret_fields_and_shaped_text(self):
        with self.assertRaises(UnsafeJsonError):
            dump_safe_json({"password": "nope"})
        with self.assertRaises(UnsafeJsonError):
            dump_safe_json({"nested": {"buzz_private_key": "nope"}})
        with self.assertRaises(UnsafeJsonError):
            dump_safe_json({"note": "sk-testtoken"})
        with self.assertRaises(UnsafeJsonError):
            dump_safe_json({"note": "nsec1qqqqqqqq"})
        with self.assertRaises(UnsafeJsonError):
            dump_safe_json({"buzz_ready": True})
        self.assertIn("password", SECRET_KEYS)
        self.assertIsNotNone(SK_KEY_RE.search("sk-testtoken"))
        self.assertIsNotNone(NSEC_RE.search("nsec1qqqqqqqq"))

    def test_utc_rfc3339_shape(self):
        self.assertIsNotNone(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", utc_rfc3339()))


if __name__ == "__main__":
    unittest.main()
