"""NIP-19 coding and x-only public keys. No extended-key derivation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fleet_control.support.nostr_codec import (
    SECP256K1_N,
    InvalidNostrKeyError,
    decode_npub,
    decode_nsec,
    derive_nostr_public_key,
    encode_npub,
    encode_nsec,
    validate_nostr_scalar,
)

# x-only public key of scalar 1, checked against the previous codec.
SCALAR_ONE = bytes([1]) + bytes(31)
SCALAR_ONE_X = "8c28a97bf8298bc0d23d8c749452a32e694b65e30a9472a3954ab30fe5324caa"


class NostrCodecTests(unittest.TestCase):
    def test_scalar_bounds(self):
        self.assertTrue(validate_nostr_scalar(SCALAR_ONE))
        self.assertTrue(validate_nostr_scalar((SECP256K1_N - 1).to_bytes(32, "big")))
        self.assertFalse(validate_nostr_scalar(bytes(32)))
        self.assertFalse(validate_nostr_scalar(SECP256K1_N.to_bytes(32, "big")))
        self.assertFalse(validate_nostr_scalar(b"\x01"))

    def test_roundtrip_matches_scalar_one_public_key(self):
        public = derive_nostr_public_key(SCALAR_ONE)
        self.assertEqual(public.hex(), SCALAR_ONE_X)
        self.assertEqual(len(public), 32)
        self.assertEqual(decode_nsec(encode_nsec(SCALAR_ONE)), SCALAR_ONE)
        self.assertEqual(decode_npub(encode_npub(public)), public)

    def test_rejects_wrong_hrp_and_malformed_text(self):
        public = derive_nostr_public_key(SCALAR_ONE)
        with self.assertRaises(InvalidNostrKeyError):
            decode_nsec(encode_npub(public))
        with self.assertRaises(InvalidNostrKeyError):
            decode_npub(encode_nsec(SCALAR_ONE))
        with self.assertRaises(InvalidNostrKeyError):
            decode_nsec("nsec1qqqqqqqq")
        with self.assertRaises(InvalidNostrKeyError):
            decode_nsec(123)  # type: ignore[arg-type]
        with self.assertRaises(InvalidNostrKeyError):
            encode_nsec(bytes(32))


if __name__ == "__main__":
    unittest.main()
