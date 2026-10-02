# Delegation round trip

Private Control–worker conversations stay private. A human receives
meaningful progress, decisions, approval requests, and evaluated
results in the conversation that asked for the work. A shared
human-supervised group is optional, not required.

The worker DM is the coordination channel. Answering inside it makes
the worker treat Control's reply as a new request. The local journal
links each private reply event to the human request. There is no task
viewer. The supported inspection command is:

```bash
fleet-delegation-show dlg_<32 lowercase hex>
```

It prints one JSON record from
`<profiles root>/<profile>/fleet-delegations/` (or
`FLEET_DELEGATION_JOURNAL_DIR` when that absolute override is set).
The record holds `task`, `origin_platform`, `origin_chat_id`,
`origin_session_key`, `worker`, `worker_public_key_hex`, `channel_id`,
`event_id`, and `reply_event_ids`. A routed record also holds
`origin_thread_id`, `origin_message_id`, `origin_chat_type`,
`origin_scope_id`, and `origin_user_id`. Records written before this
revision remain readable and are not backfilled.

## What Control does

`delegate_worker` reads the origin from the helper environment
`FLEET_CONTROL_ORIGIN_PLATFORM`, `FLEET_CONTROL_ORIGIN_CHAT_ID`, and
`FLEET_CONTROL_ORIGIN_SESSION_KEY`. When the gateway also supplies the
topic route, it reads `FLEET_CONTROL_ORIGIN_THREAD_ID`,
`FLEET_CONTROL_ORIGIN_MESSAGE_ID`, `FLEET_CONTROL_ORIGIN_CHAT_TYPE`,
`FLEET_CONTROL_ORIGIN_SCOPE_ID`, and `FLEET_CONTROL_ORIGIN_USER_ID`.
The MCP server sets those for one `fleet-delegate` process from
`_meta["hermes.fleet.origin"]` and deletes any inherited copy first.
The tool schema is still `worker`, `task`, and optional `delegation_id`.
A missing or non-messaging origin fails closed before the worker DM is
sent. An origin that is the worker DM itself fails closed after the DM
is opened and does not send.

The worker message stays `[fleet-delegation <id>]` plus the task. It
does not contain the human platform, chat id, or session key.

`fleet-delegation-intake` matches an inbound Buzz reply only when
`reply_to` is the stored event and the sender pubkey is the stored
worker key. A match suppresses worker delivery and worker error
notices. When the stored origin is usable, `wake_text` contains the
original task and the worker result, and `report_to` is that human
conversation. The first successful claim records `reply_deliveries` as
`inflight`. That is handed off: the origin adapter accepted the turn,
and the model has not produced a report yet. A later intake of a
`completed` reply returns `delivery: completed` and no `wake_text`. A
second concurrent intake sees the live claim and returns
`delivery: in_flight`, also with no wake. A mismatched sender or a
record with no origin suppresses the worker turn and does not guess a
destination. A different `reply_to` stays on the normal gateway path. A
further instruction is a new `delegate_worker` call, which sends a new
top-level DM with no `--reply-to`.

Three outcomes are distinct. Finishing the adapter session task does
not prove the human received the report.

- Handed off. The adapter accepted the turn. If the model fails before
  a report, or gateway shutdown cancels the turn before
  `send_final_ledgered` records an obligation, the claim returns to
  `pending` and the worker text stays in `reply-holds/`. Fleet recovery
  owns the next evaluation. The Hermes delivery ledger has nothing to
  redeliver.
- Report pending delivery. The model produced the report and
  `send_final_ledgered` stored it, then returned
  `SendResult(success=False)`. The journal is `completed` so the model
  is not run again. The Hermes delivery ledger owns redelivery,
  including its recovered-reply marker. `completed` here means "do not
  evaluate again," not "the human has the message."
- Delivered. The human send returned success. The journal is
  `completed`. A crash after that successful send and before the
  completion write can produce a second human report; that window is
  at-least-once.

If the human adapter is missing, or resume fails before the adapter
accepts the turn, the claim is released to `pending`. Recovery claims
that pending reply again. An `inflight` claim whose pid is no longer
running is recovered the same way. A live pid is not stolen. A
completed reply is not woken again. The worker DM is not used as the
retry path, so an interrupted handoff is not silently replaced by a
model turn in the worker conversation. If the ledger later abandons a
failed obligation, fleet recovery does not start another model turn.

## Hermes patch

The reviewable patch against Hermes
`7817bf522af3caf54b30ae59f16157469d7638fc` is
`patches/hermes-delegation-handoff/delegation-handoff.patch` in
hermes-fleet. This checkout does not fork Hermes. Installing these
helpers does not stop the reply loop.

`run_coroutine_threadsafe` copies the MCP loop's context, not the
gateway turn's. Reading `get_session_env` inside
`_call_tool_racing_stdio_death` is not sufficient: an unset ContextVar
falls back to `os.environ`, and the MCP loop never bound the turn.
The sync handler snapshots the turn ContextVars before the hop and
passes `meta={"hermes.fleet.origin": ...}` only for the configured
Fleet server's `delegate_worker` tool. The origin carries platform,
chat, session, thread or topic, reply anchor, chat type, scope, and
user id. Other MCP servers and ordinary worker gateways are unchanged.

The Buzz adapter calls `fleet-delegation-intake` only when
`HERMES_FLEET_CONTROL_INTEGRATION=1` and the event has a reply parent.
The sender is the inbound event's public key. The worker text is the
result inside `wake_text`. It is not parsed as a route, and the resumed
turn sets `allow_gateway_control` false so it cannot run a gateway
command. A successful correlation does not call `handle_message` on the
worker DM, does not send, and does not send a reaction or an error
notice. `report_to` resumes the stored session on that platform's
adapter, including the topic. `handle_message` derives the session key
and delivers the final text with that adapter's `send`.

Intake has two successful answers. `kind` `not_delegation_reply` is a
positive decision that the parent is not a stored delegation, and that
message keeps the existing dispatch. `kind` `delegation_reply` suppresses
the worker DM. A helper failure is neither of those answers. A missing
binary, timeout, non-zero exit, or unusable output means the correlation
service is unavailable. Reply-parent messages on this integration are
held and are not dispatched, reacted to, or given a worker error.
The hold directory is the helper journal directory, not the checkout:

- absolute `FLEET_DELEGATION_JOURNAL_DIR`: `<that directory>/unavailable-holds`
- otherwise: `<FLEET_CONTROL_PROFILES_ROOT or /home/hermes/.hermes/profiles>/<FLEET_CONTROL_HERMES_PROFILE>/fleet-delegations/unavailable-holds`

`HERMES_FLEET_CONTROL_ROOT` is only the directory that contains
`fleet-delegation-intake`. A root-owned checkout at
`/opt/hermes-fleet-control/<sha>` does not need a new owner. Top-level
messages, and every gateway that does not set
`HERMES_FLEET_CONTROL_INTEGRATION=1`, keep their normal path. Gateway
startup runs recovery immediately, then again every
`HERMES_FLEET_DELEGATION_RECOVERY_INTERVAL` seconds (default 30, clamped
to 0.05..300) until shutdown awaits the loop. A recovery pass already
in flight is not overlapped by the next tick or by another inbound
event. When intake is available again, a held reply is classified: a
positive unrelated reply is dispatched then, and a correlated reply
resumes the human session once. If the hold file cannot be written, the
message is still not dispatched in this process; recovery then depends
on the relay presenting that event again. Holds are capped at 64 files.

The patch adds `gateway/fleet_delegation.py` and anchored call sites,
marked `FLEET_DELEGATION_META`, `FLEET_DELEGATION_HANDOFF`, and
`FLEET_DELEGATION_RECOVERY` in gateway startup and shutdown. A Hermes
update that replaces those files drops the call sites. Reapply the
patch onto the pinned commit, or replay the hunks if the anchors still
match. `patches/hermes-delegation-handoff/check-anchors.py` fails when
an anchor is missing. Do not start the operator gateway on a tree where
the check fails.

## Deployment order

This document is not authorization to install, restart, or start a
gateway.

1. Install this hermes-fleet-control revision on Control. Leave the
   operator gateway stopped.
2. Apply the Hermes patch, set `HERMES_FLEET_CONTROL_INTEGRATION=1`,
   `HERMES_FLEET_MCP_SERVER`, and `HERMES_FLEET_CONTROL_ROOT`, and
   restart Hermes Control. Confirm `check-anchors.py` passes.
3. Confirm with `fleet-delegation-show` that a new record contains the
   task, origin, thread when the conversation has one, worker key, and
   event id, and that the worker DM body does not contain the origin.
4. Start the operator gateway only after that Hermes restart.

Starting operator before step 2 restores the reply loop. On
`7817bf522af3caf54b30ae59f16157469d7638fc` a worker reply is a normal DM
in `agent:main:buzz:dm:<worker-dm>:<delegation-event>`, and Control's
answer is published back into that thread.
