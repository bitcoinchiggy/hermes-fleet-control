"""Apply Control's inbound Buzz allowlist on the active profile.

Reads the selected profile ``.env`` and appends verified ``operator`` and
``researcher`` public keys to the keys already authorized there. Extra
human keys stay. ``allow_all_users`` stays false. ``BUZZ_PRIVATE_KEY`` is
preserved and is not part of the public result.

This command does not import a worker key-derivation package, does not
read worker private keys, does not accept provisioner administration
credentials, and does not use a guest agent. It writes only the one
profile bound to the active gateway unit. A second run with the same
keys does not change the file.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from fleet_control.config import FORBIDDEN_ENV_KEYS, refuse_forbidden_environment
from fleet_control.support.envfile import EnvFileError, env_assignment_values
from fleet_control.support.nostr_codec import InvalidNostrKeyError, decode_npub
from fleet_control.support.profile_env import (
    HERMES_PROFILES_DIR,
    ProfileEnvError,
    open_named_profile,
    validate_profile_name,
)

PUBHEX_RE = re.compile(r"^[0-9a-f]{64}$")
INBOUND_WORKERS = ("operator", "researcher")
LEGACY_GENERIC_UNIT = "hermes-gateway.service"
PROFILE_KEY = "FLEET_CONTROL_HERMES_PROFILE"
PROFILES_ROOT_KEY = "FLEET_CONTROL_PROFILES_ROOT"
_UNIT_RE = re.compile(r"^hermes-gateway-(?P<profile>.+)\.service\Z")
_SECRET_RE = re.compile("nsec1|sk-|" + "xp" + "rv", re.IGNORECASE)
_SECRET_KEYS = frozenset(
    {
        "buzz_private_key",
        "private_key",
        "nsec",
        "secret",
        "litellm_key_token",
    }
)
_ALLOWED_USERS = "BUZZ_ALLOWED_USERS"
_ALLOW_ALL = "BUZZ_ALLOW_ALL_USERS"
_PRIVATE_KEY = "BUZZ_PRIVATE_KEY"
_ASSIGNMENT_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class InboundAllowError(ValueError):
    """Secret-free failure. The message is safe to print."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.public_message = message

    def __repr__(self) -> str:
        return f"InboundAllowError({self.public_message!r})"


def active_gateway_profile(units: Sequence[object]) -> str:
    """Return the single active ``hermes-gateway-<profile>.service`` profile.

    The generic unit does not count. Zero or several profile units fail
    closed. No profile name is assumed.
    """
    profiles: list[str] = []
    for unit in units:
        if not isinstance(unit, str) or not unit or unit != unit.strip():
            raise InboundAllowError("invalid gateway unit")
        if unit == LEGACY_GENERIC_UNIT:
            continue
        match = _UNIT_RE.fullmatch(unit)
        if match is None:
            raise InboundAllowError("invalid gateway unit")
        try:
            profile = validate_profile_name(match.group("profile"))
        except ProfileEnvError:
            raise InboundAllowError("invalid gateway unit") from None
        if f"hermes-gateway-{profile}.service" != unit:
            raise InboundAllowError("invalid gateway unit")
        profiles.append(profile)
    if len(profiles) != 1:
        raise InboundAllowError("control gateway profile is not singular")
    return profiles[0]


def bind_control_profile(units: Sequence[object], configured: object) -> str:
    """Require the configured profile to be the one active gateway unit."""
    active = active_gateway_profile(units)
    if not isinstance(configured, str) or not configured or configured != configured.strip():
        raise InboundAllowError("FLEET_CONTROL_HERMES_PROFILE is not set")
    try:
        name = validate_profile_name(configured)
    except ProfileEnvError:
        raise InboundAllowError("FLEET_CONTROL_HERMES_PROFILE is not set") from None
    if name != active:
        raise InboundAllowError("FLEET_CONTROL_HERMES_PROFILE does not match the active gateway")
    return name


def _unquote(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _public_hex(value: object, what: str) -> str:
    if isinstance(value, bool) or not isinstance(value, str):
        raise InboundAllowError(f"invalid {what}")
    text = value.strip().lower()
    if _SECRET_RE.search(text) or any(ch in text for ch in ("\n", "\r", "\x00")):
        raise InboundAllowError("refusing secret material")
    if not PUBHEX_RE.fullmatch(text):
        raise InboundAllowError(f"invalid {what}")
    return text


def _refuse_document_secrets(value: object) -> None:
    if isinstance(value, str):
        if _SECRET_RE.search(value) or _PRIVATE_KEY in value:
            raise InboundAllowError("refusing secret material")
        return
    if isinstance(value, bool) or value is None or isinstance(value, int | float):
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise InboundAllowError("invalid worker document")
            lowered = key.lower()
            if lowered in _SECRET_KEYS or "private" in lowered or lowered.endswith("_token"):
                raise InboundAllowError("refusing secret material")
            _refuse_document_secrets(item)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _refuse_document_secrets(item)
        return
    raise InboundAllowError("invalid worker document")


def _field(document: Mapping[str, Any], key: str) -> object | None:
    observed = document.get("observed")
    nested = None
    if isinstance(observed, Mapping) and key in observed:
        nested = observed.get(key)
    top = document.get(key) if key in document else None
    if nested is None and top is None:
        return None
    if nested is not None and top is not None and nested != top:
        raise InboundAllowError(f"invalid {key}")
    return nested if nested is not None else top


def verified_worker_hexes(documents: Sequence[object]) -> tuple[str, str]:
    """Public hex for operator, then researcher, after ``npub`` matches the hex."""
    found: dict[str, str] = {}
    for document in documents:
        if not isinstance(document, Mapping):
            raise InboundAllowError("invalid worker document")
        _refuse_document_secrets(document)
        name = document.get("name")
        if name not in INBOUND_WORKERS:
            raise InboundAllowError("worker is not an inbound delegation target")
        if name in found:
            raise InboundAllowError("duplicate worker")
        hex_key = _field(document, "buzz_public_key_hex")
        npub = _field(document, "buzz_npub")
        if not isinstance(npub, str) or not npub.startswith("npub1"):
            raise InboundAllowError("worker public key is not verified")
        try:
            decoded = decode_npub(npub).hex()
        except (InvalidNostrKeyError, ValueError):
            raise InboundAllowError("worker public key is not verified") from None
        checked = _public_hex(hex_key, "buzz_public_key_hex")
        if decoded != checked:
            raise InboundAllowError("worker public key is not verified")
        found[str(name)] = checked
    if set(found) != set(INBOUND_WORKERS):
        raise InboundAllowError("operator and researcher public keys are required")
    ordered = (found["operator"], found["researcher"])
    if ordered[0] == ordered[1]:
        raise InboundAllowError("worker public keys are not distinct")
    return ordered


def current_allowed_users(raw: bytes) -> tuple[str, ...]:
    """Public keys already authorized on this profile. Does not return secrets."""
    try:
        allow_values = env_assignment_values(raw, _ALLOW_ALL)
        user_values = env_assignment_values(raw, _ALLOWED_USERS)
    except EnvFileError:
        raise InboundAllowError("control allowlist is unusable") from None
    if len(allow_values) != 1 or _unquote(allow_values[0]).lower() != "false":
        raise InboundAllowError("allow_all_users is not a control authorization")
    if len(user_values) != 1:
        raise InboundAllowError("control allowlist is unusable")
    text = _unquote(user_values[0])
    if _SECRET_RE.search(text):
        raise InboundAllowError("refusing secret material")
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in text.split(","):
        token = item.strip().lower()
        if not token:
            continue
        hex_key = _public_hex(token, "allowed_users")
        if hex_key in seen:
            continue
        seen.add(hex_key)
        cleaned.append(hex_key)
    if not cleaned:
        raise InboundAllowError("control allowlist is unusable")
    return tuple(cleaned)


def merge_allowed_users(existing: Sequence[str], worker_hexes: Sequence[str]) -> tuple[str, ...]:
    """Keep every current human key, then append worker keys that are absent."""
    merged: list[str] = []
    seen: set[str] = set()
    for item in existing:
        hex_key = _public_hex(item, "allowed_users")
        if hex_key in seen:
            continue
        seen.add(hex_key)
        merged.append(hex_key)
    if not merged:
        raise InboundAllowError("control allowlist is unusable")
    for item in worker_hexes:
        hex_key = _public_hex(item, "worker public key")
        if hex_key in seen:
            continue
        seen.add(hex_key)
        merged.append(hex_key)
    return tuple(merged)


def _private_values(raw: bytes) -> list[str]:
    try:
        return env_assignment_values(raw, _PRIVATE_KEY)
    except EnvFileError:
        raise InboundAllowError("control profile is unusable") from None


def _replace_allowed_users(existing: bytes, users: str) -> bytes:
    if not _ASSIGNMENT_RE.fullmatch(_ALLOWED_USERS):
        raise InboundAllowError("control allowlist is unusable")
    if not users or any(ch in users for ch in ("\n", "\r", "\x00")):
        raise InboundAllowError("control allowlist is unusable")
    if _SECRET_RE.search(users) or _PRIVATE_KEY in users:
        raise InboundAllowError("refusing secret material")
    try:
        text = bytes(existing).decode("utf-8")
    except UnicodeDecodeError:
        raise InboundAllowError("control profile is unusable") from None
    assignment = f"{_ALLOWED_USERS}={users}"
    match = re.compile(rf"^(?:export\s+)?{re.escape(_ALLOWED_USERS)}\s*=")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    seen = False
    for line in lines:
        body = line.splitlines()[0] if line else line
        if match.match(body.lstrip()):
            if seen:
                continue
            if line.endswith("\r\n"):
                ending = "\r\n"
            elif line.endswith("\n"):
                ending = "\n"
            else:
                ending = ""
            out.append(assignment + ending)
            seen = True
            continue
        out.append(line)
    if not seen:
        if out and not out[-1].endswith(("\n", "\r")):
            out[-1] = out[-1] + "\n"
        out.append(assignment + "\n")
    return "".join(out).encode("utf-8")


def plan_profile_update(raw: bytes, documents: Sequence[object]) -> tuple[bytes, dict[str, Any]]:
    """Return updated env bytes and a public view. Does not write."""
    if not isinstance(raw, (bytes, bytearray)):
        raise InboundAllowError("control profile is unusable")
    before_private = _private_values(bytes(raw))
    if len(before_private) != 1 or not before_private[0].strip():
        raise InboundAllowError("control profile is unusable")
    existing = current_allowed_users(bytes(raw))
    merged = merge_allowed_users(existing, verified_worker_hexes(documents))
    updated = _replace_allowed_users(bytes(raw), ",".join(merged))
    after_private = _private_values(updated)
    if after_private != before_private:
        raise InboundAllowError("refusing to modify BUZZ_PRIVATE_KEY")
    for key in FORBIDDEN_ENV_KEYS:
        try:
            if env_assignment_values(updated, key):
                raise InboundAllowError("refusing secret material")
        except EnvFileError:
            raise InboundAllowError("control profile is unusable") from None
    view = {
        "allow_all_users": False,
        "allowed_users": list(merged),
        "changed": updated != bytes(raw),
    }
    return updated, view


def apply_inbound_authorization(
    *,
    profiles_root: str,
    configured_profile: object,
    gateway_units: Sequence[object],
    documents: Sequence[object],
) -> dict[str, Any]:
    """Update one profile. Idempotent. Preserves the private key and human keys."""
    profile = bind_control_profile(gateway_units, configured_profile)
    with open_named_profile(profile, profiles_root=profiles_root) as opened:
        raw = opened.read_env()
        updated, view = plan_profile_update(raw, documents)
        if updated != raw:
            opened.replace_env(updated)
    with open_named_profile(profile, profiles_root=profiles_root) as opened:
        after = opened.read_env()
    if _private_values(after) != _private_values(raw):
        raise InboundAllowError("refusing to modify BUZZ_PRIVATE_KEY")
    confirmed = current_allowed_users(after)
    if tuple(view["allowed_users"]) != confirmed:
        raise InboundAllowError("control allowlist is unusable")
    view["profile"] = profile
    view["changed"] = after != raw
    view["allow_all_users"] = False
    return view


def _load_request(raw: bytes) -> tuple[list[object], list[object]]:
    if not raw or len(raw) > 1_000_000 or b"\x00" in raw:
        raise InboundAllowError("invalid inbound request")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise InboundAllowError("invalid inbound request") from None
    if _SECRET_RE.search(text) or _PRIVATE_KEY in text:
        raise InboundAllowError("refusing secret material")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        raise InboundAllowError("invalid inbound request") from None
    if not isinstance(parsed, dict):
        raise InboundAllowError("invalid inbound request")
    units = parsed.get("gateway_units")
    workers = parsed.get("workers")
    if not isinstance(units, list) or not isinstance(workers, list):
        raise InboundAllowError("invalid inbound request")
    return units, workers


def main(argv: Sequence[str] | None = None) -> int:
    """Read the request on stdin and write only the bound profile."""
    if argv:
        sys.stderr.write("invalid inbound request\n")
        return 1
    try:
        refuse_forbidden_environment()
    except Exception:
        sys.stderr.write("refusing to run where provisioner-only credentials are present\n")
        return 1
    configured = os.environ.get(PROFILE_KEY)
    root = os.environ.get(PROFILES_ROOT_KEY) or HERMES_PROFILES_DIR
    try:
        units, workers = _load_request(sys.stdin.buffer.read(1_000_001))
        view = apply_inbound_authorization(
            profiles_root=root,
            configured_profile=configured,
            gateway_units=units,
            documents=workers,
        )
    except InboundAllowError as exc:
        sys.stdout.write(
            json.dumps(
                {"accepted": False, "error": {"code": "inbound_allow_failed", "message": exc.public_message}},
                separators=(",", ":"),
            )
            + "\n"
        )
        return 1
    sys.stdout.write(json.dumps({"accepted": True, **view}, separators=(",", ":")) + "\n")
    return 0
