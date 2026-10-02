"""Correlate one inbound Buzz reply with the local delegation journal.

The Hermes gateway observes the reply parent and the sender pubkey.
Those values are arguments here. The reply text is not a route, and
this module does not send messages.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
from pathlib import Path
from typing import Any, Mapping

from fleet_control.delegation_reply import (
    DELIVERY_COMPLETED,
    DELIVERY_IN_FLIGHT,
    DELIVERY_WAKE,
    KIND_NOT_DELEGATION_REPLY,
    REASON_REPLY_COMPLETED,
    REASON_REPLY_IN_FLIGHT,
    DelegationReplyPlan,
    plan_delegation_reply,
    should_note_reply,
    without_wake,
)
from fleet_control.errors import ControlError, fail
from fleet_control.journal import (
    MAX_REPLY_EVENTS,
    delete_reply_hold,
    exclusive_delegation,
    exclusive_delegation_wait,
    iter_records,
    read_record,
    read_reply_hold,
    resolve_journal_dir,
    update_record,
    write_record,
    write_reply_hold,
)
from fleet_control.output import public_json

_REQUEST_KEYS = frozenset(
    {
        "reply_to_message_id",
        "sender_public_key_hex",
        "inbound_text",
        "inbound_event_id",
        "reply_to_text",
        "action",
        "claim_id",
        "delegation_id",
        "gateway_owner",
        "gateway_pid",
    }
)
_ACTIONS = frozenset({"observe", "complete", "release", "recover"})
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_OWNER_RE = re.compile(r"^[0-9a-f]{32}$")
_PROCESS_OWNER = secrets.token_hex(16)
_RECOVER_LIMIT = 8


def evaluate_inbound_reply(
    directory: Path,
    *,
    reply_to_message_id: str | None,
    sender_public_key_hex: str | None,
    inbound_text: str,
    inbound_event_id: str | None,
    reply_to_text: str | None = None,
    gateway_owner: str | None = None,
    gateway_pid: int | None = None,
) -> DelegationReplyPlan:
    """Return the gateway plan and claim a wake at most once per reply event.

    A completed reply does not wake again. A live inflight claim does not
    wake a second caller. A pending claim, or an inflight claim whose pid
    is gone, is claimed again so a crash or a missing adapter can be retried.
    """
    plan = _plan_for_parent(
        directory,
        reply_to_message_id=reply_to_message_id,
        sender_public_key_hex=sender_public_key_hex,
        inbound_text=inbound_text,
        reply_to_text=reply_to_text,
    )
    if plan.wake_text is None:
        record = _single_match(directory, reply_to_message_id)
        if record is not None and should_note_reply(plan):
            _note_reply(directory, record, inbound_event_id)
        return plan
    record = _single_match(directory, reply_to_message_id)
    if record is None:
        return plan
    return _claim_wake(
        directory,
        record,
        plan,
        inbound_text=inbound_text,
        inbound_event_id=inbound_event_id,
        sender_public_key_hex=sender_public_key_hex,
        reply_to_message_id=reply_to_message_id,
        owner=_owner(gateway_owner),
        pid=_pid(gateway_pid),
    )


def complete_reply_delivery(
    directory: Path,
    delegation_id: str,
    inbound_event_id: str,
    claim_id: str,
) -> bool:
    """Mark one inflight reply completed. Already completed is success."""
    if not _OWNER_RE.fullmatch(claim_id) or not _HEX64.fullmatch(inbound_event_id):
        return False
    try:
        with exclusive_delegation_wait(directory, delegation_id):
            fresh = read_record(directory, delegation_id)
            if fresh is None:
                return False
            entries = _entries(fresh)
            current = _find(entries, inbound_event_id)
            if current is None:
                return False
            if current["state"] == "completed":
                delete_reply_hold(directory, delegation_id, inbound_event_id)
                return True
            if current["state"] != "inflight" or current["claim_id"] != claim_id:
                return False
            current["state"] = "completed"
            current["owner"] = ""
            current["pid"] = 0
            write_record(directory, update_record(fresh, reply_deliveries=entries))
            delete_reply_hold(directory, delegation_id, inbound_event_id)
    except ControlError:
        return False
    return True


def release_reply_claim(
    directory: Path,
    delegation_id: str,
    inbound_event_id: str,
    claim_id: str,
) -> bool:
    """Return an unfinished claim to pending so recovery can retry it."""
    if not _OWNER_RE.fullmatch(claim_id) or not _HEX64.fullmatch(inbound_event_id):
        return False
    try:
        with exclusive_delegation_wait(directory, delegation_id):
            fresh = read_record(directory, delegation_id)
            if fresh is None:
                return False
            entries = _entries(fresh)
            current = _find(entries, inbound_event_id)
            if current is None:
                return False
            if current["state"] == "pending":
                return True
            if current["state"] != "inflight" or current["claim_id"] != claim_id:
                return False
            current["state"] = "pending"
            current["owner"] = ""
            current["pid"] = 0
            write_record(directory, update_record(fresh, reply_deliveries=entries))
    except ControlError:
        return False
    return True


def recover_unfinished_replies(
    directory: Path,
    *,
    gateway_owner: str | None = None,
    gateway_pid: int | None = None,
) -> list[DelegationReplyPlan]:
    """Claim pending replies and inflight replies whose owner pid is gone.

    A live pid is left alone, so a concurrent intake does not steal the wake.
    """
    owner = _owner(gateway_owner)
    pid = _pid(gateway_pid)
    plans: list[DelegationReplyPlan] = []
    for record in iter_records(directory):
        if len(plans) >= _RECOVER_LIMIT:
            break
        delegation_id = record.get("delegation_id")
        if not isinstance(delegation_id, str):
            continue
        for entry in _entries(record):
            if len(plans) >= _RECOVER_LIMIT:
                break
            if not _needs_recovery(entry, owner):
                continue
            event_id = entry.get("event_id")
            if not isinstance(event_id, str):
                continue
            held = read_reply_hold(directory, delegation_id, event_id)
            text = held.get("inbound_text") if isinstance(held, dict) else None
            sender = held.get("sender_public_key_hex") if isinstance(held, dict) else None
            parent = held.get("reply_to_message_id") if isinstance(held, dict) else record.get("event_id")
            if not isinstance(text, str) or not isinstance(sender, str) or not isinstance(parent, str):
                continue
            plan = evaluate_inbound_reply(
                directory,
                reply_to_message_id=parent,
                sender_public_key_hex=sender,
                inbound_text=text,
                inbound_event_id=event_id,
                gateway_owner=owner,
                gateway_pid=pid,
            )
            if plan.delivery == DELIVERY_WAKE and plan.wake_text:
                plans.append(plan)
    return plans


def _plan_for_parent(
    directory: Path,
    *,
    reply_to_message_id: str | None,
    sender_public_key_hex: str | None,
    inbound_text: str,
    reply_to_text: str | None,
) -> DelegationReplyPlan:
    record = _single_match(directory, reply_to_message_id)
    if not isinstance(reply_to_message_id, str) or not reply_to_message_id or record is None:
        empty = {} if record is None else {"event_id": reply_to_message_id, "state": "accepted"}
        if record is None and _match_count(directory, reply_to_message_id) > 1:
            empty = {"event_id": reply_to_message_id, "state": "accepted"}
        return plan_delegation_reply(
            {} if record is None and _match_count(directory, reply_to_message_id) <= 1 else empty,
            reply_to_message_id=reply_to_message_id,
            reply_to_text=reply_to_text,
            inbound_text=inbound_text,
            sender_public_key_hex=sender_public_key_hex,
        )
    return plan_delegation_reply(
        record,
        reply_to_message_id=reply_to_message_id,
        reply_to_text=reply_to_text,
        inbound_text=inbound_text,
        sender_public_key_hex=sender_public_key_hex,
    )


def _match_count(directory: Path, reply_to_message_id: str | None) -> int:
    if not isinstance(reply_to_message_id, str) or not reply_to_message_id:
        return 0
    return sum(1 for record in iter_records(directory) if record.get("event_id") == reply_to_message_id)


def _single_match(directory: Path, reply_to_message_id: str | None) -> dict[str, Any] | None:
    if not isinstance(reply_to_message_id, str) or not reply_to_message_id:
        return None
    matches = [record for record in iter_records(directory) if record.get("event_id") == reply_to_message_id]
    if len(matches) != 1:
        return None
    return matches[0]


def _claim_wake(
    directory: Path,
    record: Mapping[str, Any],
    plan: DelegationReplyPlan,
    *,
    inbound_text: str,
    inbound_event_id: str | None,
    sender_public_key_hex: str | None,
    reply_to_message_id: str | None,
    owner: str,
    pid: int,
) -> DelegationReplyPlan:
    delegation_id = record.get("delegation_id")
    if (
        not isinstance(delegation_id, str)
        or not isinstance(inbound_event_id, str)
        or not _HEX64.fullmatch(inbound_event_id)
        or not isinstance(reply_to_message_id, str)
        or not isinstance(sender_public_key_hex, str)
    ):
        return without_wake(plan, reason=REASON_REPLY_IN_FLIGHT, delivery=DELIVERY_IN_FLIGHT, claim_id=None)
    try:
        with exclusive_delegation_wait(directory, delegation_id):
            fresh = read_record(directory, delegation_id)
            if fresh is None or fresh.get("state") != "accepted" or "reply_event_ids" not in fresh:
                return without_wake(plan, reason=REASON_REPLY_IN_FLIGHT, delivery=DELIVERY_IN_FLIGHT, claim_id=None)
            if fresh.get("event_id") != reply_to_message_id:
                return without_wake(plan, reason=REASON_REPLY_IN_FLIGHT, delivery=DELIVERY_IN_FLIGHT, claim_id=None)
            entries = _entries(fresh)
            current = _find(entries, inbound_event_id)
            if current is not None and current["state"] == "completed":
                return without_wake(
                    plan,
                    reason=REASON_REPLY_COMPLETED,
                    delivery=DELIVERY_COMPLETED,
                    claim_id=current["claim_id"],
                    inbound_event_id=inbound_event_id,
                )
            if current is not None and current["state"] == "inflight" and _pid_alive(current["pid"]):
                return without_wake(
                    plan,
                    reason=REASON_REPLY_IN_FLIGHT,
                    delivery=DELIVERY_IN_FLIGHT,
                    claim_id=current["claim_id"],
                    inbound_event_id=inbound_event_id,
                )
            claim_id = secrets.token_hex(16)
            if current is None:
                if len(entries) >= MAX_REPLY_EVENTS:
                    return without_wake(plan, reason=REASON_REPLY_IN_FLIGHT, delivery=DELIVERY_IN_FLIGHT, claim_id=None)
                current = {
                    "event_id": inbound_event_id,
                    "state": "inflight",
                    "claim_id": claim_id,
                    "owner": owner,
                    "pid": pid,
                }
                entries.append(current)
            else:
                current["state"] = "inflight"
                current["claim_id"] = claim_id
                current["owner"] = owner
                current["pid"] = pid
            replies = _noted_ids(fresh, inbound_event_id)
            write_reply_hold(
                directory,
                delegation_id,
                inbound_event_id,
                {
                    "delegation_id": delegation_id,
                    "event_id": inbound_event_id,
                    "inbound_text": inbound_text,
                    "sender_public_key_hex": sender_public_key_hex,
                    "reply_to_message_id": reply_to_message_id,
                },
            )
            write_record(
                directory,
                update_record(fresh, reply_event_ids=replies, reply_deliveries=entries),
            )
    except ControlError:
        return without_wake(plan, reason=REASON_REPLY_IN_FLIGHT, delivery=DELIVERY_IN_FLIGHT, claim_id=None)
    return DelegationReplyPlan(
        kind=plan.kind,
        acknowledge_worker=plan.acknowledge_worker,
        reason=None,
        delegation_id=plan.delegation_id,
        worker=plan.worker,
        parent_text_present=plan.parent_text_present,
        report_to=plan.report_to,
        wake_text=plan.wake_text,
        suppress_worker_delivery=True,
        suppress_worker_error=True,
        claim_id=claim_id,
        delivery=DELIVERY_WAKE,
        inbound_event_id=inbound_event_id,
    )


def _noted_ids(record: Mapping[str, Any], inbound_event_id: str) -> list[str]:
    current = record.get("reply_event_ids")
    if not isinstance(current, list):
        return [inbound_event_id]
    ids = [item for item in current if isinstance(item, str)]
    if inbound_event_id in ids or len(ids) >= MAX_REPLY_EVENTS:
        return ids
    return [*ids, inbound_event_id]


def _entries(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = record.get("reply_deliveries")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _find(entries: list[dict[str, Any]], event_id: str) -> dict[str, Any] | None:
    for item in entries:
        if item.get("event_id") == event_id:
            return item
    return None


def _needs_recovery(entry: Mapping[str, Any], owner: str) -> bool:
    state = entry.get("state")
    if state == "pending":
        return True
    if state != "inflight":
        return False
    pid = entry.get("pid")
    if isinstance(pid, int) and not isinstance(pid, bool) and _pid_alive(pid):
        return False
    del owner
    return True


def _pid_alive(pid: object) -> bool:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _owner(value: str | None) -> str:
    if isinstance(value, str) and _OWNER_RE.fullmatch(value):
        return value
    return _PROCESS_OWNER


def _pid(value: int | None) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and 0 < value < 2**31:
        return value
    return os.getpid()


def _note_reply(directory: Path, record: Mapping[str, Any], inbound_event_id: str | None) -> None:
    if "reply_event_ids" not in record:
        return
    delegation_id = record.get("delegation_id")
    if not isinstance(delegation_id, str) or not isinstance(inbound_event_id, str):
        return
    if not _HEX64.fullmatch(inbound_event_id) or inbound_event_id == record.get("event_id"):
        return
    with exclusive_delegation(directory, delegation_id):
        fresh = read_record(directory, delegation_id)
        if fresh is None or fresh.get("state") != "accepted" or "reply_event_ids" not in fresh:
            return
        if fresh.get("event_id") != record.get("event_id"):
            return
        current = fresh.get("reply_event_ids")
        if not isinstance(current, list):
            return
        if inbound_event_id in current or len(current) >= MAX_REPLY_EVENTS:
            return
        write_record(
            directory,
            update_record(fresh, reply_event_ids=[*current, inbound_event_id]),
        )


def main(argv: list[str] | None = None, stdin: Any = None) -> int:
    """Read one inbound observation from stdin and print the plan."""
    args = list(sys.argv[1:] if argv is None else argv)
    source = sys.stdin.buffer if stdin is None else stdin
    try:
        if args:
            raise fail("invalid_request")
        raw = source.read(65537)
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > 65536:
            raise fail("invalid_request")
        try:
            payload = json.loads(bytes(raw).decode("utf-8"))
        except Exception:
            raise fail("invalid_request") from None
        if not isinstance(payload, dict) or any(key not in _REQUEST_KEYS for key in payload):
            raise fail("invalid_request")
        action = payload.get("action", "observe")
        if action not in _ACTIONS:
            raise fail("invalid_request")
        directory = resolve_journal_dir(_environ())
        if action == "recover":
            plans = recover_unfinished_replies(
                directory,
                gateway_owner=_optional_str(payload.get("gateway_owner")) if "gateway_owner" in payload else None,
                gateway_pid=_optional_pid(payload.get("gateway_pid")) if "gateway_pid" in payload else None,
            )
            sys.stdout.write(public_json({"kind": "recovery", "plans": [item.public_body() for item in plans]}))
            return 0
        if action in ("complete", "release"):
            delegation_id = payload.get("delegation_id")
            inbound_event_id = payload.get("inbound_event_id")
            claim_id = payload.get("claim_id")
            if not isinstance(delegation_id, str) or not isinstance(inbound_event_id, str) or not isinstance(claim_id, str):
                raise fail("invalid_request")
            recorded = (
                complete_reply_delivery(directory, delegation_id, inbound_event_id, claim_id)
                if action == "complete"
                else release_reply_claim(directory, delegation_id, inbound_event_id, claim_id)
            )
            if not recorded:
                raise fail("invalid_request")
            sys.stdout.write(public_json({"kind": "delivery_recorded", "delivery": action}))
            return 0
        for required in ("reply_to_message_id", "sender_public_key_hex", "inbound_text", "inbound_event_id"):
            if required not in payload:
                raise fail("invalid_request")
        inbound = payload.get("inbound_text")
        if not isinstance(inbound, str):
            raise fail("invalid_request")
        plan = evaluate_inbound_reply(
            directory,
            reply_to_message_id=_optional_str(payload.get("reply_to_message_id")),
            sender_public_key_hex=_optional_str(payload.get("sender_public_key_hex")),
            inbound_text=inbound,
            inbound_event_id=_optional_str(payload.get("inbound_event_id")),
            reply_to_text=_optional_str(payload.get("reply_to_text")) if "reply_to_text" in payload else None,
            gateway_owner=_optional_str(payload.get("gateway_owner")) if "gateway_owner" in payload else None,
            gateway_pid=_optional_pid(payload.get("gateway_pid")) if "gateway_pid" in payload else None,
        )
    except ControlError as exc:
        sys.stdout.write(public_json(exc.public_body()))
        return 1
    except Exception:
        sys.stdout.write(public_json(fail("internal_error").public_body()))
        return 1
    if plan.kind == KIND_NOT_DELEGATION_REPLY and plan.reason is None:
        sys.stdout.write(public_json(plan.public_body()))
        return 0
    sys.stdout.write(public_json(plan.public_body()))
    return 0


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise fail("invalid_request")
    return value


def _optional_pid(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise fail("invalid_request")
    return value


def _environ() -> dict[str, str]:
    import os

    return dict(os.environ)


if __name__ == "__main__":
    raise SystemExit(main())
