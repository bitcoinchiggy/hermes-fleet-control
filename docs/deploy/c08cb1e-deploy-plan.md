# Guarded Control deploy for c08cb1e

Operator commands for `c08cb1ebd073ee7946f49005dd45071366eeb688`.
Writing this page did not deploy, restart, SSH, open a pull request, or
contact a host. Do not paste evidence, a unit dump, or an env file into
chat. Output is key names, paths, worker names, and checksums. Secret
values are not printed.

The commands live in this branch's `docs/deploy/`. They are not in the
`dcb3f950` tree or the `c08cb1e` tree. Copy this `docs/deploy/` directory
onto the host that will run the command. Do not take the helpers from
the checkout being deployed. Run the commands from the directory that
contains that copied `docs/deploy/` folder, so the paths below resolve.
The scripts are mode `0755`. `c08cb1e_material.py` starts with
`#!/usr/bin/python3.12`. The shell wrappers that call it require that
interpreter and stop if it is missing. The helper uses the Python
standard library, not the agent virtualenv. `qm`, `flock`, `git`,
`systemctl`, `node`, and `npm` are required only by the commands that
name them.

Stop at the first non-zero exit. Steps 1–9 deploy. Steps 10–13 roll
back. A successful deploy stops after step 9. A later step is not a
repair. Re-running records a baseline once, refuses to replace it, and
skips a restart that already reached the revision it checks. It does
not delete journals, reservations, tombstones, profile files, or the
stable checkout.

## Pins

Deploy `c08cb1ebd073ee7946f49005dd45071366eeb688`, tree
`2b8888b984634b714d62646ddd5b6f48d073d160`, directory
`/opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688`.
Stable `dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a`, tree
`3d5f940738c5d1c0061645d06e74d3f88b034ae5`, the single
`/opt/hermes-fleet-control/dcb3f950*` directory. Provisioner
`b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb`. Unit
`hermes-gateway-control.service`. New drop-in `fleet-retirement.conf`
does not edit `fleet-delegation.conf`. Interpreter
`/usr/bin/python3.12`, outside
`/home/hermes/.hermes/hermes-agent/venv`. Lock `cryptography==50.0.2`,
`PyYAML==6.0.2`.

`c08cb1e` is `63099c4` plus `docs/control-onboard-validation.md`
(commit `5868856`, 64 insertions, 12 deletions). `dcb3f950` is an
ancestor of `c08cb1e` and not of `63099c4`. `git diff dcb3f950 c08cb1e`
is 16 files, 2739 insertions, 25 deletions. The running change is
`onboard_worker`, `retire_worker`, and the onboarding-journal gate in
`delegate_worker`. This procedure never calls those tools or
`ensure_worker`.

`onboard_worker` POSTs `{}` once for a name the provisioner already
declares, after a reservation under `fleet-onboarding` or
`FLEET_ONBOARD_JOURNAL_DIR`. A later call reads status and does not
submit again. `retire_worker` stores the binding, then POSTs one
deprovision. The default body is `{}`. `confirm_retained: true` is a
separate call. `retry: true` does not repeat a reserved or ambiguous
attempt. The tools do not delete reservations, delegation journals, or
tombstones. `delegate_worker` rejects a public onboarding journal that
lacks `status: complete` or a valid `onb_` id. No journal keeps the
previous checks.

## Agent commit e29f306c

Checked on `bitcoinchiggy/hermes-agent` only. `NousResearch/hermes-agent`
was not queried. The earlier claim that
`e29f306cdbc7728f297d218be6ecda511bcf450a` is on that upstream and reads
MCP `command`, `args`, and `cwd` does not match the fork.

- It is the tip of branch `fleet`. Parent
  `6b208cf543923b059159788063da33601de419e4`. It is not on `main`,
  `cursor/fleet-coordination-channel-9cef`,
  `cursor/fleet-hermes-integration-898a`, or
  `cursor/fleet-hermes-pin-898a`.
- The same patch (`git patch-id`
  `fadaab30e1941d0f7c3fc4deea321bee9c9afae1`) is
  `b1780240c9d93129c63674b712c5e067c69e81a0` on the coordination branch
  (tip `46762a638c4639fbd3dd3ba963141f1f6ac22666`). The integration and
  pin branches both tip at `bb8dc76cac8a365b73ce2630fd1b631adb8219b7`,
  the merge-base of `fleet` and that branch, and an ancestor of both
  commits.
- The patch does not touch MCP loading. Intake uses
  `build_subprocess_env(strip_launch_profile=True)`. Coordination config
  uses `load_user_config_effective(..., fail_closed=True, reject_non_mapping=True)`.
  Files: `gateway/buzz_recovery_quarantine.py`,
  `gateway/fleet_coordination.py`, `gateway/fleet_delegation.py`,
  `hermes_cli/config_effective.py`, and the two matching tests.
- On the `fleet` tip, stdio MCP still reads `command`, `cwd`, and
  `args` from profile `config.yaml` in `tools/mcp_tool_transport.py`
  (`_stdio_launch`, and `config.get("args", [])` at the spawn).
  `_stdio_launch` is also on the coordination branch. That reader is
  not in the `e29f306c` diff. Step 5 rewrites only those fields. This
  procedure does not change the agent checkout.

The running Control agent revision was not read.

## What NRestarts measures

`NRestarts` counts automatic restarts caused by the unit `Restart=`
policy after an unclean exit. A manual `systemctl restart` does not
increment it. A successful manual restart can leave `NRestarts` at 0.
The restart commands print the value and this sentence. They do not
require it to increase. Health is `ActiveState=active` and
`SubState=running`. Identity is a new `MainPID` whose environment
`HERMES_FLEET_CONTROL_ROOT` is the checkout that step is checking,
with `FLEET_CONTROL_PYTHON` unset, plus the expected drop-ins.

## Assumptions

Not read from a host. Commands stop when a check fails.

- Three machines. System unit if it is the only one loaded and the
  paste runs as root; user unit if it is the only one loaded. Stop if
  both or neither are loaded. No SSH.
- Process environment, not only the unit text:
  `HERMES_FLEET_CONTROL_ROOT` on the checkout that step expects,
  `HERMES_FLEET_CONTROL_INTEGRATION=1`, `FLEET_CONTROL_PYTHON` unset.
- `fleet-delegation.conf` is loaded. No drop-in name sorts after
  `fleet-retirement.conf`. The earlier temporary retirement drop-in is
  already gone.
- The Fleet MCP entry named by `HERMES_FLEET_MCP_SERVER` has the stable
  prefix in `command`, `args`, or `cwd`, or it uses
  `${HERMES_FLEET_CONTROL_ROOT}`. Any other stable-path occurrence stops
  step 5. Arbitrary MCP argument strings are not printed.
- Control journal dirs are the directories the deployed loaders use:
  `FLEET_DELEGATION_JOURNAL_DIR` or
  `<profiles>/<profile>/fleet-delegations`,
  `FLEET_ONBOARD_JOURNAL_DIR` or `fleet-onboarding`, and
  `FLEET_RETIRE_JOURNAL_DIR` or `fleet-retirements`. They are
  non-empty and private. The manifest stores checksums and modes, not
  file bodies.
- Provisioner state comes from the deployed `resolve_state_dir` loader
  on the running checkout. Journals are `onboarding/<name>.json`.
  Tombstones are `tombstones/<name>.json`. A filename search is not
  used. Bodies are not printed.
- Provisioner `FLEET_PROVISIONER_GIT_REF` is absent. Exactly one active
  unit whose name contains `provisioner`, or is `hermes-fleet.service`
  or `fleet-provisioner.service`, and `tombstones/` has at least one
  json file.
- Node is 20 or newer. A second paste skips `npm ci` and
  `install-control-runtime` when the import and `npm ls` already match.
- Control evidence:
  `/var/lib/hermes-control-deploy/c08cb1ebd073ee7946f49005dd45071366eeb688`
  as root, else
  `$HOME/.local/state/hermes-control-deploy/c08cb1ebd073ee7946f49005dd45071366eeb688`.
  The Provisioner witness and the guest-node witness are host mutations
  under `/var/lib/hermes-control-deploy/`, run as root. They are not
  read-only diagnostics and they are not profile journals. The files
  each command creates are listed under Host filesystem writes.

## Open questions

`c08cb1e-preflight.sh` answers these on the Control host. It does not
see the other machines. `not-on-this-host` stays open until steps 2
and 3.

Exit 0 means `diagnostic=completed` and `host-ready=yes`. Exit 4 means
`diagnostic=completed` and `host-ready=no`. Exit 4 is not a crash and
it is not a pass: a missing or unknown prerequisite did not pass. Do
not start step 1 unless the exit is 0. Preflight prints `read-only=yes`
and does not create files. A value printed as `redacted` is safe
diagnostic output. It is not proof that the hidden configuration is
correct, and it does not make the host ready.

1. Hostnames, and are the three roles separate?
2. Is `hermes-gateway-control.service` a system unit or a user unit?
3. Is the stable directory the full `dcb3f950…` name, and is
   `fleet-delegation.conf` still the last loaded drop-in?
4. Absolute MCP checkout paths, or `${HERMES_FLEET_CONTROL_ROOT}`?
   `host-ready=yes` requires `command` and `cwd` to be an absolute
   checkout path or `${HERMES_FLEET_CONTROL_ROOT}`, and every argument
   to be absent, one of `node`, `npm`, `python3`, or `python3.12`, a
   non-credential flag, interpolation, or an absolute checkout path.
   Anything else is printed as `redacted` and leaves exit 4. A redacted
   `sk-` value, `nsec` value, bearer string, or the value after
   `--token` or `--password` was hidden, not validated.
5. Is `FLEET_CONTROL_PYTHON` unset, and is `FLEET_PROVISIONER_GIT_REF`
   unset on the stable Provisioner?
6. Provisioner unit name, and which `onboarding/` and `tombstones/`
   directories does the deployed state loader resolve?
7. Does the gateway load `skills/fleet-delegation/SKILL.md` from this
   checkout or from a profile copy? This procedure does not copy the
   skill. Tool text travels with `index.js`. `skill-load=home-skills`
   means a copy under `HERMES_HOME/skills` exists; the fleet-tip loader
   prefers that over `skills.external_dirs`. That is not a process-map
   observation.
8. Is the origin URL free of an embedded token? Step 4 stops when URL
   userinfo is present. It does not copy that URL into the new git
   config and it does not print it. Scp-style `git@host:path` is not
   userinfo.

## Control stops

The helpers stop, without printing a secret, when a check fails. Key
names and paths may be printed. Do not print values whose keys match
`TOKEN`, `SECRET`, `PASSWORD`, `PRIVATE`, `NSEC`, `CREDENTIAL`, or
`KEY`.

- Python 3.12 is missing or resolves inside the agent virtualenv.
- Both unit scopes are loaded, or neither is.
- Gateway not active and running, or `MainPID` is not a new live pid
  after a restart that was supposed to change it.
- `FLEET_CONTROL_PYTHON` is set. On step 1,
  `HERMES_FLEET_CONTROL_INTEGRATION` is not `1`. After step 6 the root
  is not the new checkout.
- Stable directory is not exactly one `dcb3f950*` checkout at the pins.
  Running root is neither that directory nor the new one.
- `fleet-delegation.conf` is not exactly one loaded regular file, or a
  loaded drop-in name sorts after `fleet-retirement.conf`.
- A journal dir is missing, not private (`mode & 077`), empty, or holds
  a taken `*.lock`. After step 1, the sha256 manifest must match
  `journals.manifest`.
- The stable git origin has URL userinfo, or its form is unknown.
- Fleet env file is not a regular file. Profile `.env` is missing or
  not private.
- `config.yaml`, `fleet-delegation.conf`, profile `.env`, fleet env, or
  the unit fragment differs from the step 1 baseline, except the step 5
  rewrite recorded as `config.yaml.deployed`.
- Worker projection differs from the baseline. The projection keeps
  name, declared, retained, tombstone name and vmid, observed state,
  public key hex, vmid, and onboarding id and status.
- `git status --porcelain=v1 -uall` on the new checkout shows anything
  outside untracked `runtime/` and `fleet-mcp/node_modules/`.

Step 1 writes the baseline only on the stable checkout with
`fleet-retirement.conf` absent. Files: `journals.manifest`, copies of
`fleet-delegation.conf`, `config.yaml`, the fleet env, the profile
`.env`, and the unit fragment, plus `mainpid`, `stable_dir`, and
`config.mode`. Copies are mode `0600`. The directory is mode `0700`.
A later command compares and does not replace them.

## Host filesystem writes

Preflight does not write. Every other command below names its writes.
`baseline=matched` on a witness means the saved baseline was not
replaced. It does not mean that run wrote nothing.

- Step 1 creates the Control evidence directory (mode `0700`) and, once,
  mode `0600` files `journals.manifest`, `fleet-delegation.conf`,
  `config.yaml`, `config.mode`, `fleet.env`, `profile.env`,
  `unit.fragment`, `mainpid`, `stable_dir`, and `scope`. The manifest
  step opens an existing journal `*.lock` read-write, checks that it is
  not held, and unlocks it. It does not write lock contents.
- Step 2 creates
  `/var/lib/hermes-control-deploy/c08cb1e-provisioner-witness` (mode
  `0700`) and, once, `witness.manifest` and `identity` (mode `0600`).
  Every run sets the directory mode again. A matched run does not
  rewrite the two files.
- Step 3 creates
  `/var/lib/hermes-control-deploy/c08cb1e-guest-node-witness` (mode
  `0700`), creates or truncates `lock` and takes a non-blocking flock,
  and replaces `qm-now.txt` with VMID and status rows. The first run
  copies that file to `qm-baseline.txt` (mode `0600`). Later runs
  compare and do not replace `qm-baseline.txt`. `lock` and `qm-now.txt`
  follow the shell umask. This is a host mutation. It does not start,
  stop, or destroy a guest.
- Step 4 creates `/opt/hermes-fleet-control` if needed, `git init` of the
  new checkout, and `git remote add` only when the origin has no
  embedded credential. It fetches and checks out the deploy commit. It
  may create `runtime/venv` through `install-control-runtime` and
  `fleet-mcp/node_modules` through `npm ci`.
- Step 5 may create `fleet-retirement.conf` (mode `0644`) beside the
  loaded delegation drop-in, through an `O_EXCL` temp file, fsync, and
  `os.replace`. It may replace `config.yaml` the same way, keeping the
  original mode and owner. It writes evidence files
  `fleet-retirement.conf.desired`, `config.yaml.deployed`, and
  `config.status` (mode `0600`).
- Step 6 runs `systemctl daemon-reload` and `systemctl restart` for this
  unit when the live root is still stable. It does not write the
  evidence files again.
- Step 7 reads. It does not write.
- Steps 8 and 9 run the step 2 and step 3 commands again. Step 9 still
  truncates `lock` and replaces `qm-now.txt`.
- Step 10 may replace `config.yaml` from the baseline, chmod it to the
  recorded mode, write `fleet-retirement.conf.removed` (mode `0600`),
  unlink `fleet-retirement.conf`, and restart the same unit.
- Step 11 reads. Steps 12 and 13 repeat steps 2 and 3.

## 1. Control — baseline

On the Control host:

```bash
docs/deploy/c08cb1e-preflight.sh
docs/deploy/c08cb1e_material.py baseline
```

The preflight must exit 0. `baseline` prints scope, `ActiveState`,
`SubState`, `MainPID`, `NRestarts` with what that counter measures,
drop-in names, fleet env key names, `FLEET_CONTROL_PYTHON=absent`, the
journal manifest checksum, `stable`, `running-root`, and
`baseline=created` or `baseline=matched`. It ends `STEP 1 OK`. It does
not restart or create the new checkout.

## 2. Provisioner — witness

On the Provisioner, as root. This is a host mutation, not a read-only
diagnostic. The first run creates the witness directory and its two
files. Later runs chmod the directory and compare. Steps 8 and 12 run
this same command. See Host filesystem writes.

```bash
docs/deploy/c08cb1e-provisioner-witness.sh
```

Require `baseline=created` the first time and `baseline=matched` later.
The command resolves state with the deployed loader and counts
`onboarding/*.json` and `tombstones/*.json`. It does not print those
bodies.

## 3. Guest node — VM inventory

On the guest node, as root. That host is the one where `qm` and
`/etc/pve` are present. This command is a host mutation, not a
read-only diagnostic. It does not start, stop, or destroy a guest.
Every run creates or reuses
`/var/lib/hermes-control-deploy/c08cb1e-guest-node-witness` (mode
`0700`), creates or truncates `lock` and holds a non-blocking flock,
and replaces `qm-now.txt`. The first run copies that snapshot to
`qm-baseline.txt` (mode `0600`). A later `baseline=matched` still
replaces `qm-now.txt` and truncates `lock`; it does not replace
`qm-baseline.txt`. The command prints `host-mutation=yes` and
`read-only=no` before those writes. Steps 9 and 13 run this same
command.

```bash
docs/deploy/c08cb1e-guest-node-witness.sh
```

Require `host-mutation=yes`, `baseline=created` the first time and
`baseline=matched` later, and `GUEST-NODE OK`.

## 4. Control — install the checkout beside the stable one

The stable checkout is only read. `NEW` is
`/opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688`.

```bash
docs/deploy/c08cb1e_material.py install
```

If the stable origin has URL userinfo, the command prints
`origin-embedded-token=present` and `origin-copied=no`, then stops. It
does not write that URL into the new git config. A credential-free
origin is copied and not printed. The command then fetches and checks
out the deploy commit, checks `HEAD` and `HEAD^{tree}`, installs the
locked runtime when the import is missing, and runs `npm ci` only when
`npm ls` fails. It ends `STEP 4 OK`.

## 5. Control — drop-in and config.yaml

```bash
docs/deploy/c08cb1e_material.py configure
```

Requires the baseline. Re-checks the journal manifest and
`fleet-delegation.conf`. Writes `fleet-retirement.conf` beside it only
if absent (mode `0644`); if present, the bytes must already match.
Rewrites `config.yaml` only for
`mcp_servers.<name>.command`, `cwd`, and `args[n]`, by one prefix swap,
through `config.yaml.c08cb1e-tmp` opened `O_EXCL`, fsync, the original
mode and owner, then `os.replace`. Prints `config=interpolated`,
`config=unchanged`, or `config=rewritten`, then `STEP 5 OK`.

## 6. Control — reload and restart only this gateway

```bash
docs/deploy/c08cb1e_material.py restart
```

Re-checks journals. If the live root is already the new checkout and
the drop-in is loaded, prints `restart=skipped` and `STEP 6 OK`.
Otherwise the root must still be stable. Same scope as step 1:
`systemctl daemon-reload` and `systemctl restart` (with `--user` when
step 1 selected the user unit). Requires `ActiveState=active`,
`SubState=running`, a new `MainPID`, the new root,
`FLEET_CONTROL_PYTHON` unset, both drop-ins loaded, and the journal
manifest unchanged. `NRestarts` is printed and is not required to
increase. Prints `STEP 6 OK`.

## 7. Control — config and status

```bash
docs/deploy/c08cb1e_material.py verify
```

Running root is the new checkout. Journals match the baseline.
`config.yaml` does not name the stable checkout unless step 5 recorded
`config=interpolated`. Prints `STEP 7 OK`.

List tools with the new MCP SDK only after `STEP 7 OK`, spawning `node`
on `NEW/fleet-mcp/index.js` with cwd `NEW/fleet-mcp` and env `PATH`,
`HOME`, and `LANG=C`. Require `worker_status`, `ensure_worker`,
`onboard_worker`, `delegate_worker`, and `retire_worker`.
`send_message` must be absent. Do not call a tool. The helper
`require_tools` enforces that set on the names the client returns.

## 8. Provisioner — witness unchanged

Run the step 2 command again. Require `baseline=matched`.

## 9. Guest node — inventory unchanged

Run the step 3 command again. Require `baseline=matched`.

## 10. Control — roll back to the stable checkout

```bash
docs/deploy/c08cb1e_material.py rollback
```

Undo of steps 5 and 6 only. Compares journals first.
`fleet-delegation.conf` must match its backup. Restores `config.yaml`
from the baseline with the same `O_EXCL`, fsync, mode, owner, and
`os.replace` when the live bytes are the deployed bytes. Any other
bytes stop. If `fleet-retirement.conf` matches the desired bytes, it
is copied to `fleet-retirement.conf.removed` and unlinked. If the root
is already stable, the drop-in is gone, and `config.yaml` is the
baseline, prints `rollback=already-stable` and `STEP 10 OK` without
restarting. Otherwise restarts the same scope and requires a new
`MainPID`, active/running, the stable root, and the retirement drop-in
absent. `NRestarts` is not required to increase. The new directory
stays on disk. Journals still match. Prints `STEP 10 OK`.

## 11. Control — confirm the stable checkout is running

```bash
docs/deploy/c08cb1e_material.py confirm
```

Root and tree are the stable pins. The drop-in is not loaded and not
on disk. Journals match. No gateway process cwd is the new checkout.
An unreadable cwd stops. Prints `STEP 11 OK`.

## 12. Provisioner — still unchanged

Run the step 2 command again.

## 13. Guest node — still unchanged

Run the step 3 command again.
