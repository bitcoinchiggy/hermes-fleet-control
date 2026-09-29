"""NIP-19 ``nsec`` / ``npub`` and x-only secp256k1 public keys.

A 32-byte scalar is validated and its public key is derived. This module
does not accept an extended private key, a seed, or a derivation path.
"""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric import ec

from fleet_control.support import bech32

# secp256k1 group order. A scalar is valid only in ``[1, n-1]``.
SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
HRP_NSEC = "nsec"
HRP_NPUB = "npub"


class InvalidNostrKeyError(ValueError):
    """Key material is not a valid NIP-19 secret or public key."""


def _require_32(data: bytes, what: str) -> bytes:
    if not isinstance(data, (bytes, bytearray)):
        raise InvalidNostrKeyError(f"{what} must be bytes")
    raw = bytes(data)
    if len(raw) != 32:
        raise InvalidNostrKeyError(f"{what} must be exactly 32 bytes")
    return raw


def validate_nostr_scalar(data: bytes) -> bool:
    """True iff 32 bytes interpret as a secp256k1 scalar in ``[1, n-1]``."""
    if len(data) != 32:
        return False
    value = int.from_bytes(data, "big")
    return 1 <= value < SECP256K1_N


def _scalar(data: bytes) -> int:
    value = int.from_bytes(data, "big")
    if value == 0 or value >= SECP256K1_N:
        raise InvalidNostrKeyError("secp256k1 scalar is not in [1, n-1]")
    return value


def derive_nostr_private_key(entropy: bytes) -> bytes:
    """Validate already-derived 32-byte Nostr private material.

    Bytes are a big-endian integer. No modulo reduction. Invalid scalars
    raise; they do not wrap.
    """
    raw = _require_32(entropy, "Nostr secret")
    _scalar(raw)
    return raw


def derive_nostr_public_key(private_key: bytes) -> bytes:
    """32-byte x-only Nostr public key (BIP-340 / NIP-01), not 33-byte SEC."""
    raw = _require_32(private_key, "private key")
    secret = _scalar(raw)
    key = ec.derive_private_key(secret, ec.SECP256K1())
    x = key.public_key().public_numbers().x
    return x.to_bytes(32, "big")


def encode_nsec(private_key: bytes) -> str:
    raw = derive_nostr_private_key(private_key)
    data = bech32.convertbits(raw, 8, 5)
    return bech32.encode(HRP_NSEC, data)


def encode_npub(public_key: bytes) -> str:
    raw = _require_32(public_key, "public key")
    data = bech32.convertbits(raw, 8, 5)
    return bech32.encode(HRP_NPUB, data)


def decode_nsec(text: str) -> bytes:
    if not isinstance(text, str):
        raise InvalidNostrKeyError("nsec must be a string")
    try:
        hrp, data = bech32.decode(text)
        payload = bytes(bech32.convertbits(data, 5, 8, pad=False))
    except ValueError as exc:
        raise InvalidNostrKeyError("malformed nsec") from exc
    if hrp != HRP_NSEC:
        raise InvalidNostrKeyError("bech32 HRP is not nsec")
    return derive_nostr_private_key(payload)


def decode_npub(text: str) -> bytes:
    if not isinstance(text, str):
        raise InvalidNostrKeyError("npub must be a string")
    try:
        hrp, data = bech32.decode(text)
        payload = bytes(bech32.convertbits(data, 5, 8, pad=False))
    except ValueError as exc:
        raise InvalidNostrKeyError("malformed npub") from exc
    if hrp != HRP_NPUB:
        raise InvalidNostrKeyError("bech32 HRP is not npub")
    return _require_32(payload, "npub payload")
