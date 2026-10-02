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
ORIGIN_THREAD_ID = "FLEET_CONTROL_ORIGIN_THREAD_ID"
ORIGIN_MESSAGE_ID = "FLEET_CONTROL_ORIGIN_MESSAGE_ID"
ORIGIN_CHAT_TYPE = "FLEET_CONTROL_ORIGIN_CHAT_TYPE"
ORIGIN_SCOPE_ID = "FLEET_CONTROL_ORIGIN_SCOPE_ID"
ORIGIN_USER_ID = "FLEET_CONTROL_ORIGIN_USER_ID"
ORIGIN_ENV_KEYS = (
    ORIGIN_PLATFORM,
    ORIGIN_CHAT_ID,
    ORIGIN_SESSION_KEY,
    ORIGIN_THREAD_ID,
    ORIGIN_MESSAGE_ID,
    ORIGIN_CHAT_TYPE,
    ORIGIN_SCOPE_ID,
    ORIGIN_USER_ID,
)
_CORE_KEYS = (ORIGIN_PLATFORM, ORIGIN_CHAT_ID, ORIGIN_SESSION_KEY)
_ROUTE_KEYS = (
    ORIGIN_THREAD_ID,
    ORIGIN_MESSAGE_ID,
    ORIGIN_CHAT_TYPE,
    ORIGIN_SCOPE_ID,
    ORIGIN_USER_ID,
)
_CHAT_TYPES = frozenset({"dm", "group", "channel", "thread"})

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
    """Human conversation that asked for the delegation.

    ``thread_id`` is the platform topic (Telegram topic, Buzz NIP-10 root).
    ``message_id`` is the reply anchor that keeps a topic lane visible.
    Both are empty when the conversation has no topic. ``chat_type`` is
    empty only on records written before the route fields existed.
    """

    platform: str
    chat_id: str
    session_key: str
    thread_id: str = ""
    message_id: str = ""
    chat_type: str = ""
    scope_id: str = ""
    user_id: str = ""


def read_trusted_origin(env: Mapping[str, str]) -> ReplyOrigin | None:
    """Return the per-call origin, or None when the core variables are absent.

    A partial or invalid assignment fails closed. It is not treated as a
    missing origin. Route fields are optional as a group: all absent keeps
    the older three-field origin, and any one of them requires the rest.
    """
    core = [env.get(key) for key in _CORE_KEYS]
    route = [env.get(key) for key in _ROUTE_KEYS]
    if all(value is None or value == "" for value in core):
        if any(value not in (None, "") for value in route):
            raise fail("origin_unavailable")
        return None
    if any(value is None for value in route) and any(value is not None for value in route):
        raise fail("origin_unavailable")
    platform, chat_id, session_key = core
    if all(value is None for value in route):
        origin = parse_origin(platform, chat_id, session_key)
    else:
        thread_id, message_id, chat_type, scope_id, user_id = route
        origin = parse_origin(
            platform,
            chat_id,
            session_key,
            thread_id=thread_id,
            message_id=message_id,
            chat_type=chat_type,
            scope_id=scope_id,
            user_id=user_id,
        )
    if origin is None:
        raise fail("origin_unavailable")
    return origin


def parse_origin(
    platform: object,
    chat_id: object,
    session_key: object,
    thread_id: object = "",
    message_id: object = "",
    chat_type: object = "",
    scope_id: object = "",
    user_id: object = "",
) -> ReplyOrigin | None:
    """Validate one stored or trusted origin. Return None when it is unusable."""
    if not isinstance(platform, str) or _PLATFORM_RE.fullmatch(platform) is None:
        return None
    if platform in _NON_MESSAGING:
        return None
    chat = _bounded(chat_id, _MAX_CHAT_ID)
    session = _bounded(session_key, _MAX_SESSION_KEY)
    if chat is None or session is None:
        return None
    route = _route(thread_id, message_id, chat_type, scope_id, user_id)
    if route is None:
        return None
    return ReplyOrigin(platform=platform, chat_id=chat, session_key=session, **route)


def targets_worker_dm(origin: ReplyOrigin, channel_id: str) -> bool:
    """True when delivering here would answer inside the worker DM."""
    channel = channel_id.casefold()
    if origin.platform == "buzz" and origin.chat_id.casefold() == channel:
        return True
    return channel in [part.casefold() for part in origin.session_key.split(":")]


def _route(
    thread_id: object,
    message_id: object,
    chat_type: object,
    scope_id: object,
    user_id: object,
) -> dict[str, str] | None:
    """Validate the topic route. An all-empty route is the older origin."""
    values = (thread_id, message_id, chat_type, scope_id, user_id)
    if all(value == "" for value in values):
        return {
            "thread_id": "",
            "message_id": "",
            "chat_type": "",
            "scope_id": "",
            "user_id": "",
        }
    if not isinstance(chat_type, str) or chat_type not in _CHAT_TYPES:
        return None
    cleaned: list[str] = []
    for value in (thread_id, message_id, scope_id, user_id):
        if value == "":
            cleaned.append("")
            continue
        bounded = _bounded(value, _MAX_CHAT_ID)
        if bounded is None:
            return None
        cleaned.append(bounded)
    thread, message, scope, user = cleaned
    return {
        "thread_id": thread,
        "message_id": message,
        "chat_type": chat_type,
        "scope_id": scope,
        "user_id": user,
    }


def _bounded(value: object, limit: int) -> str | None:
    if not isinstance(value, str) or not value or len(value) > limit:
        return None
    if any(ord(char) < 32 or char.isspace() for char in value):
        return None
    lowered = value.lower()
    if "nsec1" in lowered or "buzz_private_key" in lowered:
        return None
    return value
