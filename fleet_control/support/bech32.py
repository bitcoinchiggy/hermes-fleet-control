"""BIP-173 bech32 (not bech32m). Used by NIP-19 nsec/npub."""

from __future__ import annotations

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
GENERATOR = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


def _polymod(values: list[int]) -> int:
    chk = 1
    for value in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ value
        for i in range(5):
            if (top >> i) & 1:
                chk ^= GENERATOR[i]
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _create_checksum(hrp: str, data: list[int]) -> list[int]:
    values = _hrp_expand(hrp) + data
    polymod = _polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def convertbits(data: bytes | list[int], from_bits: int, to_bits: int, pad: bool = True) -> list[int]:
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << to_bits) - 1
    max_acc = (1 << (from_bits + to_bits - 1)) - 1
    for value in data:
        if value < 0 or value >> from_bits:
            raise ValueError("invalid convertbits value")
        acc = ((acc << from_bits) | value) & max_acc
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & maxv):
        raise ValueError("invalid convertbits padding")
    return ret


def encode(hrp: str, data: list[int]) -> str:
    combined = data + _create_checksum(hrp, data)
    return hrp + "1" + "".join(CHARSET[d] for d in combined)


def decode(bech: str) -> tuple[str, list[int]]:
    if any(ord(x) < 33 or ord(x) > 126 for x in bech):
        raise ValueError("invalid bech32 character")
    if bech.lower() != bech and bech.upper() != bech:
        raise ValueError("mixed-case bech32")
    bech = bech.lower()
    pos = bech.rfind("1")
    if pos < 1 or pos + 7 > len(bech):
        raise ValueError("invalid bech32 separator")
    hrp = bech[:pos]
    data = []
    for ch in bech[pos + 1 :]:
        idx = CHARSET.find(ch)
        if idx == -1:
            raise ValueError("invalid bech32 charset")
        data.append(idx)
    if _polymod(_hrp_expand(hrp) + data) != 1:
        raise ValueError("invalid bech32 checksum")
    return hrp, data[:-6]
