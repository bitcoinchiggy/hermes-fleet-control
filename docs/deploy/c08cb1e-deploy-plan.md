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
standard library plus PyYAML when PyYAML is already installed. It does
not install PyYAML and it does not use the agent virtualenv.
`configure` and the preflight YAML read import PyYAML in-process.
Preflight does not spawn the stable checkout's virtualenv and does not
import Provisioner code. `qm`, `flock`, `git`, `systemctl`, `node`, and
`npm` are required only by the commands that name them. `node` and
`npm` are resolved on `PATH=/usr/sbin:/usr/bin:/sbin:/bin` only. A
`node` that exists only on another PATH is reported as absent.

Stop at the first non-zero exit. Steps 1–9 deploy. Steps 10–13 roll
back. A successful deploy stops after step 9. A later step is not a
repair. Re-running records a baseline once and refuses to replace it.
Step 1 also stops when `fleet-retirement.conf` is loaded or on disk, so
it is valid only before step 5. A restart that already reached the
revision it checks is skipped. Rollback does not delete journals,
reservations, tombstones, profile files, or the stable checkout. It
does not overwrite a profile `.env`, the fleet env file, the unit
fragment, or `fleet-delegation.conf`. A difference in those files is
a warning. Rollback still removes a verified `fleet-retirement.conf`
and restores or reverse-rewrites `config.yaml` when that rewrite is
safe. If `config.yaml` still names the new checkout, or the retirement
drop-in cannot be verified, rollback is incomplete: it does not restart
the gateway and it does not print `STEP 10 OK`.

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
- Node on the pinned PATH is 20 or newer. A second paste skips `npm ci`
  and `install-control-runtime` when the import and `npm ls` already
  match. `/usr/bin/python3.12` resolves outside the agent virtualenv.
  Baseline and install both stop when it does not.
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
   checkout path or `${HERMES_FLEET_CONTROL_ROOT}`. An argument is
   ready only when it is absent, interpolated, an absolute checkout
   path, one of `node`, `npm`, `python3`, or `python3.12`, the flag
   `--version` or `--stdio`, or a `relative-script:<basename>` fact.
   The relative-script fact is printed only for a basename matching
   `^[A-Za-z0-9._-]+\.(js|mjs|cjs)$` with no `/` and no `..`, when
   `command` is `node` on the pinned PATH and that binary's real path
   is an executable regular file outside the checkout, `cwd` is exactly
   `<root>/fleet-mcp`. That directory must not be a symlink, and
   `realpath(cwd)` must stay inside the checkout. `realpath(cwd/arg)`
   must be a regular non-symlink file inside both `realpath(cwd)` and
   the checkout. The node binary may be a symlink to that outside file.
   The script file may not be a symlink. Any other flag, including
   `-p...` and `--access-token`, is printed as `redacted`. The value
   after a flag other than `--version` or `--stdio` is `redacted` too,
   even when the value is a public word such as `node` or `python3`.
   `redacted` is not configuration validation and leaves exit 4.
5. Is `FLEET_CONTROL_PYTHON` unset, and is `FLEET_PROVISIONER_GIT_REF`
   unset on the stable Provisioner?
6. Provisioner unit name? Preflight does not import the deployed
   state loader. When a provisioner unit is on this host it prints
   `onboarding-dir=deferred-to-witness` and
   `tombstones-dir=deferred-to-witness`. Step 2 resolves the directories.
7. Does the gateway load `skills/fleet-delegation/SKILL.md` from this
   checkout or from a profile copy? This procedure does not copy the
   skill. Tool text travels with `index.js`. `skill-load=home-skills`
   means a copy under `HERMES_HOME/skills` exists; the fleet-tip loader
   prefers that over `skills.external_dirs`.
   `skill-load=checkout-only-not-on-skill-path` is an accepted readiness
   value when that profile copy is absent and the checkout file exists.
   Neither value is a process-map observation, and this procedure does
   not claim the running loader read the file.
8. Is the origin URL free of an embedded token? Step 4 stops when URL
   userinfo contains a password, or when the URL contains `?`, `#`, or
   `;`. Those forms are not copied and are not printed.
   `ssh://git@host/...` with a username and no password is treated as
   credential-free, as is scp-style `git@host:path`. Other URL userinfo
   is not copied.

## Control stops

The helpers stop, without printing a secret, when a check fails. Key
names and paths may be printed. Do not print values whose keys match
`TOKEN`, `SECRET`, `PASSWORD`, `PRIVATE`, `NSEC`, `CREDENTIAL`, or
`KEY`.

- Python 3.12 is missing or resolves inside the agent virtualenv.
  Baseline and install check this.
- Both unit scopes are loaded, or neither is, on steps that select a
  scope from systemd. Rollback reads the scope saved at step 1 instead,
  so a failed unit does not have to be active for that selection.
- Gateway not active and running, or `MainPID` is not a new live pid
  after a restart that was supposed to change it. Rollback accepts an
  inactive or failed unit and uses `MainPID` 0 as the before value.
- `FLEET_CONTROL_PYTHON` is set. On step 1,
  `HERMES_FLEET_CONTROL_INTEGRATION` is not `1`. After step 6 the root
  is not the new checkout.
- Stable directory is not exactly one `dcb3f950*` checkout at the HEAD
  and tree pins. Baseline and install both check those pins. Running
  root is neither that directory nor the new one.
- `fleet-delegation.conf` is not a regular file inside
  `/etc/systemd/system/` or `~/.config/systemd/user/` after resolving
  the path. A substring match is not enough, and a symlink is rejected.
  A loaded drop-in name that sorts after `fleet-retirement.conf` (for
  example `override.conf`) also stops.
- `ExecStart`, `WorkingDirectory`, or an `EnvironmentFile=` path
  references the stable checkout or sets `HERMES_FLEET_CONTROL_ROOT`.
  Baseline, configure, restart, and verify stop. An optional
  `EnvironmentFile=-` entry that is missing is tolerated; an existing
  optional file is still read. A required missing file, a symlink, and
  a path that contains the stable checkout still stop. Rollback and
  confirm do not use that stop: the stable path is the rollback target.
- `NeedDaemonReload` is not `no` before an edit or after a reload.
- A journal dir is missing, not private (`mode & 077`), empty, or holds
  a taken `*.lock`. After step 1, steps other than rollback and confirm
  stop when the sha256 manifest does not match `journals.manifest`.
  Rollback and confirm print a journal warning (`journal-warning=changed`
  or `journal-warning=unreadable`) and do not overwrite or delete
  journal files. New journal entries do not by themselves fail rollback
  or confirm.
- The stable git origin has URL userinfo other than an `ssh://`
  username with no password, contains `?`, `#`, or `;`, or its form is
  unknown.
- Fleet env file is not a regular file. Profile `.env` is missing or
  not private. Configure, restart, and verify still require profile
  `.env`, the fleet env, and the unit fragment to match the baseline
  copies. Rollback and confirm warn on those differences and do not
  modify the files.
- Configure and verify stop when `config.yaml` or `fleet-delegation.conf`
  differs from the recorded bytes, except the step 5 rewrite recorded
  as `config.yaml.deployed`. Rollback does not stop on delegation drift.
  For `config.yaml`, rollback restores the baseline when the live bytes
  are the deployed bytes, reverse-rewrites fleet MCP paths when that
  swap is safe, and otherwise leaves the file in place and reports an
  incomplete rollback.
- `git status --porcelain=v1 -uall` on the new checkout, checked by
  install and verify, shows anything outside untracked `runtime/` and
  `fleet-mcp/node_modules/`.

`project_workers` and `require_tools` are defined in the helper. No
command calls them. This procedure does not fetch worker status and
does not spawn the Fleet MCP server.

Step 1 writes the baseline only on the stable checkout with
`fleet-retirement.conf` absent, including on a later re-run. Files:
`journals.manifest`, copies of `fleet-delegation.conf`, `config.yaml`,
the fleet env, the profile `.env`, and the unit fragment, plus
`mainpid`, `stable_dir`, `scope`, `config.mode`, `config.path`,
`profile.env.path`, `fleet.env.path`, `unit.fragment.path`, and
`delegation.path`. Copies are mode `0600`. The directory is mode
`0700`. The files are written in a sibling staging directory and
renamed into place only after every required file is on disk. A
partial staging directory or a partial evidence directory that
contains only expected names is discarded and rewritten on the next
`baseline`. An unexpected name is left in place and stops the
command. A partial directory is not a complete baseline. Do not
delete journals to recover. An evidence directory written by an
older helper, without a `scope` file, stops rollback with `baseline
scope is missing`. If steps 5–6 were run with that older helper,
roll back with that same helper version, then move the evidence
directory aside. A new baseline is valid only while
`fleet-retirement.conf` is absent.

`baseline`, `configure`, `restart`, `verify`, `rollback`, and
`confirm` take one exclusive flock on the parent of the evidence
directory and wait up to 5 seconds. If another command holds it, the
new command prints `STOP: another deploy command holds the evidence
lock` and exits 1.

Fleet env output is `fleet-env-name-count`, `fleet-env-names-sha256`
(the sha256 of the sorted unique validated names, one per line),
`fleet-env-unparsed-lines`, and `present` or `absent` for
`FLEET_PROVISIONER_URL` and `FLEET_PROVISIONER_CALLER_TOKEN`. Names
and values from the file are not printed. A quoted value that does
not close on its opening line makes every following line unparsed
until the closing quote. Those lines are not names.

## Host filesystem writes

Preflight does not write. Every other command below names its writes.
`baseline=matched` on a witness means the saved baseline was not
replaced. It does not mean that run wrote nothing.

- Step 1 creates the Control evidence directory (mode `0700`) and, once,
  mode `0600` files `journals.manifest`, `fleet-delegation.conf`,
  `config.yaml`, `config.mode`, `fleet.env`, `profile.env`,
  `unit.fragment`, `mainpid`, `stable_dir`, `scope`, `config.path`,
  `profile.env.path`, `fleet.env.path`, `unit.fragment.path`, and
  `delegation.path`. The manifest step opens an existing journal
  `*.lock` with `O_RDONLY|O_NOFOLLOW`, probes `LOCK_SH|LOCK_NB`, and
  unlocks it. A symlink stops. It does not take an exclusive lock and
  it does not write lock contents.
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
  follow the shell umask. A symlink at the evidence directory, a parent,
  or `lock`, `qm-now.txt`, or `qm-baseline.txt` stops the command before
  `mkdir` or a redirect. This is a host mutation. It does not start,
  stop, or destroy a guest.
- Step 4 creates `/opt/hermes-fleet-control` if needed, `git init` of the
  new checkout, and `git remote add` only when the origin has no
  embedded credential. It fetches and checks out the deploy commit. It
  may create `runtime/venv` through `install-control-runtime` and
  `fleet-mcp/node_modules` through `npm ci`.
- Step 5 holds the shared exclusive flock on the evidence parent for
  the whole command. It first writes evidence files
  `fleet-retirement.conf.desired`, `config.yaml.deployed`, and
  `config.status` (mode `0600`). It then may create
  `fleet-retirement.conf` (mode `0644`) beside the loaded delegation
  drop-in, through an `O_EXCL` temp file, a full write, fsync, chown,
  chmod, `os.replace`, and an fsync of the directory. It may replace
  `config.yaml` the same way, keeping the original mode and owner. A
  crash after the evidence write and before the live edit leaves the
  rollback record in place and does not require the live files to have
  changed.
- Step 6 runs `systemctl daemon-reload` and `systemctl restart` for this
  unit when the live root is still stable. It then waits about 10
  seconds and requires the same `MainPID`, `active`/`running`, and an
  unchanged `NRestarts` since that first post-restart read. It does not
  write the evidence files again.
- Step 7 reads. It does not write.
- Steps 8 and 9 run the step 2 and step 3 commands again. Step 9 still
  truncates `lock` and replaces `qm-now.txt`.
- Step 10 may replace `config.yaml` from the baseline or with a
  reverse rewrite of the fleet MCP paths, chmod a baseline restore to
  the recorded mode, write `fleet-retirement.conf.removed` (mode
  `0600`) in the evidence directory, and unlink
  `fleet-retirement.conf` only when that file's bytes match the
  desired copy and it is not a symlink. It may run `daemon-reload`
  and restart the same unit. It does not write the removed copy
  beside the drop-in. It does not modify journals, reservations,
  tombstones, identities, credentials, profile `.env`, the fleet env,
  the unit fragment, or `fleet-delegation.conf`. An incomplete
  rollback does not restart.
- Step 11 reads. Steps 12 and 13 repeat steps 2 and 3.

## 1. Control — baseline

On the Control host:

```bash
docs/deploy/c08cb1e-preflight.sh
docs/deploy/c08cb1e_material.py baseline
```

The preflight must exit 0. `baseline` prints scope, `ActiveState`,
`SubState`, `MainPID`, `NRestarts` with what that counter measures,
drop-in names, `fleet-env-name-count`, `fleet-env-names-sha256`,
`fleet-env-unparsed-lines`, and present or absent for
`FLEET_PROVISIONER_URL` and `FLEET_PROVISIONER_CALLER_TOKEN`. It does
not print fleet env names or values. It also prints
`FLEET_CONTROL_PYTHON=absent`, the journal manifest checksum,
`stable`, `running-root`, and `baseline=created` or
`baseline=matched`. It checks the stable HEAD and tree pins,
`/usr/bin/python3.12` outside the agent virtualenv, root for a system
unit, `NeedDaemonReload=no`, delegation-drop-in location, and that
`ExecStart`, `WorkingDirectory`, and `EnvironmentFile=` do not pin the
checkout. It ends `STEP 1 OK`. It does not restart or create the new
checkout. It stops if `fleet-retirement.conf` is already present.

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

The command checks the stable HEAD and tree pins and that
`/usr/bin/python3.12` resolves outside the agent virtualenv before it
writes. If the stable origin has URL userinfo, `?`, `#`, or `;`, it prints
`origin-embedded-token=present` or `origin-embedded-token=unknown` and
`origin-copied=no`, then stops. It does not write that URL into the new
git config. A credential-free origin, including `ssh://git@host/...`
with no password, is copied and not printed. Git commands pass
`safe.directory` for that checkout. The command then fetches and checks
out the deploy commit, checks `HEAD` and `HEAD^{tree}`, installs the
locked runtime when the import is missing, runs `npm ci` only when
`npm ls` fails, and requires `git status --porcelain=v1 -uall` to show
only untracked `runtime/` and `fleet-mcp/node_modules/` paths. It ends
`STEP 4 OK`.

## 5. Control — drop-in and config.yaml

```bash
docs/deploy/c08cb1e_material.py configure
```

Requires the baseline. Re-checks the journal manifest,
`fleet-delegation.conf`, profile `.env`, the fleet env, and the unit
fragment. Holds the shared exclusive flock on the evidence parent.
Writes
`fleet-retirement.conf.desired`, `config.yaml.deployed`, and
`config.status` before it edits a live file. Writes
`fleet-retirement.conf` beside the delegation drop-in only if absent
(mode `0644`); if present, the bytes must already match. Rewrites
`config.yaml` only for `mcp_servers.<name>.command`, `cwd`, and
`args[n]`, by one prefix swap, through `config.yaml.c08cb1e-tmp` opened
`O_EXCL`, a full write, fsync, chown, the original mode, then
`os.replace`. An interpolated config is accepted only when the fleet
MCP entry contains `${HERMES_FLEET_CONTROL_ROOT}`. Prints
`config=interpolated`, `config=unchanged`, or `config=rewritten`, then
`STEP 5 OK`.

## 6. Control — reload and restart only this gateway

```bash
docs/deploy/c08cb1e_material.py restart
```

Re-checks journals and the step 1 side files. If the live root is
already the new checkout and the drop-in is loaded, prints
`restart=skipped` and `STEP 6 OK`. Otherwise the root must still be
stable. Same scope as step 1: `systemctl daemon-reload` and
`systemctl restart` (with `--user` when step 1 selected the user unit).
Requires `ActiveState=active`, `SubState=running`, a new `MainPID`, the
new root, `FLEET_CONTROL_PYTHON` unset, both drop-ins loaded, and the
journal manifest unchanged. It then waits about 10 seconds and requires
that same `MainPID`, still `active`/`running`, and `NRestarts`
unchanged from the first post-restart read. `NRestarts` is printed and
is not required to increase. Prints `STEP 6 OK`.

## 7. Control — config and status

```bash
docs/deploy/c08cb1e_material.py verify
```

Running root is the new checkout. Journals match the baseline. Profile
`.env`, the fleet env, and the unit fragment match step 1. The new
checkout's `git status --porcelain=v1 -uall` shows only the allowed
untracked paths. `config.yaml` matches `config.yaml.deployed` and does
not name the stable checkout unless step 5 recorded
`config=interpolated`. Prints `STEP 7 OK`.

This command does not spawn MCP and does not call `require_tools` or
`project_workers`. Do not treat a tool list or a worker projection as
a check this procedure completed.

## 8. Provisioner — witness unchanged

Run the step 2 command again. Require `baseline=matched`.

## 9. Guest node — inventory unchanged

Run the step 3 command again. Require `baseline=matched`.

## 10. Control — roll back to the stable checkout

```bash
docs/deploy/c08cb1e_material.py rollback
```

Undo of steps 5 and 6 only. Reads the scope and stable directory from
the evidence directory, so an inactive or failed unit can roll back.
`MainPID` 0 is the before value when the unit is not active and
running. A journal difference prints a warning and
`journal-warning=changed` or `journal-warning=unreadable`. Rollback
does not overwrite or delete journal files. Profile `.env`, the fleet
env, and the unit fragment may differ. That prints
`WARNING: side file differs from baseline; rollback will not modify it`
and `side-file-drift=` with the drifted labels, or `side-file-drift=none`.
Those files are not written. A delegation difference prints a warning
and `delegation-drift=changed` and is not written. The retirement
drop-in is removed only when it is the sibling
`fleet-retirement.conf` of the stored delegation path, it is not a
symlink, and its bytes equal `fleet-retirement.conf.desired`. The
removed bytes are copied to `fleet-retirement.conf.removed` in the
evidence directory first. Any other drop-in state prints
`dropin-rollback=unverified` and is left on disk.
`config.yaml` is restored from the baseline, with the recorded mode,
when the live bytes are `config.yaml.deployed`. When the live bytes
are already the baseline, it is left alone (`config-rollback=unchanged`).
Other bytes get one reverse rewrite of the fleet MCP `command`, `cwd`,
and `args` that name the new checkout, leaving unrelated keys in
place (`config-rollback=reversed`). If that rewrite is not safe, or
PyYAML is not already installed, the file is left unchanged
(`config-rollback=incomplete`). When the drop-in was removed or was
already absent, `daemon-reload` runs and `DropInPaths` must no longer
list it, with `NeedDaemonReload=no`. If the drop-in is unverified, the
config rewrite is incomplete, or `config.yaml` still names the new
checkout, the command prints `rollback=incomplete`, prints
`STOP: rollback incomplete; operator intervention required`, and does
not restart. If the unit was already active, the root is stable, the
drop-in was already absent, and `config.yaml` was already the
baseline, it prints `rollback=already-stable` and `STEP 10 OK` without
restarting. Otherwise it restarts the same scope and requires a new
`MainPID`, active/running, the stable root, and the retirement drop-in
absent. The restart waits about 10 seconds and re-reads. `NRestarts`
is not required to increase. The new directory stays on disk. A
successful rollback prints `STEP 10 OK`. An incomplete one does not.

## 11. Control — confirm the stable checkout is running

```bash
docs/deploy/c08cb1e_material.py confirm
```

Root and tree are the stable pins. The running process is the stable
gateway: active and running, `HERMES_FLEET_CONTROL_ROOT` is the stable
checkout, and `FLEET_CONTROL_PYTHON` is unset. `fleet-delegation.conf`
is loaded. The retirement drop-in is not loaded and not on disk.
`NeedDaemonReload=no`. A journal difference prints a warning and does
not fail the command. Side-file drift is the same warning as rollback
and is not modified. `config.yaml` must not name the new checkout; it
does not have to be byte-for-byte the baseline when a reverse rewrite
preserved unrelated keys. No gateway process cwd is the new checkout.
An unreadable cwd stops. Prints `STEP 11 OK`.

## 12. Provisioner — still unchanged

Run the step 2 command again.

## 13. Guest node — still unchanged

Run the step 3 command again.
