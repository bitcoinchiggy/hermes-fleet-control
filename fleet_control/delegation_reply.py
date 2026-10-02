"""Decide whether an inbound Buzz message is a worker reply to a delegation.

This module does not send messages and does not read or write the journal.
Deployed Hermes ``7817bf522af3caf54b30ae59f16157469d7638fc`` does not call
``plan_delegation_reply``. Until the gateway consults the plan before
``adapter.send``, Control's answer is still delivered into the worker DM.

``acknowledge_worker is None`` means this plan does not apply and the
gateway should keep its normal path. ``False`` means a correlated worker
reply must not be answered in the worker DM. A further instruction is a
new ``delegate_worker`` call, which sends a new top-level DM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from fleet_control.support.names import NAME_RE

KIND_DELEGATION_REPLY = "delegation_reply"
KIND_NOT_DELEGATION_REPLY = "not_delegation_reply"
REASON_ORIGIN_UNKNOWN = "origin_unknown"
REASON_ORIGIN_INVALID = "origin_invalid"
REASON_NOT_ACCEPTED = "delegation_not_accepted"
REASON_RECORD_UNUSABLE = "record_unusable"
REASON_REPLY_UNSAFE = "reply_unsafe"

_DELEGATION_ID_RE = re.compile(r"^dlg_[0-9a-f]{32}$")
_PLATFORM_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_MAX_CHAT_ID = 256
_MAX_SESSION_KEY = 512
_MAX_CHANNEL_ID = 256
_MAX_REPLY_TEXT = 8000


@dataclass(frozen=True)
class ReplyOrigin:
    """Trusted human destination supplied by the gateway, not by message text."""

    platform: str
    chat_id: str
    session_key: str


@dataclass(frozen=True)
class DelegationReplyPlan:
    """What Control should do with one inbound message.

    ``wake_text`` is present only when ``report_to`` is set. It names the
    delegation and quotes the inbound reply. It does not contain the
    original task.
    """

    kind: str
    acknowledge_worker: bool | None
    reason: str | None
    delegation_id: str | None
    worker: str | None
    parent_text_present: bool
    report_to: ReplyOrigin | None
    wake_text: str | None


def plan_delegation_reply(
    record: Mapping[str, object],
    *,
    reply_to_message_id: str | None,
    reply_to_text: str | None,
    inbound_text: str,
    origin: ReplyOrigin | None = None,
) -> DelegationReplyPlan:
    """Correlate one inbound message with one journal record.

    ``origin`` is a separate trusted argument. Text inside the reply is
    never parsed into a destination. A missing or different
    ``reply_to_message_id`` leaves the message on the normal gateway path.
    """
    event_id = record.get("event_id") if isinstance(record, Mapping) else None
    if (
        not isinstance(reply_to_message_id, str)
        or not reply_to_message_id
        or not isinstance(event_id, str)
        or reply_to_message_id != event_id
    ):
        return _untouched()

    parent_text_present = isinstance(reply_to_text, str) and bool(reply_to_text.strip())
    if record.get("state") != "accepted":
        return _correlated(
            reason=REASON_NOT_ACCEPTED,
            parent_text_present=parent_text_present,
            delegation_id=_delegation_id(record),
            worker=_worker(record),
        )

    delegation_id = _delegation_id(record)
    worker = _worker(record)
    channel_id = _channel_id(record)
    if delegation_id is None or worker is None or channel_id is None:
        return _correlated(
            reason=REASON_RECORD_UNUSABLE,
            parent_text_present=parent_text_present,
        )

    reply = _reply_text(inbound_text)
    if reply is None:
        return _correlated(
            reason=REASON_REPLY_UNSAFE,
            parent_text_present=parent_text_present,
            delegation_id=delegation_id,
            worker=worker,
        )
    if origin is None:
        return _correlated(
            reason=REASON_ORIGIN_UNKNOWN,
            parent_text_present=parent_text_present,
            delegation_id=delegation_id,
            worker=worker,
        )

    destination = _destination(origin, channel_id)
    if destination is None:
        return _correlated(
            reason=REASON_ORIGIN_INVALID,
            parent_text_present=parent_text_present,
            delegation_id=delegation_id,
            worker=worker,
        )
    return _correlated(
        reason=None,
        parent_text_present=parent_text_present,
        delegation_id=delegation_id,
        worker=worker,
        report_to=destination,
        wake_text=_wake(delegation_id, worker, reply),
    )


def _untouched() -> DelegationReplyPlan:
    return DelegationReplyPlan(
        kind=KIND_NOT_DELEGATION_REPLY,
        acknowledge_worker=None,
        reason=None,
        delegation_id=None,
        worker=None,
        parent_text_present=False,
        report_to=None,
        wake_text=None,
    )


def _correlated(
    *,
    reason: str | None,
    parent_text_present: bool,
    delegation_id: str | None = None,
    worker: str | None = None,
    report_to: ReplyOrigin | None = None,
    wake_text: str | None = None,
) -> DelegationReplyPlan:
    return DelegationReplyPlan(
        kind=KIND_DELEGATION_REPLY,
        acknowledge_worker=False,
        reason=reason,
        delegation_id=delegation_id,
        worker=worker,
        parent_text_present=parent_text_present,
        report_to=report_to,
        wake_text=wake_text,
    )


def _delegation_id(record: Mapping[str, object]) -> str | None:
    value = record.get("delegation_id")
    if isinstance(value, str) and _DELEGATION_ID_RE.fullmatch(value):
        return value
    return None


def _worker(record: Mapping[str, object]) -> str | None:
    value = record.get("worker")
    if isinstance(value, str) and NAME_RE.fullmatch(value):
        return value
    return None


def _channel_id(record: Mapping[str, object]) -> str | None:
    return _bounded(record.get("channel_id"), _MAX_CHANNEL_ID)


def _reply_text(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > _MAX_REPLY_TEXT or "\x00" in value:
        return None
    if _has_secret(value):
        return None
    return value


def _destination(origin: object, channel_id: str) -> ReplyOrigin | None:
    platform = getattr(origin, "platform", None)
    chat_id = getattr(origin, "chat_id", None)
    session_key = getattr(origin, "session_key", None)
    if not isinstance(platform, str) or _PLATFORM_RE.fullmatch(platform) is None:
        return None
    chat = _bounded(chat_id, _MAX_CHAT_ID)
    session = _bounded(session_key, _MAX_SESSION_KEY)
    if chat is None or session is None:
        return None
    if _targets_worker_dm(platform, chat, session, channel_id):
        return None
    return ReplyOrigin(platform=platform, chat_id=chat, session_key=session)


def _targets_worker_dm(platform: str, chat_id: str, session_key: str, channel_id: str) -> bool:
    channel = channel_id.casefold()
    if platform == "buzz" and chat_id.casefold() == channel:
        return True
    return channel in [part.casefold() for part in session_key.split(":")]


def _bounded(value: object, limit: int) -> str | None:
    if not isinstance(value, str) or not value or len(value) > limit:
        return None
    if any(ord(char) < 32 or char.isspace() for char in value):
        return None
    if _has_secret(value):
        return None
    return value


def _has_secret(value: str) -> bool:
    lowered = value.lower()
    return "nsec1" in lowered or "buzz_private_key" in lowered


def _wake(delegation_id: str, worker: str, inbound_text: str) -> str:
    return (
        f"Pending delegation {delegation_id} from worker {worker}. "
        "The original task text is not included. "
        f"Inbound worker reply:\n{inbound_text}"
    )
