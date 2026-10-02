# Control upgrade breaks

Two uniform-version failures showed up together. They have different
fixes. Neither fix is pairing, `allow_all_users`, an ad-hoc package
install at request time, or polling the Buzz CLI.

## 1. `delegate_worker` returns `helper_failed`

The MCP launcher inherited Hermes's environment and spawned
`fleet-delegate` through `#!/usr/bin/env python3`. After a Hermes
update, that `python3` was Python 3.14, which does not have
`cryptography`. The helper imports `cryptography` and the tool returned
`helper_failed`. The same helper succeeded under Python 3.12.

The Buzz child pins `PATH` to `/usr/local/bin:/usr/bin:/bin`. That pin
applies only to the `buzz` process. It does not select the helper
interpreter.

The worker guest installer is a different path. It probes `python3` on
`PATH` and can install `python3-cryptography` with `apt-get`. Copying
that onto Control would follow the next Hermes interpreter change and
would install a dependency at the moment of use. Control does not do
that.

### Fix

A reviewed install creates one virtualenv for this checkout:

```bash
python3 install-control-runtime --python /usr/bin/python3.12
```

`install-control-runtime` is standard library only, so the `python3` on
`PATH` may start it. `--python` is required. It is the absolute
interpreter that runs `python -m venv runtime/venv` and then
`runtime/venv/bin/python -m pip install --require-virtualenv -r requirements.txt`.
The command that worked in the failure was `/usr/bin/python3.12`.
Confirm that binary on the host before using it. Do not point this at
`/home/hermes/.hermes/hermes-agent/venv`.

`fleet-mcp/index.js` execs `runtime/venv/bin/python` and passes
`fleet-delegate` as an argument. The shebang is ignored. If that
interpreter is missing, not absolute, or resolves into the Hermes agent
virtualenv, the tool returns `helper_failed`. It does not search
`PATH`. `FLEET_CONTROL_PYTHON` may replace the virtualenv path only
when it is an absolute interpreter outside the agent virtualenv.

A direct `./fleet-delegate` still starts through the shebang, then
re-execs the same managed interpreter before importing `cryptography`.
That re-exec is a backstop. The supported Hermes entry is the MCP
launcher.

## 2. Operator reply was unauthorized on Control's gateway

The operator answered with the exact test marker. Control's gateway
logged an unauthorized user and sent pairing challenges. A later CLI
poll observed the reply. That poll was not an inbound orchestration
turn.

`config/fleet.yaml` `buzz.allowed_users` is worker-guest policy. Fleet
`communicate` writes it onto worker profiles. It does not select
Control's active gateway profile and it does not write Control's
`.env`. The gateway that receives the worker's reply allows only the
public keys in that profile's `BUZZ_ALLOWED_USERS`. The worker's public
key was not among them.

Pairing, `allow_all_users`, and polling are not the authorization
model. The durable change is the planner in
`bitcoinchiggy/hermes-fleet`: keep the human keys, append the public
`buzz_public_key_hex` values for `operator` and `researcher`, leave
`allow_all_users` false, and apply that payload with
`hermes-buzz-runtime-apply` on the single active
`hermes-gateway-<profile>.service`. This repository does not contain
that planner and does not write allowlists.

The profile name `control` in this repository's tests is a fixture. It
is not evidence of the live gateway profile. Zero or several
`hermes-gateway-<profile>.service` units fail closed, and a generic
`hermes-gateway.service` does not count. `FLEET_CONTROL_HERMES_PROFILE`
has to name that same profile because delegation signs with its key.
