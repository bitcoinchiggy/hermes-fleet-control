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
task completion. A later worker reply is a separate Buzz turn.

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
or an extended private key, and it does not write profile files.

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

The MCP server execs `runtime/venv/bin/python` and passes the helper
script as an argument. A missing interpreter is `helper_failed`, not a
`PATH` search. Both upgrade breaks, and the inbound allowlist that
this repository does not apply, are recorded in
[docs/upgrade-breaks.md](docs/upgrade-breaks.md).

## Layout

`fleet-status`, `fleet-ensure`, and `fleet-delegate` are the CLI
helpers. Each inserts this checkout on `sys.path` and nothing else.
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
