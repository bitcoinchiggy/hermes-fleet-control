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
`runtime/venv/bin/python -m pip install --require-virtualenv --require-hashes --only-binary=:all: -r requirements.lock`.
The lock pins `cryptography==50.0.2` and the transitive pins
`cffi==2.1.1` and `pycparser==3.0`, each with reviewed wheel hashes.
`requirements.txt` only records the direct pin. The command that worked
in the failure was `/usr/bin/python3.12`. Confirm that binary on the
host before using it. Do not point this at
`/home/hermes/.hermes/hermes-agent/venv`.

`fleet-mcp/index.js` execs `runtime/venv/bin/python` and passes
`fleet-delegate` as an argument. The shebang is ignored. If that
interpreter is missing, not absolute, or resolves into the Hermes agent
virtualenv, the tool returns `helper_failed`. It does not search
`PATH`. `FLEET_CONTROL_PYTHON` may replace the virtualenv path only
when it is an absolute interpreter outside the agent virtualenv.

A direct `./fleet-delegate` still starts through the shebang, then
re-execs the same managed interpreter before importing `cryptography`.
Membership is `sys.prefix` (and `pyvenv.cfg` in that prefix), not
`realpath` of the interpreter. A virtualenv `bin/python` is often a
symlink to the system binary, so equal realpaths do not mean this
process is inside the virtualenv. A path that is not a virtualenv fails
closed instead of being executed. That re-exec is a backstop. The
supported Hermes entry is the MCP launcher.

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
model. `fleet.yaml` does not govern Control. Replacing the profile list
with the fleet.yaml humans would drop extra existing human keys.
hermes-fleet only checks that fleet policy is not `allow_all_users` and
names the apply command. It does not emit a replacement allowlist.

The supported apply command is Control-local `fleet-allow-inbound`. It
is not an MCP tool. It reads the active profile, keeps every current
public key in order (extra existing human keys are preserved), and
appends `operator` then `researcher` when `buzz_npub` decodes to
`buzz_public_key_hex`. `allow_all_users` stays false. `BUZZ_PRIVATE_KEY`
is preserved and is not printed. A second run with the same keys does
not change the file. The command does not import a worker
key-derivation package, does not read worker private keys, does not
accept provisioner administration credentials, and does not use a guest
agent.

Reviewed steps, not performed by this change:

1. `python3 install-control-runtime --python /usr/bin/python3.12` after
   confirming that binary.
2. Capture
   `systemctl list-units 'hermes-gateway-*.service' --state=active --plain --no-legend`.
   Exactly one `hermes-gateway-<profile>.service` must be active. Do
   not assume the name. Set `FLEET_CONTROL_HERMES_PROFILE` to it.
3. GET `/v1/workers/operator` and GET `/v1/workers/researcher`. Pass
   those public documents, and the captured unit name, on stdin.
4. Run `fleet-allow-inbound`. It writes only that profile's `.env`.
5. Restart only that gateway unit when the result says `changed` is
   true. Run the command again and require `changed` false.

Stop if more than one profile gateway is active, if `allow_all_users`
is not false, if a worker `npub` does not match its public hex, or if
a previously authorized human key disappears.

The profile name `control` in this repository's tests is a fixture. It
is not evidence of the live gateway profile. Zero or several
`hermes-gateway-<profile>.service` units fail closed, and a generic
`hermes-gateway.service` does not count. `FLEET_CONTROL_HERMES_PROFILE`
has to name that same profile because delegation signs with its key.
