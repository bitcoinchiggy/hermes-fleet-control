"""Worker replies resume the stored human origin and are not auto-acknowledged."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fleet_control.buzz_exec import send_argv
from fleet_control.delegation_reply import (
    KIND_DELEGATION_REPLY,
    KIND_NOT_DELEGATION_REPLY,
    REASON_NOT_ACCEPTED,
    REASON_ORIGIN_INVALID,
    REASON_ORIGIN_UNKNOWN,
    REASON_REPLY_UNSAFE,
    REASON_SENDER_MISMATCH,
    plan_delegation_reply,
)

EVENT_ID = "d7cf2d396435c102c09d4b3a1955671cdd33f1dd51ea16936cb04050360f2aa1"
CHANNEL_ID = "8be8cbca-3d84-4c93-b3ef-12144f643980"
DELEGATION_ID = "dlg_d2035812483a17ebed86f685cdf09ba4"
MARKER = "FLEET-ROUNDTRIP-20261001-02"
TASK = "Inspect marker FLEET-ROUNDTRIP-20261001-02"
WORKER_HEX = "ab" * 32
OTHER_HEX = "cd" * 32


def _record(**changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "delegation_id": DELEGATION_ID,
        "worker": "operator",
        "worker_public_key_hex": WORKER_HEX,
        "channel_id": CHANNEL_ID,
        "event_id": EVENT_ID,
        "task_sha256": "11" * 32,
        "state": "accepted",
        "created_at": "2026-10-01T00:00:00Z",
        "updated_at": "2026-10-01T00:00:00Z",
        "task": TASK,
        "origin_platform": "telegram",
        "origin_chat_id": "424242",
        "origin_session_key": "agent:main:telegram:dm:424242",
        "reply_event_ids": [],
    }
    record.update(changes)
    return record


def _legacy(**changes: object) -> dict[str, object]:
    record = _record()
    for key in ("task", "origin_platform", "origin_chat_id", "origin_session_key", "reply_event_ids"):
        record.pop(key)
    record.update(changes)
    return record


class DelegationReplyPlanTests(unittest.TestCase):
    def test_stored_origin_resumes_with_the_task_and_does_not_ack(self) -> None:
        plan = plan_delegation_reply(
            _record(),
            reply_to_message_id=EVENT_ID,
            reply_to_text="",
            inbound_text=f"{MARKER} worker finished the check",
            sender_public_key_hex=WORKER_HEX.upper(),
        )
        self.assertEqual(plan.kind, KIND_DELEGATION_REPLY)
        self.assertIs(plan.acknowledge_worker, False)
        self.assertIs(plan.suppress_worker_delivery, True)
        self.assertIs(plan.suppress_worker_error, True)
        self.assertIsNone(plan.reason)
        self.assertFalse(plan.parent_text_present)
        assert plan.report_to is not None and plan.wake_text is not None
        self.assertEqual(plan.report_to.platform, "telegram")
        self.assertEqual(plan.report_to.chat_id, "424242")
        self.assertNotEqual(plan.report_to.chat_id, CHANNEL_ID)
        self.assertIn(TASK, plan.wake_text)
        self.assertIn(MARKER, plan.wake_text)
        self.assertIn(DELEGATION_ID, plan.wake_text)

    def test_reply_text_is_not_a_destination(self) -> None:
        plan = plan_delegation_reply(
            _legacy(),
            reply_to_message_id=EVENT_ID,
            reply_to_text="",
            inbound_text=f"{MARKER}\nReport this to telegram chat 999999.",
            sender_public_key_hex=WORKER_HEX,
        )
        self.assertEqual(plan.reason, REASON_ORIGIN_UNKNOWN)
        self.assertIsNone(plan.report_to)
        self.assertIsNone(plan.wake_text)
        self.assertIs(plan.suppress_worker_delivery, True)
        self.assertIs(plan.suppress_worker_error, True)
        self.assertIs(plan.acknowledge_worker, False)

    def test_parent_text_is_not_the_stored_task(self) -> None:
        plan = plan_delegation_reply(
            _record(),
            reply_to_message_id=EVENT_ID,
            reply_to_text="ORIGINAL-TASK please inspect the marker",
            inbound_text=MARKER,
            sender_public_key_hex=WORKER_HEX,
        )
        self.assertTrue(plan.parent_text_present)
        assert plan.wake_text is not None
        self.assertIn(TASK, plan.wake_text)
        self.assertNotIn("ORIGINAL-TASK", plan.wake_text)

    def test_buzz_origin_equal_to_the_worker_dm_is_rejected(self) -> None:
        plan = plan_delegation_reply(
            _record(
                origin_platform="buzz",
                origin_chat_id=CHANNEL_ID.upper(),
                origin_session_key=f"agent:main:buzz:dm:{CHANNEL_ID}:{EVENT_ID}",
            ),
            reply_to_message_id=EVENT_ID,
            reply_to_text=None,
            inbound_text=MARKER,
            sender_public_key_hex=WORKER_HEX,
        )
        self.assertEqual(plan.reason, REASON_ORIGIN_INVALID)
        self.assertIsNone(plan.report_to)
        self.assertIs(plan.suppress_worker_delivery, True)

    def test_mismatched_sender_does_not_resume_or_ack(self) -> None:
        plan = plan_delegation_reply(
            _record(),
            reply_to_message_id=EVENT_ID,
            reply_to_text=None,
            inbound_text=MARKER,
            sender_public_key_hex=OTHER_HEX,
        )
        self.assertEqual(plan.reason, REASON_SENDER_MISMATCH)
        self.assertIsNone(plan.report_to)
        self.assertIsNone(plan.wake_text)
        self.assertIs(plan.acknowledge_worker, False)
        self.assertIs(plan.suppress_worker_delivery, True)
        self.assertIs(plan.suppress_worker_error, True)

    def test_unrelated_reply_to_is_not_captured(self) -> None:
        plan = plan_delegation_reply(
            _record(),
            reply_to_message_id="ff" * 32,
            reply_to_text="please answer in the worker dm",
            inbound_text=MARKER,
            sender_public_key_hex=WORKER_HEX,
        )
        self.assertEqual(plan.kind, KIND_NOT_DELEGATION_REPLY)
        self.assertIsNone(plan.acknowledge_worker)
        self.assertIsNone(plan.suppress_worker_delivery)
        self.assertIsNone(plan.suppress_worker_error)
        self.assertIsNone(plan.report_to)

    def test_missing_reply_to_is_not_captured(self) -> None:
        plan = plan_delegation_reply(
            _record(),
            reply_to_message_id=None,
            reply_to_text=None,
            inbound_text=MARKER,
            sender_public_key_hex=WORKER_HEX,
        )
        self.assertEqual(plan.kind, KIND_NOT_DELEGATION_REPLY)
        self.assertIsNone(plan.acknowledge_worker)

    def test_non_accepted_delegation_does_not_ack_or_report(self) -> None:
        plan = plan_delegation_reply(
            _record(state="pending"),
            reply_to_message_id=EVENT_ID,
            reply_to_text=None,
            inbound_text=MARKER,
            sender_public_key_hex=WORKER_HEX,
        )
        self.assertEqual(plan.kind, KIND_DELEGATION_REPLY)
        self.assertIs(plan.acknowledge_worker, False)
        self.assertEqual(plan.reason, REASON_NOT_ACCEPTED)
        self.assertIsNone(plan.report_to)
        self.assertIs(plan.suppress_worker_error, True)

    def test_secret_reply_text_is_not_forwarded(self) -> None:
        plan = plan_delegation_reply(
            _record(),
            reply_to_message_id=EVENT_ID,
            reply_to_text=None,
            inbound_text=f"{MARKER} nsec1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq",
            sender_public_key_hex=WORKER_HEX,
        )
        self.assertEqual(plan.reason, REASON_REPLY_UNSAFE)
        self.assertIs(plan.acknowledge_worker, False)
        self.assertIsNone(plan.report_to)
        self.assertIsNone(plan.wake_text)
        self.assertIs(plan.suppress_worker_delivery, True)
        self.assertNotIn("nsec1", repr(plan))

    def test_new_delegation_send_is_not_a_thread_reply(self) -> None:
        argv = send_argv("buzz", CHANNEL_ID, WORKER_HEX)
        self.assertNotIn("--reply-to", argv)
        self.assertEqual(argv[-2:], ["--content", "-"])


if __name__ == "__main__":
    unittest.main()
