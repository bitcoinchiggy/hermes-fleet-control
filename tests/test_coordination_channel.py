"""New delegations can use one private channel without moving stored routes."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fleet_control.delegation_intake import complete_reply_delivery, evaluate_inbound_reply
from fleet_control.delegation_reply import (
    KIND_DELEGATION_REPLY,
    KIND_NOT_DELEGATION_REPLY,
    REASON_SENDER_MISMATCH,
    plan_delegation_reply,
)
from fleet_control.errors import ControlError
from fleet_control.journal import ensure_journal_dir, fresh_record, update_record, write_record
import tests.test_fleet_control_delegate as _delegate_mod

CONTROL_NSEC = _delegate_mod.CONTROL_NSEC
DM_ID = _delegate_mod.DM_ID
EVENT_ID = _delegate_mod.EVENT_ID
SUPPLIED_ID = _delegate_mod.SUPPLIED_ID
TASK = _delegate_mod.TASK
WORKER_HEX = _delegate_mod.WORKER_HEX

CHANNEL = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_HEX = "cd" * 32
RESULT_ID = "ef" * 32
LOOP_PARENT = "07" * 32


def _profile(root: Path, text: str) -> dict[str, str]:
    profile = root / "control"
    profile.mkdir(parents=True)
    (profile / "config.yaml").write_text(text, encoding="utf-8")
    return {
        "FLEET_CONTROL_HERMES_PROFILE": "control",
        "FLEET_CONTROL_PROFILES_ROOT": str(root),
        "FLEET_CONTROL_BUZZ_BIN": "/usr/local/bin/buzz",
        "FLEET_PROVISIONER_CALLER_TOKEN": "test-caller-token",
        "FLEET_CONTROL_ORIGIN_PLATFORM": "telegram",
        "FLEET_CONTROL_ORIGIN_CHAT_ID": "424242",
        "FLEET_CONTROL_ORIGIN_SESSION_KEY": "agent:main:telegram:dm:424242",
    }


class CoordinationChannelTests(unittest.TestCase):
    def setUp(self):
        self.host = _delegate_mod.DelegateTests()
        self.host.setUp()

    def tearDown(self):
        self.host.tearDown()

    def delegate(self, payload=None, **kwargs):
        return self.host.delegate(payload, **kwargs)

    def test_new_work_is_a_mentioned_channel_message_and_keeps_the_human_origin(self):
        env = _profile(Path(self.host.tmp.name) / "profiles", f"fleet:\n  coordination_channel_id: {CHANNEL}\n")
        result = self.delegate(environ=env)
        self.assertEqual(result["channel_id"], CHANNEL)
        self.assertEqual(len(self.host.buzz.calls), 1)
        argv = self.host.buzz.calls[0]["argv"]
        self.assertEqual(argv[1:3], ["messages", "send"])
        self.assertIn("--channel", argv)
        self.assertIn(CHANNEL, argv)
        self.assertIn("--mention", argv)
        self.assertIn(WORKER_HEX, argv)
        self.assertNotIn("dms", argv)
        stdin = self.host.buzz.calls[0]["stdin"].decode("utf-8")
        self.assertTrue(stdin.startswith("[fleet-delegation "))
        self.assertNotIn("nsec1", stdin.lower())
        self.assertNotIn("BUZZ_PRIVATE_KEY", stdin)
        self.assertNotIn(CONTROL_NSEC, stdin)
        record = json.loads((self.host.journal / f"{result['delegation_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(record["origin_platform"], "telegram")
        self.assertEqual(record["origin_chat_id"], "424242")
        self.assertEqual(record["channel_id"], CHANNEL)
        self.assertEqual(record["state"], "accepted")
        self.assertNotIn("nsec", json.dumps(record).lower())

    def test_invalid_channel_does_not_send(self):
        env = _profile(Path(self.host.tmp.name) / "profiles", "fleet:\n  coordination_channel_id: not-a-channel\n")
        with self.assertRaises(ControlError) as caught:
            self.delegate(environ=env)
        self.assertEqual(caught.exception.code, "coordination_channel_invalid")
        self.assertEqual(self.host.buzz.calls, [])

    def test_origin_inside_the_channel_is_rejected_before_send(self):
        env = _profile(Path(self.host.tmp.name) / "profiles", f"fleet:\n  coordination_channel_id: {CHANNEL}\n")
        env["FLEET_CONTROL_ORIGIN_PLATFORM"] = "buzz"
        env["FLEET_CONTROL_ORIGIN_CHAT_ID"] = CHANNEL
        env["FLEET_CONTROL_ORIGIN_SESSION_KEY"] = f"agent:main:buzz:channel:{CHANNEL}"
        with self.assertRaises(ControlError) as caught:
            self.delegate(environ=env)
        self.assertEqual(caught.exception.code, "origin_invalid")
        self.assertEqual(self.host.buzz.calls, [])

    def test_accepted_dm_record_is_not_moved_onto_the_channel(self):
        first = self.delegate({"worker": "operator", "task": TASK, "delegation_id": SUPPLIED_ID})
        self.assertEqual(first["channel_id"], DM_ID)
        calls = len(self.host.buzz.calls)
        env = _profile(Path(self.host.tmp.name) / "profiles", f"fleet:\n  coordination_channel_id: {CHANNEL}\n")
        second = self.delegate(
            {"worker": "operator", "task": TASK, "delegation_id": SUPPLIED_ID},
            environ=env,
        )
        self.assertEqual(second["channel_id"], DM_ID)
        self.assertEqual(second["event_id"], EVENT_ID)
        self.assertEqual(len(self.host.buzz.calls), calls)
        record = json.loads((self.host.journal / f"{SUPPLIED_ID}.json").read_text(encoding="utf-8"))
        self.assertEqual(record["origin_chat_id"], "424242")
        self.assertEqual(record["channel_id"], DM_ID)

    def test_pending_record_keeps_its_channel_and_origin(self):
        task_hash = hashlib.sha256(TASK.encode("utf-8")).hexdigest()
        record = fresh_record(
            delegation_id=SUPPLIED_ID,
            worker="operator",
            worker_public_key_hex=WORKER_HEX,
            task_sha256=task_hash,
            state="bound",
            task=TASK,
            origin_platform="telegram",
            origin_chat_id="424242",
            origin_session_key="agent:main:telegram:dm:424242",
        )
        record = update_record(record, state="pending", channel_id=DM_ID)
        ensure_journal_dir(self.host.journal)
        write_record(self.host.journal, record)
        env = _profile(Path(self.host.tmp.name) / "profiles", f"fleet:\n  coordination_channel_id: {CHANNEL}\n")
        with self.assertRaises(ControlError) as caught:
            self.delegate({"worker": "operator", "task": TASK, "delegation_id": SUPPLIED_ID}, environ=env)
        self.assertEqual(caught.exception.code, "delegation_ambiguous")
        self.assertEqual(self.host.buzz.calls, [])
        stored = json.loads((self.host.journal / f"{SUPPLIED_ID}.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["channel_id"], DM_ID)
        self.assertEqual(stored["origin_chat_id"], "424242")
        self.assertEqual(stored["state"], "ambiguous")


def _accepted(directory: Path) -> None:
    task = "Inspect the queue"
    record = fresh_record(
        delegation_id=SUPPLIED_ID,
        worker="operator",
        worker_public_key_hex=WORKER_HEX,
        task_sha256=hashlib.sha256(task.encode("utf-8")).hexdigest(),
        state="bound",
        task=task,
        origin_platform="telegram",
        origin_chat_id="424242",
        origin_session_key="agent:main:telegram:dm:424242",
    )
    write_record(
        directory,
        update_record(record, state="accepted", channel_id=CHANNEL, event_id=EVENT_ID),
    )


class ChannelReplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = Path(self.tmp.name) / "delegations"
        self.journal.mkdir(mode=0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_record_is_not_a_delegation(self):
        plan = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=LOOP_PARENT,
            sender_public_key_hex=WORKER_HEX,
            inbound_text="HTTP 402",
            inbound_event_id=RESULT_ID,
        )
        self.assertEqual(plan.kind, KIND_NOT_DELEGATION_REPLY)
        self.assertIsNone(plan.wake_text)
        self.assertIsNone(plan.report_to)

    def test_result_must_reply_to_the_assignment_from_the_recorded_worker(self):
        _accepted(self.journal)
        correlated = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=EVENT_ID,
            sender_public_key_hex=WORKER_HEX,
            inbound_text="queue is empty",
            inbound_event_id=RESULT_ID,
        )
        self.assertEqual(correlated.kind, KIND_DELEGATION_REPLY)
        self.assertIs(correlated.acknowledge_worker, False)
        self.assertEqual(correlated.report_to.chat_id, "424242")
        self.assertNotEqual(correlated.report_to.chat_id, CHANNEL)
        self.assertIsNotNone(correlated.wake_text)

        sibling = plan_delegation_reply(
            json.loads((self.journal / f"{SUPPLIED_ID}.json").read_text(encoding="utf-8")),
            reply_to_message_id=RESULT_ID,
            reply_to_text="queue is empty",
            inbound_text="evaluation",
            sender_public_key_hex=WORKER_HEX,
        )
        self.assertEqual(sibling.kind, KIND_NOT_DELEGATION_REPLY)

        forged = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=EVENT_ID,
            sender_public_key_hex=OTHER_HEX,
            inbound_text="forged result",
            inbound_event_id="12" * 32,
        )
        self.assertEqual(forged.reason, REASON_SENDER_MISMATCH)
        self.assertIsNone(forged.wake_text)
        self.assertIs(forged.suppress_worker_delivery, True)
        self.assertIs(forged.suppress_worker_error, True)

    def test_completed_result_does_not_wake_again(self):
        _accepted(self.journal)
        first = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=EVENT_ID,
            sender_public_key_hex=WORKER_HEX,
            inbound_text="queue is empty",
            inbound_event_id=RESULT_ID,
            gateway_pid=1,
        )
        self.assertIsNotNone(first.wake_text)
        self.assertTrue(
            complete_reply_delivery(self.journal, SUPPLIED_ID, RESULT_ID, first.claim_id or "")
        )
        second = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=EVENT_ID,
            sender_public_key_hex=WORKER_HEX,
            inbound_text="queue is empty",
            inbound_event_id=RESULT_ID,
            gateway_pid=1,
        )
        self.assertIsNone(second.wake_text)
        self.assertEqual(second.delivery, "completed")


if __name__ == "__main__":
    unittest.main()
