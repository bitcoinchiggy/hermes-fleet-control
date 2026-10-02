"""Correlate one inbound Buzz reply with the local delegation journal.

The Hermes gateway observes the reply parent and the sender pubkey.
Those values are arguments here. The reply text is not a route, and
this module does not send messages.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from fleet_control.delegation_reply import (
    KIND_NOT_DELEGATION_REPLY,
    DelegationReplyPlan,
    plan_delegation_reply,
    should_note_reply,
)
from fleet_control.errors import ControlError, fail
from fleet_control.journal import (
    MAX_REPLY_EVENTS,
    exclusive_delegation,
    iter_records,
    read_record,
    resolve_journal_dir,
    update_record,
    write_record,
)
from fleet_control.output import public_json

_REQUEST_KEYS = frozenset(
    {
        "reply_to_message_id",
        "sender_public_key_hex",
        "inbound_text",
        "inbound_event_id",
        "reply_to_text",
    }
)
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def evaluate_inbound_reply(
    directory: Path,
    *,
    reply_to_message_id: str | None,
    sender_public_key_hex: str | None,
    inbound_text: str,
    inbound_event_id: str | None,
    reply_to_text: str | None = None,
) -> DelegationReplyPlan:
    """Return the gateway plan and link a verified reply into the journal."""
    if not isinstance(reply_to_message_id, str) or not reply_to_message_id:
        return plan_delegation_reply(
            {},
            reply_to_message_id=None,
            reply_to_text=reply_to_text,
            inbound_text=inbound_text,
            sender_public_key_hex=sender_public_key_hex,
        )
    matches = [
        record
        for record in iter_records(directory)
        if record.get("event_id") == reply_to_message_id
    ]
    if not matches:
        return plan_delegation_reply(
            {},
            reply_to_message_id=reply_to_message_id,
            reply_to_text=reply_to_text,
            inbound_text=inbound_text,
            sender_public_key_hex=sender_public_key_hex,
        )
    if len(matches) != 1:
        return plan_delegation_reply(
            {"event_id": reply_to_message_id, "state": "accepted"},
            reply_to_message_id=reply_to_message_id,
            reply_to_text=reply_to_text,
            inbound_text=inbound_text,
            sender_public_key_hex=sender_public_key_hex,
        )
    record = matches[0]
    plan = plan_delegation_reply(
        record,
        reply_to_message_id=reply_to_message_id,
        reply_to_text=reply_to_text,
        inbound_text=inbound_text,
        sender_public_key_hex=sender_public_key_hex,
    )
    if should_note_reply(plan):
        _note_reply(directory, record, inbound_event_id)
    return plan


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
        for required in ("reply_to_message_id", "sender_public_key_hex", "inbound_text", "inbound_event_id"):
            if required not in payload:
                raise fail("invalid_request")
        inbound = payload.get("inbound_text")
        if not isinstance(inbound, str):
            raise fail("invalid_request")
        plan = evaluate_inbound_reply(
            resolve_journal_dir(_environ()),
            reply_to_message_id=_optional_str(payload.get("reply_to_message_id")),
            sender_public_key_hex=_optional_str(payload.get("sender_public_key_hex")),
            inbound_text=inbound,
            inbound_event_id=_optional_str(payload.get("inbound_event_id")),
            reply_to_text=_optional_str(payload.get("reply_to_text")) if "reply_to_text" in payload else None,
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


def _environ() -> dict[str, str]:
    import os

    return dict(os.environ)


if __name__ == "__main__":
    raise SystemExit(main())
