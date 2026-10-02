"""Helper-only test. Human to worker and back, using the real delegate and intake functions.

Buzz and Fleet are fakes. Nothing is sent to a relay. This module does not
import Hermes and does not exercise the gateway adapter.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fleet_control.delegation_inspect import show_delegation
from fleet_control.delegation_intake import (
    complete_reply_delivery,
    evaluate_inbound_reply,
    recover_unfinished_replies,
    release_reply_claim,
)
from fleet_control.delegate import delegate_worker
from fleet_control.errors import ControlError
from fleet_control.journal import fresh_record, read_record, update_record, write_record
from test_fleet_control_delegate import (
    EVENT_ID,
    FLEET_FILE,
    TASK,
    WORKER_HEX,
    Buzz,
    FleetHTTP,
    profile_bytes,
    public_worker,
    send_stdout,
)

FOLLOW_EVENT = "12" * 32
INBOUND_EVENT = "34" * 32
LEGACY_EVENT = "56" * 32
LEGACY_CHANNEL = "22222222-2222-4222-8222-222222222222"
RESULT = "operator finished the marker check"
ORIGIN_CHAT = "424242"
ORIGIN_SESSION = "agent:main:telegram:dm:424242"


class RoundtripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = Path(self.tmp.name) / "delegations"
        self.http = FleetHTTP(public_worker())
        self.buzz = Buzz()
        self.env = {
            "FLEET_CONTROL_HERMES_PROFILE": "control",
            "FLEET_CONTROL_BUZZ_BIN": "/usr/local/bin/buzz",
            "PATH": "/tmp/parent-path-must-not-leak",
            "LANG": "C.UTF-8",
            "FLEET_PROVISIONER_CALLER_TOKEN": "test-caller-token",
            "FLEET_CONTROL_ORIGIN_PLATFORM": "telegram",
            "FLEET_CONTROL_ORIGIN_CHAT_ID": ORIGIN_CHAT,
            "FLEET_CONTROL_ORIGIN_SESSION_KEY": ORIGIN_SESSION,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def delegate(self, payload=None, **kwargs):
        defaults = {
            "environ": self.env,
            "fleet_file_bytes": FLEET_FILE,
            "profile_env_bytes": profile_bytes(),
            "transport": self.http,
            "buzz_runner": self.buzz,
            "journal_dir": self.journal,
        }
        defaults.update(kwargs)
        return delegate_worker(payload if payload is not None else {"worker": "operator", "task": TASK}, **defaults)

    def test_human_control_worker_control_human_survives_restart(self) -> None:
        receipt = self.delegate()
        sent = self.buzz.calls[1]
        self.assertNotIn("--reply-to", sent["argv"])
        stdin = sent["stdin"].decode()
        self.assertEqual(stdin, f"[fleet-delegation {receipt['delegation_id']}]\n{TASK}")
        self.assertNotIn(ORIGIN_CHAT, stdin)
        self.assertNotIn(ORIGIN_SESSION, stdin)
        self.assertNotIn("telegram", stdin)

        resumed = self._resume_after_restart(receipt["event_id"], RESULT, INBOUND_EVENT)
        self.assertEqual(resumed["delivery"], "wake")
        self.assertEqual(resumed["chat_id"], ORIGIN_CHAT)
        self.assertEqual(resumed["session_key"], ORIGIN_SESSION)
        self.assertIs(resumed["suppress_worker_delivery"], True)
        self.assertIs(resumed["suppress_worker_error"], True)
        self.assertIs(resumed["acknowledge_worker"], False)
        self.assertIn(TASK, resumed["wake"])
        self.assertIn(RESULT, resumed["wake"])
        self.assertNotIn(ORIGIN_CHAT, resumed["wake"])
        self.assertTrue(
            complete_reply_delivery(self.journal, receipt["delegation_id"], INBOUND_EVENT, resumed["claim_id"])
        )

        stored = read_record(self.journal, receipt["delegation_id"])
        assert stored is not None
        self.assertEqual(stored["reply_event_ids"], [INBOUND_EVENT])
        self.assertEqual(stored["reply_deliveries"][0]["state"], "completed")
        self.assertNotIn("origin_thread_id", stored)
        self.assertEqual(stored["worker_public_key_hex"], WORKER_HEX)
        self.assertEqual(stored["event_id"], receipt["event_id"])
        shown = show_delegation(self.journal, receipt["delegation_id"])
        self.assertEqual(shown["task"], TASK)
        self.assertEqual(shown["origin_chat_id"], ORIGIN_CHAT)
        self.assertEqual(shown["reply_event_ids"], [INBOUND_EVENT])
        self.assertEqual(shown["reply_deliveries"][0]["state"], "completed")
        self.assertNotIn("task viewer", json.dumps(shown))

        again = self._resume_after_restart(receipt["event_id"], RESULT, INBOUND_EVENT)
        self.assertEqual(again["delivery"], "completed")
        self.assertIsNone(again["wake"])
        self.assertIs(again["suppress_worker_delivery"], True)
        self.assertEqual(read_record(self.journal, receipt["delegation_id"])["reply_event_ids"], [INBOUND_EVENT])

    def test_concurrent_intake_wakes_once_and_a_dead_owner_can_be_recovered(self) -> None:
        receipt = self.delegate()
        owner = "ab" * 16
        pid = os.getpid()
        barrier = threading.Barrier(2)
        found: list = []

        def once() -> None:
            barrier.wait(5)
            found.append(
                evaluate_inbound_reply(
                    self.journal,
                    reply_to_message_id=receipt["event_id"],
                    sender_public_key_hex=WORKER_HEX,
                    inbound_text=RESULT,
                    inbound_event_id=INBOUND_EVENT,
                    gateway_owner=owner,
                    gateway_pid=pid,
                )
            )

        threads = [threading.Thread(target=once), threading.Thread(target=once)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
        wakes = [plan for plan in found if plan.delivery == "wake"]
        inflight = [plan for plan in found if plan.delivery == "in_flight"]
        self.assertEqual(len(wakes), 1)
        self.assertEqual(len(inflight), 1)
        self.assertIsNone(inflight[0].wake_text)
        self.assertIs(inflight[0].suppress_worker_delivery, True)
        self.assertEqual(read_record(self.journal, receipt["delegation_id"])["reply_event_ids"], [INBOUND_EVENT])
        stolen = recover_unfinished_replies(self.journal, gateway_owner="cd" * 16, gateway_pid=pid)
        self.assertEqual(stolen, [])

        dead = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], check=True, capture_output=True, text=True)
        dead_pid = int(dead.stdout.strip())
        release_reply_claim(self.journal, receipt["delegation_id"], INBOUND_EVENT, wakes[0].claim_id)
        crashed = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=receipt["event_id"],
            sender_public_key_hex=WORKER_HEX,
            inbound_text=RESULT,
            inbound_event_id=INBOUND_EVENT,
            gateway_owner="ef" * 16,
            gateway_pid=dead_pid,
        )
        self.assertEqual(crashed.delivery, "wake")
        recovered = recover_unfinished_replies(self.journal, gateway_owner="12" * 16, gateway_pid=pid)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].delivery, "wake")
        self.assertIn(RESULT, recovered[0].wake_text or "")
        self.assertIn(TASK, recovered[0].wake_text or "")
        again = recover_unfinished_replies(self.journal, gateway_owner="34" * 16, gateway_pid=pid)
        self.assertEqual(again, [])
        self.assertTrue(
            complete_reply_delivery(self.journal, receipt["delegation_id"], INBOUND_EVENT, recovered[0].claim_id)
        )
        quiet = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=receipt["event_id"],
            sender_public_key_hex=WORKER_HEX,
            inbound_text=RESULT,
            inbound_event_id=INBOUND_EVENT,
            gateway_owner=owner,
            gateway_pid=pid,
        )
        self.assertEqual(quiet.delivery, "completed")
        self.assertIsNone(quiet.wake_text)
        self.assertIs(quiet.suppress_worker_delivery, True)

    def test_missing_adapter_release_is_recovered_once(self) -> None:
        receipt = self.delegate()
        plan = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=receipt["event_id"],
            sender_public_key_hex=WORKER_HEX,
            inbound_text=RESULT,
            inbound_event_id=INBOUND_EVENT,
        )
        self.assertEqual(plan.delivery, "wake")
        self.assertTrue(release_reply_claim(self.journal, receipt["delegation_id"], INBOUND_EVENT, plan.claim_id or ""))
        stored = read_record(self.journal, receipt["delegation_id"])
        assert stored is not None
        self.assertEqual(stored["reply_deliveries"][0]["state"], "pending")
        duplicate = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=receipt["event_id"],
            sender_public_key_hex=WORKER_HEX,
            inbound_text=RESULT,
            inbound_event_id=INBOUND_EVENT,
        )
        self.assertEqual(duplicate.delivery, "wake")
        self.assertTrue(
            complete_reply_delivery(self.journal, receipt["delegation_id"], INBOUND_EVENT, duplicate.claim_id or "")
        )
        done = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=receipt["event_id"],
            sender_public_key_hex=WORKER_HEX,
            inbound_text=RESULT,
            inbound_event_id=INBOUND_EVENT,
        )
        self.assertEqual(done.delivery, "completed")
        self.assertIsNone(done.wake_text)

    def test_topic_origin_is_stored_and_kept_out_of_the_worker_message(self) -> None:
        env = dict(self.env)
        env.update(
            {
                "FLEET_CONTROL_ORIGIN_THREAD_ID": "99",
                "FLEET_CONTROL_ORIGIN_MESSAGE_ID": "555",
                "FLEET_CONTROL_ORIGIN_CHAT_TYPE": "dm",
                "FLEET_CONTROL_ORIGIN_SCOPE_ID": "",
                "FLEET_CONTROL_ORIGIN_USER_ID": "42",
                "FLEET_CONTROL_ORIGIN_SESSION_KEY": "agent:main:telegram:dm:424242:99",
            }
        )
        receipt = self.delegate(environ=env)
        stdin = self.buzz.calls[1]["stdin"].decode()
        self.assertEqual(stdin, f"[fleet-delegation {receipt['delegation_id']}]\n{TASK}")
        self.assertNotIn("424242", stdin)
        stored = read_record(self.journal, receipt["delegation_id"])
        assert stored is not None
        self.assertEqual(stored["origin_thread_id"], "99")
        self.assertEqual(stored["origin_message_id"], "555")
        self.assertEqual(stored["origin_chat_type"], "dm")
        self.assertEqual(stored["origin_user_id"], "42")
        plan = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=receipt["event_id"],
            sender_public_key_hex=WORKER_HEX,
            inbound_text=RESULT,
            inbound_event_id=INBOUND_EVENT,
        )
        assert plan.report_to is not None
        self.assertEqual(plan.report_to.thread_id, "99")
        self.assertEqual(plan.report_to.message_id, "555")
        self.assertEqual(plan.report_to.chat_type, "dm")
        self.assertIn(RESULT, plan.wake_text or "")
        self.assertNotIn("999", plan.wake_text or "")

    def test_mismatched_sender_and_unknown_origin_do_not_guess(self) -> None:
        receipt = self.delegate()
        mismatch = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=receipt["event_id"],
            sender_public_key_hex="cd" * 32,
            inbound_text="deliver this to telegram chat 999999",
            inbound_event_id="78" * 32,
        )
        self.assertEqual(mismatch.reason, "sender_mismatch")
        self.assertIsNone(mismatch.report_to)
        self.assertIsNone(mismatch.wake_text)
        self.assertIs(mismatch.suppress_worker_delivery, True)
        self.assertIs(mismatch.suppress_worker_error, True)
        self.assertIs(mismatch.acknowledge_worker, False)
        self.assertEqual(read_record(self.journal, receipt["delegation_id"])["reply_event_ids"], [])

        legacy_id = "dlg_" + "ab" * 16
        record = fresh_record(
            delegation_id=legacy_id,
            worker="operator",
            worker_public_key_hex=WORKER_HEX,
            task_sha256="11" * 32,
            state="accepted",
        )
        record = update_record(record, channel_id=LEGACY_CHANNEL, event_id=LEGACY_EVENT)
        write_record(self.journal, record)
        unknown = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=LEGACY_EVENT,
            sender_public_key_hex=WORKER_HEX,
            inbound_text="please reply in chat 999999",
            inbound_event_id="90" * 32,
        )
        self.assertEqual(unknown.reason, "origin_unknown")
        self.assertIsNone(unknown.report_to)
        self.assertIs(unknown.suppress_worker_delivery, True)
        self.assertIs(unknown.acknowledge_worker, False)
        self.assertNotIn("origin_chat_id", read_record(self.journal, legacy_id))

    def test_unrelated_dm_stays_on_the_normal_path(self) -> None:
        receipt = self.delegate()
        plan = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id="ff" * 32,
            sender_public_key_hex=WORKER_HEX,
            inbound_text="hello from another conversation",
            inbound_event_id="a1" * 32,
        )
        self.assertEqual(plan.kind, "not_delegation_reply")
        self.assertIsNone(plan.acknowledge_worker)
        self.assertIsNone(plan.suppress_worker_delivery)
        self.assertIsNone(plan.suppress_worker_error)
        self.assertIsNone(plan.report_to)
        self.assertEqual(read_record(self.journal, receipt["delegation_id"])["reply_event_ids"], [])

    def test_follow_up_delegation_is_a_new_top_level_send(self) -> None:
        first = self.delegate()
        self.buzz = Buzz(send=(0, send_stdout(event_id=FOLLOW_EVENT)))
        second = self.delegate({"worker": "operator", "task": "Ask operator for the log excerpt"})
        self.assertNotEqual(second["delegation_id"], first["delegation_id"])
        self.assertEqual(second["event_id"], FOLLOW_EVENT)
        sent = self.buzz.calls[1]
        self.assertNotIn("--reply-to", sent["argv"])
        self.assertNotIn(first["event_id"], sent["stdin"].decode())
        self.assertNotIn(ORIGIN_SESSION, sent["stdin"].decode())
        follow = evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=FOLLOW_EVENT,
            sender_public_key_hex=WORKER_HEX,
            inbound_text="the excerpt is empty",
            inbound_event_id="b2" * 32,
        )
        assert follow.report_to is not None and follow.wake_text is not None
        self.assertEqual(follow.report_to.chat_id, ORIGIN_CHAT)
        self.assertIn("Ask operator for the log excerpt", follow.wake_text)
        self.assertIs(follow.acknowledge_worker, False)
        self.assertIs(follow.suppress_worker_delivery, True)

    def test_missing_or_worker_dm_origin_does_not_send(self) -> None:
        env = dict(self.env)
        for key in (
            "FLEET_CONTROL_ORIGIN_PLATFORM",
            "FLEET_CONTROL_ORIGIN_CHAT_ID",
            "FLEET_CONTROL_ORIGIN_SESSION_KEY",
        ):
            env.pop(key)
        with self.assertRaises(ControlError) as caught:
            self.delegate(environ=env)
        self.assertEqual(caught.exception.code, "origin_unavailable")
        self.assertEqual(self.buzz.calls, [])

        poisoned = dict(self.env)
        poisoned["FLEET_CONTROL_ORIGIN_PLATFORM"] = "cli"
        with self.assertRaises(ControlError) as caught:
            self.delegate(environ=poisoned)
        self.assertEqual(caught.exception.code, "origin_unavailable")
        self.assertEqual(self.buzz.calls, [])

        worker_dm = dict(self.env)
        worker_dm["FLEET_CONTROL_ORIGIN_PLATFORM"] = "buzz"
        worker_dm["FLEET_CONTROL_ORIGIN_CHAT_ID"] = "11111111-1111-4111-8111-111111111111"
        worker_dm["FLEET_CONTROL_ORIGIN_SESSION_KEY"] = (
            "agent:main:buzz:dm:11111111-1111-4111-8111-111111111111"
        )
        with self.assertRaises(ControlError) as caught:
            self.delegate(environ=worker_dm)
        self.assertEqual(caught.exception.code, "origin_invalid")
        self.assertEqual(
            [call["argv"][1:3] for call in self.buzz.calls],
            [["dms", "open"]],
        )

    def test_show_command_prints_the_linked_record(self) -> None:
        receipt = self.delegate()
        evaluate_inbound_reply(
            self.journal,
            reply_to_message_id=receipt["event_id"],
            sender_public_key_hex=WORKER_HEX,
            inbound_text=RESULT,
            inbound_event_id=INBOUND_EVENT,
        )
        venv = Path(self.tmp.name) / "show-venv"
        subprocess.run(
            [sys.executable, "-m", "venv", "--system-site-packages", str(venv)],
            check=True,
            capture_output=True,
        )
        python = venv / "bin" / "python"
        real = os.path.realpath(sys.executable)
        if os.path.realpath(python) != real:
            python.unlink()
            python.symlink_to(real)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin"),
            "HOME": self.tmp.name,
            "FLEET_CONTROL_PYTHON": str(python),
            "FLEET_DELEGATION_JOURNAL_DIR": str(self.journal),
        }
        proc = subprocess.run(
            [sys.executable, str(REPO / "fleet-delegation-show"), receipt["delegation_id"]],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        shown = json.loads(proc.stdout)
        self.assertEqual(shown["task"], TASK)
        self.assertEqual(shown["origin_session_key"], ORIGIN_SESSION)
        self.assertEqual(shown["reply_event_ids"], [INBOUND_EVENT])
        self.assertNotIn("viewer", proc.stdout)

    def _resume_after_restart(self, event_id: str, inbound: str, inbound_event: str) -> dict:
        code = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "from fleet_control.delegation_intake import evaluate_inbound_reply\n"
            "plan = evaluate_inbound_reply(\n"
            "    Path(sys.argv[1]),\n"
            "    reply_to_message_id=sys.argv[2],\n"
            "    sender_public_key_hex=sys.argv[3],\n"
            "    inbound_text=sys.argv[4],\n"
            "    inbound_event_id=sys.argv[5],\n"
            ")\n"
            "destination = plan.report_to\n"
            "json.dump({\n"
            "    'chat_id': None if destination is None else destination.chat_id,\n"
            "    'session_key': None if destination is None else destination.session_key,\n"
            "    'suppress_worker_delivery': plan.suppress_worker_delivery,\n"
            "    'suppress_worker_error': plan.suppress_worker_error,\n"
            "    'acknowledge_worker': plan.acknowledge_worker,\n"
            "    'wake': plan.wake_text,\n"
            "    'reason': plan.reason,\n"
            "    'delivery': plan.delivery,\n"
            "    'claim_id': plan.claim_id,\n"
            "    'delegation_id': plan.delegation_id,\n"
            "}, sys.stdout)\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO)
        proc = subprocess.run(
            [sys.executable, "-c", code, str(self.journal), event_id, WORKER_HEX, inbound, inbound_event],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)


if __name__ == "__main__":
    unittest.main()
