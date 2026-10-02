# hermes-fleet-control

Control-side Fleet MCP integration. These helpers let Hermes Control
read worker status, ensure one worker, and delegate a task over Buzz.

| Tool | Behavior |
|---|---|
| `worker_status` | `GET /v1/workers` or `GET /v1/workers/{name}` |
| `ensure_worker` | `PUT /v1/workers/{name}/ensure` with `{}` |
| `delegate_worker` | Sign a Buzz direct message with Control's own key |

`delegate_worker` returns when the relay accepts the signed event.
`delivery` is `relay_accepted`. That is not worker execution and not
task completion. Private Control-worker exchanges stay in the worker
DM. The human receives the evaluated result in the originating
conversation.

The journal stores the task, the trusted origin, the worker identity,
and the accepted event. `fleet-delegation-show <delegation_id>` prints
that record. It is not a task viewer. The origin is copied from Hermes
MCP `_meta["hermes.fleet.origin"]` for that one call. The model payload
cannot set it, and it is not written into the worker message.
`fleet-delegation-intake` is what the patched gateway runs on an inbound
reply when `HERMES_FLEET_CONTROL_INTEGRATION=1`. A completed reply does
not wake Control again. If handoff stops before the human adapter
accepts the turn, the reply stays pending for recovery. Gateway startup
runs that recovery, then a bounded background retry until shutdown. An
unavailable intake holds reply-parent messages in the profile journal
directory (`/home/hermes/.hermes/profiles/<profile>/fleet-delegations/unavailable-holds`,
or `FLEET_DELEGATION_JOURNAL_DIR` when that absolute override is set),
not in the hermes-fleet-control checkout. A positive unrelated answer
still uses the normal path. Unpatched Hermes
`7817bf522af3caf54b30ae59f16157469d7638fc` does not call it, so that
gateway still delivers its reply into the worker DM. The reviewable
patch and the reapply check live in hermes-fleet at
`patches/hermes-delegation-handoff/`.
[docs/delegation-roundtrip.md](docs/delegation-roundtrip.md) records the
private-coordination decision, the Hermes change, and the deployment
order.

When Control reports that status to the human, it uses the worker's
plain name (`operator`), not `@operator`, unless that worker is a
member of the current Buzz conversation and the mention is intentional.
A human `@mention` that only identified the worker is input syntax and
is not echoed into a different conversation. The rule is
`skills/fleet-delegation/SKILL.md`, and the `delegate_worker` tool
description repeats it.

## Trust boundary

Hermes Control talks to workers through Buzz. Control signs its own
messages. The provisioner does not sign for Control. Worker private
keys are not read here. This package does not derive keys from a seed
or an extended private key. The delegation tools do not write profile
files. `fleet-allow-inbound` is a separate operator command, not an MCP
tool. It rewrites only `BUZZ_ALLOWED_USERS` on the one profile bound to
the active gateway, keeps every human key already there, and preserves
`BUZZ_PRIVATE_KEY`.

There is no generic `send_message` tool. The model may pass a worker
name, a task, and an optional delegation id. It cannot choose a
channel, a public key, or a relay.

The Buzz child receives only `PATH`, `BUZZ_PRIVATE_KEY`,
`BUZZ_RELAY_URL`, an optional `BUZZ_AUTH_TAG`, and safe locale
variables. The Fleet caller token stays in the Authorization header.
That child `PATH` does not select the helper interpreter.

## Helper runtime

`delegate_worker` imports `cryptography`. Hermes's `python3` is not a
stable place to import it: a Hermes update resolved `python3` to
Python 3.14 without that package, and the tool returned
`helper_failed`. Python 3.12 succeeded.

Create the managed virtualenv with an explicit interpreter. The
installer is standard library only. It does not install into the
`PATH` interpreter and it refuses Hermes's agent virtualenv:

```bash
python3 install-control-runtime --python /usr/bin/python3.12
```

That installs the hashed `requirements.lock` (`cryptography==50.0.2`,
`PyYAML==6.0.2`, `cffi==2.1.1`, `pycparser==3.0`) with `--require-hashes` and
`--only-binary=:all:`. The MCP server execs `runtime/venv/bin/python`
and passes the helper script as an argument. A missing interpreter is
`helper_failed`, not a `PATH` search. A direct helper re-execs that
same interpreter. Membership is `sys.prefix`, because `realpath` of
`bin/python` is often the system binary.

`fleet-allow-inbound` reads the active profile and adds verified
operator and researcher public keys without dropping extra existing
human keys. It is the Control apply command. Both upgrade breaks are
recorded in [docs/upgrade-breaks.md](docs/upgrade-breaks.md).

## Layout

`fleet-status`, `fleet-ensure`, `fleet-delegate`, and
`fleet-allow-inbound` are the CLI helpers. Each inserts this checkout
on `sys.path` and nothing else. `fleet-allow-inbound` is not registered
as an MCP tool.
`fleet-mcp/` is the stdio MCP server. `fleet_control/` is the Python
package. `fleet_control/support/` is the local name, env, profile-read,
redaction, and NIP-19 code those helpers need.

## Checks

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
cd fleet-mcp && npm ci --ignore-scripts && node --check index.js && node --check python-bin.js && node --test python-bin.test.js
```

Installing or restarting Control is a separate reviewed step. This
repository does not deploy itself.
