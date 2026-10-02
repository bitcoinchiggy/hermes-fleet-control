"""Decide how Control treats an inbound Buzz message that may be a worker reply.

``acknowledge_worker is None`` means this plan does not apply.
``False`` means a correlated reply is not answered in the worker DM.
``suppress_worker_delivery`` and ``suppress_worker_error`` are true for
every correlated reply, including an unknown origin or a mismatched
sender, so neither an acknowledgement nor an error notice starts another
worker turn.

The destination is the origin stored when the delegation was accepted.
This function does not accept a caller-supplied route, and it does not
read a route out of the reply text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Mapping

from fleet_control.origin import ReplyOrigin, parse_origin, targets_worker_dm
from fleet_control.support.names import NAME_RE

KIND_DELEGATION_REPLY = "delegation_reply"
KIND_NOT_DELEGATION_REPLY = "not_delegation_reply"
REASON_ORIGIN_UNKNOWN = "origin_unknown"
REASON_ORIGIN_INVALID = "origin_invalid"
REASON_NOT_ACCEPTED = "delegation_not_accepted"
REASON_RECORD_UNUSABLE = "record_unusable"
REASON_REPLY_UNSAFE = "reply_unsafe"
REASON_SENDER_MISMATCH = "sender_mismatch"
REASON_REPLY_COMPLETED = "reply_completed"
REASON_REPLY_IN_FLIGHT = "reply_in_flight"
DELIVERY_WAKE = "wake"
DELIVERY_COMPLETED = "completed"
DELIVERY_IN_FLIGHT = "in_flight"

_DELEGATION_ID_RE = re.compile(r"^dlg_[0-9a-f]{32}$")
_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_MAX_CHANNEL_ID = 256
_MAX_REPLY_TEXT = 8000
_NO_NOTE = frozenset({REASON_SENDER_MISMATCH, REASON_NOT_ACCEPTED, REASON_RECORD_UNUSABLE})


@dataclass(frozen=True)
class DelegationReplyPlan:
    """Gateway instruction for one inbound message.

    ``wake_text`` is present only together with ``report_to``. It contains
    the stored task and the inbound worker result.
    """

    kind: str
    acknowledge_worker: bool | None
    reason: str | None
    delegation_id: str | None
    worker: str | None
    parent_text_present: bool
    report_to: ReplyOrigin | None
    wake_text: str | None
    suppress_worker_delivery: bool | None
    suppress_worker_error: bool | None
    claim_id: str | None = None
    delivery: str | None = None
    inbound_event_id: str | None = None

    def public_body(self) -> dict[str, object]:
        """JSON the gateway can apply. Secret-shaped replies never reach it."""
        destination = None
        if self.report_to is not None:
            destination = {
                "platform": self.report_to.platform,
                "chat_id": self.report_to.chat_id,
                "session_key": self.report_to.session_key,
                "thread_id": self.report_to.thread_id,
                "message_id": self.report_to.message_id,
                "chat_type": self.report_to.chat_type,
                "scope_id": self.report_to.scope_id,
                "user_id": self.report_to.user_id,
            }
        return {
            "kind": self.kind,
            "acknowledge_worker": self.acknowledge_worker,
            "reason": self.reason,
            "delegation_id": self.delegation_id,
            "worker": self.worker,
            "parent_text_present": self.parent_text_present,
            "report_to": destination,
            "wake_text": self.wake_text,
            "suppress_worker_delivery": self.suppress_worker_delivery,
            "suppress_worker_error": self.suppress_worker_error,
            "claim_id": self.claim_id,
            "delivery": self.delivery,
            "inbound_event_id": self.inbound_event_id,
        }


def without_wake(
    plan: DelegationReplyPlan,
    *,
    reason: str,
    delivery: str,
    claim_id: str | None,
    inbound_event_id: str | None = None,
) -> DelegationReplyPlan:
    """A correlated reply that must not start another human turn."""
    return replace(
        plan,
        wake_text=None,
        reason=reason,
        delivery=delivery,
        claim_id=claim_id,
        inbound_event_id=inbound_event_id,
    )


def plan_delegation_reply(
    record: Mapping[str, object],
    *,
    reply_to_message_id: str | None,
    reply_to_text: str | None,
    inbound_text: str,
    sender_public_key_hex: str | None,
) -> DelegationReplyPlan:
    """Correlate one inbound message with one journal record."""
    event_id = record.get("event_id") if isinstance(record, Mapping) else None
    if (
        not isinstance(reply_to_message_id, str)
        or not reply_to_message_id
        or not isinstance(event_id, str)
        or reply_to_message_id != event_id
    ):
        return _untouched()

    parent_text_present = isinstance(reply_to_text, str) and bool(reply_to_text.strip())
    delegation_id = _delegation_id(record)
    worker = _worker(record)
    if record.get("state") != "accepted":
        return _correlated(
            reason=REASON_NOT_ACCEPTED,
            parent_text_present=parent_text_present,
            delegation_id=delegation_id,
            worker=worker,
        )

    channel_id = _channel_id(record)
    if delegation_id is None or worker is None or channel_id is None:
        return _correlated(
            reason=REASON_RECORD_UNUSABLE,
            parent_text_present=parent_text_present,
        )
    if not _sender_matches(record.get("worker_public_key_hex"), sender_public_key_hex):
        return _correlated(
            reason=REASON_SENDER_MISMATCH,
            parent_text_present=parent_text_present,
            delegation_id=delegation_id,
            worker=worker,
        )

    reply = _reply_text(inbound_text)
    if reply is None:
        return _correlated(
            reason=REASON_REPLY_UNSAFE,
            parent_text_present=parent_text_present,
            delegation_id=delegation_id,
            worker=worker,
        )

    origin = parse_origin(
        record.get("origin_platform"),
        record.get("origin_chat_id"),
        record.get("origin_session_key"),
        thread_id=record.get("origin_thread_id", ""),
        message_id=record.get("origin_message_id", ""),
        chat_type=record.get("origin_chat_type", ""),
        scope_id=record.get("origin_scope_id", ""),
        user_id=record.get("origin_user_id", ""),
    )
    if "origin_platform" not in record:
        return _correlated(
            reason=REASON_ORIGIN_UNKNOWN,
            parent_text_present=parent_text_present,
            delegation_id=delegation_id,
            worker=worker,
        )
    if origin is None or targets_worker_dm(origin, channel_id):
        return _correlated(
            reason=REASON_ORIGIN_INVALID,
            parent_text_present=parent_text_present,
            delegation_id=delegation_id,
            worker=worker,
        )

    task = record.get("task")
    if not isinstance(task, str) or not task.strip():
        return _correlated(
            reason=REASON_RECORD_UNUSABLE,
            parent_text_present=parent_text_present,
            delegation_id=delegation_id,
            worker=worker,
        )
    return _correlated(
        reason=None,
        parent_text_present=parent_text_present,
        delegation_id=delegation_id,
        worker=worker,
        report_to=origin,
        wake_text=_wake(delegation_id, worker, task, reply),
    )


def should_note_reply(plan: DelegationReplyPlan) -> bool:
    """Link a verified worker reply into the task record."""
    return plan.kind == KIND_DELEGATION_REPLY and plan.reason not in _NO_NOTE


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
        suppress_worker_delivery=None,
        suppress_worker_error=None,
        claim_id=None,
        delivery=None,
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
        suppress_worker_delivery=True,
        suppress_worker_error=True,
        claim_id=None,
        delivery=None,
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
    value = record.get("channel_id")
    if not isinstance(value, str) or not value or len(value) > _MAX_CHANNEL_ID:
        return None
    if any(ord(char) < 32 or char.isspace() for char in value):
        return None
    return value


def _sender_matches(expected: object, sender: object) -> bool:
    if not isinstance(expected, str) or not isinstance(sender, str):
        return False
    if not _HEX64_RE.fullmatch(expected) or not _HEX64_RE.fullmatch(sender):
        return False
    return sender.lower() == expected.lower()


def _reply_text(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > _MAX_REPLY_TEXT or "\x00" in value:
        return None
    lowered = value.lower()
    if "nsec1" in lowered or "buzz_private_key" in lowered:
        return None
    return value


def _wake(delegation_id: str, worker: str, task: str, inbound_text: str) -> str:
    return (
        f"Worker result for delegation {delegation_id} ({worker}).\n"
        "Original task:\n"
        f"{task}\n\n"
        "Inbound worker reply:\n"
        f"{inbound_text}\n\n"
        "Evaluate this result for the human. "
        "A further instruction is a new delegate_worker call."
    )
