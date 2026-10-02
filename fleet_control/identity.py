"""Read Control's selected Hermes profile ``.env`` without sourcing it.

The private key is returned only to the Buzz child environment. It is
not part of ``repr``, argv, the journal, or public errors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fleet_control.authorize import canonicalize_relay
from fleet_control.config import FORBIDDEN_ENV_KEYS
from fleet_control.errors import fail
from fleet_control.support.envfile import env_assignment_values
from fleet_control.support.nostr_codec import decode_nsec, derive_nostr_public_key
from fleet_control.support.profile_env import open_named_profile

ENV_KEY = "BUZZ_PRIVATE_KEY"
RELAY_KEY = "BUZZ_RELAY_URL"
AUTH_TAG_KEY = "BUZZ_AUTH_TAG"
PROFILE_KEY = "FLEET_CONTROL_HERMES_PROFILE"
PROFILES_ROOT_KEY = "FLEET_CONTROL_PROFILES_ROOT"
_SAFE_LOCALE = re.compile(r"^[A-Za-z0-9._@+-]+$")
# Buzz child only. This does not select the helper interpreter.
_CHILD_PATH = "/usr/local/bin:/usr/bin:/bin"


@dataclass(frozen=True)
class ControlBuzzIdentity:
    """Control signing material. ``repr`` omits the private key."""

    public_key_hex: str
    relay_url: str
    auth_tag: str | None
    _private_key: str

    def __repr__(self) -> str:
        return (
            "ControlBuzzIdentity("
            f"public_key_hex={self.public_key_hex!r}, relay_url={self.relay_url!r})"
        )

    def exposes_secret(self, task: str) -> bool:
        """True when the task contains the loaded private key. Does not log it."""
        return bool(self._private_key) and self._private_key in task

    def child_env(self, environ: dict[str, str]) -> dict[str, str]:
        """Minimum Buzz environment. Does not inherit the parent environ."""
        env = {
            "PATH": _CHILD_PATH,
            ENV_KEY: self._private_key,
            RELAY_KEY: self.relay_url,
        }
        for key in ("LANG", "LC_ALL"):
            value = str(environ.get(key) or "")
            if _SAFE_LOCALE.fullmatch(value):
                env[key] = value
        if self.auth_tag is not None:
            env[AUTH_TAG_KEY] = self.auth_tag
        return env


def read_profile_env(profile: str, profiles_root: str) -> bytes:
    """Read ``.env`` through the pinned profile FD. Caller must not log it."""
    try:
        with open_named_profile(profile, profiles_root=profiles_root) as opened:
            return opened.read_env()
    except Exception:
        raise fail("control_profile_unusable") from None


def load_control_buzz_identity(raw: bytes) -> ControlBuzzIdentity:
    """Parse Buzz assignments. Quotes are not stripped. Other lines are ignored."""
    if not isinstance(raw, (bytes, bytearray)):
        raise fail("control_profile_unusable")
    blob = bytes(raw)
    for key in FORBIDDEN_ENV_KEYS:
        if key.encode("ascii") in blob:
            raise fail("forbidden_environment")
    private_key = _one(blob, ENV_KEY)
    relay = _one(blob, RELAY_KEY)
    auth_values = _values(blob, AUTH_TAG_KEY)
    if len(auth_values) > 1:
        raise fail("control_profile_unusable")
    auth_tag = auth_values[0] if auth_values else None
    if auth_tag is not None and not _safe_token(auth_tag):
        raise fail("control_profile_unusable")
    try:
        secret = decode_nsec(private_key)
        public_hex = derive_nostr_public_key(secret).hex()
    except Exception:
        raise fail("control_profile_unusable") from None
    try:
        canonical = canonicalize_relay(relay)
    except Exception:
        raise fail("control_profile_unusable") from None
    return ControlBuzzIdentity(
        public_key_hex=public_hex,
        relay_url=canonical,
        auth_tag=auth_tag,
        _private_key=private_key,
    )


def _values(raw: bytes, key: str) -> list[str]:
    try:
        values = env_assignment_values(raw, key)
    except Exception:
        raise fail("control_profile_unusable") from None
    return values


def _one(raw: bytes, key: str) -> str:
    values = _values(raw, key)
    if len(values) != 1:
        raise fail("control_profile_unusable")
    value = values[0]
    if value != value.strip() or not _safe_token(value):
        raise fail("control_profile_unusable")
    return value


def _safe_token(value: str) -> bool:
    if not value or len(value) > 4096:
        return False
    return not any(ch in value for ch in ("\n", "\r", "\x00", " ", "'", '"'))
