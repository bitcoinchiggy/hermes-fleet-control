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
`event_id`, and `reply_event_ids`. Records written before this revision
remain readable and are not backfilled.

## What Control does

`delegate_worker` reads the origin from the helper environment
`FLEET_CONTROL_ORIGIN_PLATFORM`, `FLEET_CONTROL_ORIGIN_CHAT_ID`, and
`FLEET_CONTROL_ORIGIN_SESSION_KEY`. The MCP server sets those for one
`fleet-delegate` process from `_meta["hermes.fleet.origin"]` and
deletes any inherited copy first. The tool schema is still `worker`,
`task`, and optional `delegation_id`. A missing or non-messaging origin
fails closed before the worker DM is sent. An origin that is the worker
DM itself fails closed after the DM is opened and does not send.

The worker message stays `[fleet-delegation <id>]` plus the task. It
does not contain the human platform, chat id, or session key.

`fleet-delegation-intake` matches an inbound Buzz reply only when
`reply_to` is the stored event and the sender pubkey is the stored
worker key. A match suppresses worker delivery and worker error
notices. When the stored origin is usable, `wake_text` contains the
original task and the worker result, and `report_to` is that human
conversation. A mismatched sender or a record with no origin suppresses
the worker turn and does not guess a destination. A different
`reply_to` stays on the normal gateway path. A further instruction is a
new `delegate_worker` call, which sends a new top-level DM with no
`--reply-to`.

## Required Hermes change

Deployed Hermes `7817bf522af3caf54b30ae59f16157469d7638fc` does not do
either of the following. Installing these helpers does not stop the
reply loop.

1. In `tools/mcp_tool_handlers.py`, `_call_tool_racing_stdio_death`
   calls `server.session.call_tool(tool_name, arguments=args)`.
   `mcp==2.0.0` accepts keyword-only `meta`. For the Fleet Control
   server's `delegate_worker` tool only, pass the current gateway
   ContextVars from `gateway.session_context.get_session_env`:

   ```python
   meta={
       "hermes.fleet.origin": {
           "platform": get_session_env("HERMES_SESSION_PLATFORM"),
           "chat_id": get_session_env("HERMES_SESSION_CHAT_ID"),
           "session_key": get_session_env("HERMES_SESSION_KEY"),
       }
   }
   ```

   Do not copy tool arguments into `_meta`. Do not attach this meta to
   other MCP servers. The long-lived MCP process does not see per-turn
   `HERMES_SESSION_*` updates in its own environment.

2. In `plugins/platforms/buzz/adapter.py`, before `_dispatch_message`,
   run `fleet-delegation-intake` with the observed reply parent, the
   event sender pubkey, the inbound text, the inbound event id, and
   `reply_to_text` when the cache has it. Use the managed interpreter
   from this checkout, not Hermes `python3`. Then:

   - A non-zero exit does not call `handle_message` and does not call
     `_notify_turn_error` (`gateway/platforms/base.py`).
   - `suppress_worker_delivery` true does not dispatch and does not send
     an error to the worker chat.
   - `report_to` set starts a turn in that platform, chat, and session
     with `wake_text` as the user message. The model's final text is
     delivered with that platform's adapter, not back into the worker DM.
   - `kind` `not_delegation_reply` keeps the existing dispatch.

## Deployment order

This document is not authorization to install, restart, or start a
gateway.

1. Install this hermes-fleet-control revision on Control. Leave the
   operator gateway stopped.
2. Patch and restart Hermes Control so `delegate_worker` receives the
   origin meta and the Buzz adapter runs `fleet-delegation-intake`
   before dispatch.
3. Confirm with `fleet-delegation-show` that a new record contains the
   task, origin, worker key, and event id, and that the worker DM body
   does not contain the origin.
4. Start the operator gateway only after that Hermes restart.

Starting operator before step 2 restores the reply loop. On
`7817bf522af3caf54b30ae59f16157469d7638fc` a worker reply is a normal DM
in `agent:main:buzz:dm:<worker-dm>:<delegation-event>`, and Control's
answer is published back into that thread.
