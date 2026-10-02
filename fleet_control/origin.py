"""Trusted human origin for one Hermes gateway turn.

The model payload and the worker message are not origins. The MCP
server copies ``_meta["hermes.fleet.origin"]`` into the helper
environment for that one ``fleet-delegate`` process. A static MCP
environment cannot set these variables: the server deletes them before
applying the per-call meta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from fleet_control.errors import fail

ORIGIN_PLATFORM = "FLEET_CONTROL_ORIGIN_PLATFORM"
ORIGIN_CHAT_ID = "FLEET_CONTROL_ORIGIN_CHAT_ID"
ORIGIN_SESSION_KEY = "FLEET_CONTROL_ORIGIN_SESSION_KEY"
ORIGIN_ENV_KEYS = (ORIGIN_PLATFORM, ORIGIN_CHAT_ID, ORIGIN_SESSION_KEY)

_PLATFORM_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_MAX_CHAT_ID = 256
_MAX_SESSION_KEY = 512
# Hermes session_context.NON_MESSAGING_SESSION_SURFACES. These are not a
# human conversation the gateway can resume.
_NON_MESSAGING = frozenset(
    {
        "",
        "api_server",
        "cli",
        "codex",
        "desktop",
        "gateway",
        "kanban",
        "local",
        "msgraph_webhook",
        "tool",
        "tui",
        "webhook",
    }
)


@dataclass(frozen=True)
class ReplyOrigin:
    """Human conversation that asked for the delegation."""

    platform: str
    chat_id: str
    session_key: str


def read_trusted_origin(env: Mapping[str, str]) -> ReplyOrigin | None:
    """Return the per-call origin, or None when all three variables are absent.

    A partial or invalid assignment fails closed. It is not treated as a
    missing origin.
    """
    values = [env.get(key) for key in ORIGIN_ENV_KEYS]
    if all(value is None or value == "" for value in values):
        return None
    platform, chat_id, session_key = values
    origin = parse_origin(platform, chat_id, session_key)
    if origin is None:
        raise fail("origin_unavailable")
    return origin


def parse_origin(platform: object, chat_id: object, session_key: object) -> ReplyOrigin | None:
    """Validate one stored or trusted origin. Return None when it is unusable."""
    if not isinstance(platform, str) or _PLATFORM_RE.fullmatch(platform) is None:
        return None
    if platform in _NON_MESSAGING:
        return None
    chat = _bounded(chat_id, _MAX_CHAT_ID)
    session = _bounded(session_key, _MAX_SESSION_KEY)
    if chat is None or session is None:
        return None
    return ReplyOrigin(platform=platform, chat_id=chat, session_key=session)


def targets_worker_dm(origin: ReplyOrigin, channel_id: str) -> bool:
    """True when delivering here would answer inside the worker DM."""
    channel = channel_id.casefold()
    if origin.platform == "buzz" and origin.chat_id.casefold() == channel:
        return True
    return channel in [part.casefold() for part in origin.session_key.split(":")]


def _bounded(value: object, limit: int) -> str | None:
    if not isinstance(value, str) or not value or len(value) > limit:
        return None
    if any(ord(char) < 32 or char.isspace() for char in value):
        return None
    lowered = value.lower()
    if "nsec1" in lowered or "buzz_private_key" in lowered:
        return None
    return value
