# First guarded Control deployment readiness

Planning only. Writing this page did not deploy, restart, roll back, SSH,
open a pull request, transfer a helper, or contact a host. Gate A
accepted the planning approach at
`d04238aba3b2b107da57f0df8f80d52483d3b520`. This revised execution sheet
requires final acceptance before Gate B. Gate B execution is not
authorized. This page does not approve a host command, a witness, a
helper transfer, a deployment, or a rollback.

Helper behavior is the merged tree
`30e64213d353a487fb84d84443449461b7a76944`. This page does not change
`c08cb1e_material.py`, the shell wrappers, the tests, or the workflow.
Later-gate commands in sections 5 and 11 are copied from
`docs/deploy/c08cb1e-deploy-plan.md`. They are not Gate B commands.
Gate B uses only the Final Gate B execution sheet. The helper scripts
at `30e64213d353a487fb84d84443449461b7a76944` are git mode `100755`.
Exact mode `755` on the host is intentional.

Stable revisions in this page are repository pins. They are historical
reports until a host command, under its own gate, prints them from that
host.

## 1. Executive readiness summary

The repository contains a 13-step Control procedure. Steps 1–9 deploy
`c08cb1ebd073ee7946f49005dd45071366eeb688` beside the pinned stable
checkout. Steps 10–13 roll that gateway back. Stop at the first
non-zero exit. A later step is not a repair.

The procedure is internally consistent with the helper on that merge.
It is not authorized to run. Hostnames, unit scope, and whether the
three roles are different machines are unresolved. The only shipped
command that leaves persistent files unchanged is Control preflight,
and it inspects only the machine where it runs. That filesystem
read-only behavior is separate from operational noninterference: the
shared journal-lock probes can make a concurrent Fleet operation fail
immediately. Exit 4 means the diagnostic finished and the host is not
ready. Preflight's `unit-scope=system` line is this process's view
after `XDG_RUNTIME_DIR` is cleared. It can hide a hermes user unit.

The Provisioner witness and the guest-node witness write files under
`/var/lib/hermes-control-deploy/`. Their names do not make them
read-only. Baseline writes the recovery record. Install, configure,
restart, and rollback change checkout, config, drop-ins, or the
gateway process. Those commands stay behind Gate D or Gate F.

## 2. Architecture and host-responsibility matrix

The runbook states three machines and says that split was not read from
a host. This matrix keeps that statement as an assumption.

| Role | Host | What runs there | Repository and revision | Files this procedure can change | Left untouched |
| --- | --- | --- | --- | --- | --- |
| Control gateway | `<UNRESOLVED: Control hostname>` | `hermes-gateway-control.service`, system scope if that is the only loaded scope and the command runs as root, user scope if that is the only loaded scope | Product checkout under `/opt/hermes-fleet-control/`. Stable pin `dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a`, tree `3d5f940738c5d1c0061645d06e74d3f88b034ae5`, the single `dcb3f950*` directory. Deploy pin `c08cb1ebd073ee7946f49005dd45071366eeb688`, tree `2b8888b984634b714d62646ddd5b6f48d073d160`, directory `/opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688`. Helpers are a copy of `docs/deploy/` from fleet-control `30e64213d353a487fb84d84443449461b7a76944` | New checkout; `fleet-retirement.conf` (mode `0644`) beside the loaded delegation drop-in; the named fleet MCP entry in profile `config.yaml`; evidence directory. Evidence is `/var/lib/hermes-control-deploy/c08cb1ebd073ee7946f49005dd45071366eeb688` as root, otherwise `$HOME/.local/state/hermes-control-deploy/c08cb1ebd073ee7946f49005dd45071366eeb688` | `fleet-delegation.conf`; profile `.env`; fleet env file; unit fragment; journals; reservations; tombstones; identities; credentials; the agent checkout. The procedure does not call `onboard_worker`, `retire_worker`, `delegate_worker`, `ensure_worker`, `require_tools`, or `project_workers` |
| Fleet provisioner | `<UNRESOLVED: Provisioner hostname>` | Exactly one active unit whose name contains `provisioner`, or is `hermes-fleet.service` or `fleet-provisioner.service`. The live unit name is `<UNRESOLVED: provisioner unit name>` | Historical pin `b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb` in the provisioner checkout. The live HEAD is unverified | `/var/lib/hermes-control-deploy/c08cb1e-provisioner-witness` only, and only when the witness runs | Provisioner product code, unit files, onboarding bodies, tombstone bodies |
| Guest node | `<UNRESOLVED: guest-node hostname>` | The host where `qm` and `/etc/pve` are present. `hermes-gateway-control.service` must not be loaded | No product checkout is installed by this procedure | `/var/lib/hermes-control-deploy/c08cb1e-guest-node-witness` only, and only when the witness runs | Guest lifecycle. The witness does not start, stop, or destroy a guest. Operator-supplied protected infrastructure, not a repository fact: VM 1035, VM 1036, and template 1000. Leave those identifiers unchanged |

Systemd drop-ins on the Control host:

- `fleet-delegation.conf` is an existing loaded drop-in. The procedure reads it and does not edit it.
- `fleet-retirement.conf` is absent at step 1. Step 5 creates it. Rollback unlinks it only when it is a regular file and its bytes equal evidence `fleet-retirement.conf.desired`.
- A loaded drop-in whose name sorts after `fleet-retirement.conf` stops the deploy.

Interpreter pin: `/usr/bin/python3.12`, resolving outside
`/home/hermes/.hermes/hermes-agent/venv`. The helper does not use that
virtualenv. Named locks in the runbook are `cryptography==50.0.2` and
`PyYAML==6.0.2`. Preflight and baseline use an already installed
PyYAML. `cryptography` is imported from the new checkout's
`runtime/venv` during install, not during preflight.

Agent checkout: the runbook records
`e29f306cdbc7728f297d218be6ecda511bcf450a` on `bitcoinchiggy/hermes-agent`
branch `fleet`, parent `6b208cf543923b059159788063da33601de419e4`. The
local agent clone contains that commit on `origin/fleet` with that
parent. The running Control agent revision was not read. This procedure
does not change the agent checkout. stdio MCP still reads `command`,
`cwd`, and `args` from profile `config.yaml`.

## 3. Confirmed facts vs unverified assumptions

Confirmed from the merged helper, the runbook, and local git objects.
None of these were read from a live host.

- `origin/main` of this repo is `30e64213d353a487fb84d84443449461b7a76944`.
- Deploy commit `c08cb1ebd073ee7946f49005dd45071366eeb688` exists locally and its tree is `2b8888b984634b714d62646ddd5b6f48d073d160`.
- Stable commit `dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a` exists locally, its tree is `3d5f940738c5d1c0061645d06e74d3f88b034ae5`, and it is an ancestor of the deploy commit. It is not an ancestor of `63099c4a1f38063d2c0068fa40b94baf74bfb092`. Local `git diff --shortstat` between the two pins is 16 files, 2739 insertions, 25 deletions.
- Provisioner commit `b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb` exists in the local hermes-fleet clone. That does not place it on a host.
- Preflight's `cmd_preflight` path does not mkdir, chmod, or open a file with a write flag. `test_preflight_writes_nothing` and `test_preflight_loaded_unit_still_writes_nothing` guard `os.open` write flags. Git subprocesses set `GIT_OPTIONAL_LOCKS=0`, `--no-optional-locks`, and `credential.helper=` empty.
- Every helper subprocess replaces the environment with `PATH=/usr/sbin:/usr/bin:/sbin:/bin`, `LANG=C`, `GIT_OPTIONAL_LOCKS=0`, and `GIT_TERMINAL_PROMPT=0`.
- When the gateway process is live, preflight hashes journal files and opens each journal `*.lock` with `O_RDONLY|O_NOFOLLOW`, takes `LOCK_SH|LOCK_NB`, and unlocks before it returns. It does not write lock contents. A lock that is already held becomes `journals=blocked` and exit 4. See "Shared journal locks" below.
- When `node` resolves on that fixed PATH, preflight runs `node -p process.versions.node.split('.')[0]` and keeps the major version inside the process. Stdout receives `node=ok`, `node=old`, `node=unknown`, or `node=absent`.
- `redacted` MCP output is not configuration validation and leaves exit 4.
- The Provisioner witness, as root, creates `/var/lib/hermes-control-deploy/c08cb1e-provisioner-witness` mode `0700`, chmod's that directory on every run, and on the first run writes `witness.manifest` and `identity` mode `0600`. It imports the deployed `resolve_state_dir` loader. It prints counts and directory paths, not JSON bodies.
- The guest-node witness prints `host-mutation=yes` and `read-only=no`, then creates the guest evidence directory, chmod `0700`, truncates `lock`, replaces `qm-now.txt` from `qm list`, and on the first run copies `qm-baseline.txt` mode `0600`. Later `baseline=matched` still truncates `lock` and replaces `qm-now.txt`. Rows are VMID and status. Guests are not started, stopped, or destroyed.
- Rollback accepts `Restart=` values `no`, `on-failure`, `on-abnormal`, `on-watchdog`, `on-abort`, `always`, and `on-success`, because `systemctl stop` suppresses `Restart=`. An empty or other value is `restart-policy-unknown` and does not stop the unit. An active or unreadable socket, path, or timer named in `TriggeredBy` refuses before the stop.
- `verify` and `confirm` do not write the evidence files. They do take the same exclusive evidence-parent flock as configure, restart, and rollback, and they wait up to 20 seconds. Only baseline may create that parent.
- `project_workers` and `require_tools` exist and no command calls them.

Unverified until the matching gate runs on a host:

- The three hostnames, and that the three roles are on three machines.
- Whether `hermes-gateway-control.service` is a system unit, a user unit, both, or neither.
- That the live stable directory is the single full `dcb3f950*` name at those pins, and that the live process root is that directory.
- Whether the fleet MCP entry uses absolute checkout paths or `${HERMES_FLEET_CONTROL_ROOT}`.
- That `FLEET_CONTROL_PYTHON` is unset on the gateway and `FLEET_PROVISIONER_GIT_REF` is unset on the Provisioner.
- The provisioner unit name, and that `onboarding/*.json` and `tombstones/*.json` match a witness that has not been run.
- Where `skills/fleet-delegation/SKILL.md` is loaded from. `skill-load=checkout-only-not-on-skill-path` is an accepted readiness value. It is not a process-map observation.
- That the stable origin has no embedded token. `ssh://git@host/...` with a username and no password is treated as credential-free. A password in userinfo, or `?`, `#`, or `;` in the URL, is not copied and is not printed.
- Evidence-directory owner, mode, and which euid will run every Control helper step.
- That `/usr/bin/python3.12` on the host is outside the agent virtualenv, that PyYAML is already importable by that interpreter, and that `node` on the fixed PATH is major 20 or newer.
- Which scope is actually loaded on the host. Preflight can report `unit-scope=system` while a hermes user unit exists. See "User-scope systemd visibility" below. The live result of the hermes user-manager query is unverified.
- Network reachability of the git origin and of `FLEET_PROVISIONER_URL`. No shipped read-only command probes either one.
- Any previous evidence directory or an existing `fleet-retirement.conf`.
- Whether a `docs/deploy/` helper copy already exists on the Control host, and that directory's path, owner, and mode. Absence or a digest mismatch is case B and needs a separate transfer authorization.
- The deploying user's name, uid, and passwd home. `sudo -u` can keep the caller's `HOME`.
- VM 1035, VM 1036, and template 1000. Those identifiers are operator-supplied protected infrastructure. They are not recorded elsewhere in this repository.

### Shared journal locks

Preflight's shared-lock probes do not intentionally modify persistent
state. The probe opens an existing journal `*.lock` read-only, takes
`LOCK_SH|LOCK_NB`, and unlocks before the command returns. It does not
write lock contents.

The Fleet writers take `LOCK_EX|LOCK_NB` and fail immediately when that
exclusive lock is busy. `exclusive_delegation` in
`fleet_control/journal.py` raises `delegation_in_flight`. `onboard.py`
raises `onboard_in_flight`. `retire.py` raises `retire_in_flight`.
`exclusive_delegation_wait` in `delegation_intake` retries
`delegation_in_flight` for 5 seconds. Delegate, onboard, and retire
otherwise return the in-flight error at once.

A racing delegate, onboard, or retire call can therefore fail while a
shared probe is held. The window is short. The effect is still an
operational failure. Filesystem read-only behavior and operational
noninterference are different claims. Preflight is read-only for
persistent files. It is not operationally noninterfering.

Fleet idle is an operator-confirmed precondition. No command in this
plan observes it. Before Gate B execution, the operator records the
assertion in the Gate B approval: no delegate, onboard, or retire
operation is in flight. If that assertion is missing, STOP.

Run preflight only when that assertion says Fleet is idle. If
`<scope>-journals=blocked`, or Fleet activity is detected, STOP. Do not
retry repeatedly or automatically.

### User-scope systemd visibility

`_run` replaces the subprocess environment and clears
`XDG_RUNTIME_DIR`. `systemctl --user` then talks to the invoking
process's user manager. As root, that is root's manager, not the
hermes user's manager. The current process's `XDG_RUNTIME_DIR` does
not establish visibility into the hermes user's systemd manager. A
query typed in a root shell, including `systemctl --user` without an
identity change, is root's user manager. It is not hermes's.

The system scope and the user scope are different units that share the
name `hermes-gateway-control.service`. `system-unit=` is the system
manager. A user-scoped unit is loaded only in a user manager.
Preflight's `user-unit=` is the invoking process's manager after
`XDG_RUNTIME_DIR` is cleared.

The hermes user-manager command evaluates the user id inside hermes's
shell. `id -un` on the first line must be `hermes`. A bus connection
failure, including a line that says the bus connection failed, is
unknown visibility. It is not proof the unit is absent. STOP if
user-unit visibility cannot be established. The command does not
enable lingering, start a user manager, or modify systemd:

```bash
sudo -u hermes sh -c 'id -un; XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user show -p LoadState --value hermes-gateway-control.service'
```

A user unit file may also live outside `~/.config/systemd/user`:
`$XDG_CONFIG_HOME/systemd/user`, `~/.local/share/systemd/user`,
`/etc/systemd/user`, or `/usr/lib/systemd/user`. A directory listing
that omits the unit does not prove the unit is absent. Only `LoadState`
from the hermes user's manager establishes visibility.

`systemctl_loaded` maps exit 127 to `systemctl-absent`. Any other
nonzero exit becomes `not-loaded`. A nonzero `systemctl` result may
mean the manager is unreachable. It does not by itself mean the unit
is absent. Gate C must resolve that case explicitly.

Two outcomes follow:

- The system unit is loaded and the hermes user unit is invisible. Preflight can print `unit-scope=system` and continue toward host-ready. That is not fail-closed. Later steps would follow the system unit while a user-scoped gateway may also be loaded or active.
- Only a user unit exists, and this process cannot see it. Preflight prints `unit-scope=neither` and exits 4. That outcome is fail-closed.

Both scopes may be loaded or active. The helper reports `unit-scope=both` only when its own cleared-environment queries both return `loaded`. An invisible hermes user unit does not produce `both`.

Deployment planning approval must not proceed to Gate D until the
intended service scope is unambiguous. That is outstanding decision 4.
The Gate B scope commands are listed in "Gate B command inventory".

## 4. Prerequisite checklist

| Prerequisite | How it is verified | Shipped command | When |
| --- | --- | --- | --- |
| Helper copy of `docs/deploy/` from fleet-control `30e64213d353a487fb84d84443449461b7a76944` | Case A: R2 through R5 in the Final Gate B execution sheet. That is the exact file set, root ownership, no group or world write on the directory or its parents, mode `644` for the plan and `755` for the four scripts, and the two content hashes. Case B: anything else. STOP and request a separate transfer authorization. Transfer is a write and is outside read-only Gate B | Required checks R2, R3, R4, and R5, each named in the Gate B approval | Before preflight. This plan does not transfer files |
| `/usr/bin/python3.12` executable and outside `/home/hermes/.hermes/hermes-agent/venv` | Preflight prints `python312=outside-venv`. The wrapper exits 1 when the interpreter is missing | Required check R8 in the Final Gate B execution sheet | Gate B on the Control host |
| PyYAML already installed for that interpreter | Preflight prints `pyyaml=present`. The helper never installs it. Absent PyYAML makes baseline stop with `yaml-unavailable` and makes confirm stop unless the live file is the byte-identical verified baseline | R8 | Gate B. Installing PyYAML is not part of this plan |
| Node major 20 or newer, and npm, on `PATH=/usr/sbin:/usr/bin:/sbin:/bin` | Preflight prints `node=ok` and `npm=present`. A binary only on another PATH is `absent` | R8 | Gate B. `npm ci` is step 4, Gate D |
| `cryptography==50.0.2` in the new runtime | Install imports `cryptography` and `yaml` from `runtime/venv/bin/python` and may run `install-control-runtime` | `docs/deploy/c08cb1e_material.py install` | Gate D. Not a preflight |
| git and systemctl on the fixed PATH | Preflight prints `git=present`. `systemctl` absence becomes `systemctl-absent` on the scope lines | R8 | Gate B |
| One loaded unit scope, gateway active and running, live `MainPID`, stable root, `FLEET_CONTROL_PYTHON` absent, `HERMES_FLEET_CONTROL_INTEGRATION=1` | Preflight `host-ready=yes` requires the scope this process can see. Exit 4 when any required fact is missing. `unit-scope=system` does not prove the hermes user unit is absent. Identity and the hermes user manager are separate Gate B commands | R8, plus required checks R6 and R7 | Gate B. Baseline checks the helper's visible scope again and then writes. Gate D waits until decision 4 is unambiguous |
| `fleet-delegation.conf` loaded, no later drop-in name, `fleet-retirement.conf` absent, `NeedDaemonReload=no`, effective unit does not pin the checkout | Preflight scope facts. Baseline stops if the retirement file is present | Preflight, then baseline | Gate B, then Gate D |
| Fleet MCP entry stable-compatible for the server named by `HERMES_FLEET_MCP_SERVER` | Preflight classifies command, cwd, and args. `redacted` fails readiness. Baseline runs `fleet_mcp_compatibility` before it writes | Preflight classification is not the full compatibility function | Gate B sees the classification. The full check is step 1, Gate D |
| Private non-empty journal dirs, and Fleet idle | The operator records a Fleet-idle assertion before any Gate B command. Preflight then prints `<scope>-journals=private-nonempty` or `blocked`. `blocked` is a STOP. A concurrent delegate, onboard, or retire can receive `delegation_in_flight`, `onboard_in_flight`, or `retire_in_flight` during the shared probe | Operator assertion, then the preflight shared-lock probe | Before Gate B execution. Do not retry in a loop |
| Credential names present, values hidden | Baseline prints `present` or `absent` for `FLEET_PROVISIONER_URL` and `FLEET_PROVISIONER_CALLER_TOKEN` | `docs/deploy/c08cb1e_material.py baseline` | Gate D. No shipped read-only command reports these two names |
| Writable private evidence directory owned by the deploying euid | Baseline creates mode `0700` and refuses a symlink, a foreign owner, or group/world write. Mode `0755` is accepted. An unsafe directory is not chmod'd | Baseline | Gate D. Preflight does not stat this path |
| Known-good stable checkout on the host | Preflight prints `stable-dir-count=1`, `stable-head-is-dcb3f950=yes`, `stable-tree-is-pinned=yes` | Preflight | Gate B |
| Provisioner witness | First run `baseline=created`, later `baseline=matched`, then `PROVISIONER OK` | `docs/deploy/c08cb1e-provisioner-witness.sh` | Gate D steps 2, 8, and 12. Not Gate B |
| Guest-node witness | `host-mutation=yes`, `baseline=created` or `baseline=matched`, `GUEST-NODE OK` | `docs/deploy/c08cb1e-guest-node-witness.sh` | Gate D steps 3, 9, and 13. Not Gate B |
| Healthy gateway before deploy | Preflight exit 0 | Preflight | Gate B, reviewed at Gate C, before Gate D |
| Network to the git origin | No shipped read-only probe. The first network use is `git fetch` inside install | Install | Gate D |

## 5. Exact preflight command inventory

The authoritative Gate B list is the Final Gate B execution sheet.
This section records what preflight does. The runnable form is
required check R8. The root form uses `env -i` and keeps `HOME`,
`PATH`, `LANG`, `PYTHONDONTWRITEBYTECODE`, and `PYTHONSAFEPATH`. The
non-root form sets `PYTHONDONTWRITEBYTECODE=1` and `PYTHONSAFEPATH=1`
inside the target user's shell and removes `PYTHONPATH` and
`PYTHONHOME` there. The wrapper does not clear the environment, so
the variables `env` passes reach `/usr/bin/python3.12`. The script
takes no arguments. Extra arguments exit 2.

| Field | Value |
| --- | --- |
| Target host | Control host only, from the `30e64213d353a487fb84d84443449461b7a76944` copy of `docs/deploy/`. Output includes `other-hosts=not-contacted` |
| Purpose | Report whether this host is ready for step 1 |
| Privileges | The named future deploying user. Root when the only loaded scope is the system unit. A user unit is not assumed to be root. This process's environment does not see the hermes user's systemd manager |
| Class | READ-ONLY for persistent files. Not operationally noninterfering. See section 6 and "Shared journal locks" |
| Writes | No intentional file, directory, chmod, fetch, install, daemon-reload, start, stop, or restart. `PYTHONDONTWRITEBYTECODE=1` closes interpreter bytecode writes, including a missing stdlib `.pyc`. Without that variable, `sys.dont_write_bytecode` is set only inside the PyYAML helpers, after the top-level standard-library imports, so a missing stdlib `.pyc` could be created. `PYTHONSAFEPATH=1` drops the script directory from `sys.path` and does not by itself disable bytecode writes. Reads can still update access times. The shared lock does not write the lock file. `sudo` may still write an authentication log or a timestamp file |
| Expected output | `preflight=c08cb1e-control`, `read-only=yes`, `diagnostic=completed`, `host-ready=yes` or `host-ready=no`, `host-ready-blockers=...`, `system-unit=`, `user-unit=`, `unit-scope=`, restart policy, triggers, classified MCP fields, `python312`, `pyyaml`, `node`, `npm`, `git`. Origin is `origin-form` and `origin-embedded-token`. The URL is not printed. Credential values are not printed. Hostnames, service names, the origin host, process identifiers, and filesystem paths may be printed. Treat the transcript as an internal operational record |
| Pass | Exit 0, `diagnostic=completed`, and `host-ready=yes`, after R1 through R7. That includes the approved hostname, a case A helper directory, the deploying user's identity, and, for a non-root user, `HOME` equal to the passwd home. Scope visibility is a separate STOP |
| Fail | Exit 4: diagnostic completed, host not ready. Exit 1: diagnostic failed. Exit 2: bad usage. `<scope>-journals=blocked` is a STOP even if other lines look healthy |
| On failure | Stop. Leave the host unchanged. Exit 4 is not a pass and does not start step 1. Do not retry repeatedly or automatically. Do not paste the transcript outside the internal review |
| Risk | Reads `/proc/<pid>/environ` and `config.yaml` in memory and prints classifications. Holds a shared lock on journal `*.lock` files long enough for an in-flight Fleet error. Spawns `hostname`, `systemctl show`, `systemctl list-units`, `git rev-parse`, `git remote get-url`, and maybe `node -p`. User `systemctl --user` runs without `XDG_RUNTIME_DIR` |

Preflight answers the following on that one host: stable HEAD and tree,
new-checkout existence, interpreter location, PyYAML importability,
node major and npm presence, unit scope, restart policy, `TriggeredBy`,
active state, live root classification, MCP field classes, delegation
and retirement drop-in facts, journal privacy, and whether `qm` is on
the fixed PATH together with `/etc/pve`. It does not answer another
machine, provisioner state directories, guest VM inventory, evidence
directory mode, the two provisioner credential names, `cryptography`
in the new venv, or network connectivity.

The following shipped commands are inventory for later gates. They are
not preflight. Running any of them is outside Gate B.

| Command | Step | Class |
| --- | --- | --- |
| `docs/deploy/c08cb1e_material.py baseline` | 1 | STATE-CHANGING |
| `docs/deploy/c08cb1e-provisioner-witness.sh` | 2, 8, 12 | LOCAL-WRITE |
| `docs/deploy/c08cb1e-guest-node-witness.sh` | 3, 9, 13 | LOCAL-WRITE |
| `docs/deploy/c08cb1e_material.py install` | 4 | STATE-CHANGING |
| `docs/deploy/c08cb1e_material.py configure` | 5 | STATE-CHANGING |
| `docs/deploy/c08cb1e_material.py restart` | 6 | STATE-CHANGING |
| `docs/deploy/c08cb1e_material.py verify` | 7 | READ-ONLY for files; takes the deploy lock. Gate E only |
| `docs/deploy/c08cb1e_material.py rollback` | 10 | STATE-CHANGING |
| `docs/deploy/c08cb1e_material.py confirm` | 11 | READ-ONLY for files; takes the deploy lock. Gate E after rollback, or Gate F's confirm |

Checks on the Provisioner or the guest node are outside Gate B.
Network reachability and guest inventory stay unresolved until Gate D.
During Gate B, every command not individually listed and approved in the Gate B command inventory is prohibited.

## Final Gate B execution sheet

Gate A accepted the planning approach at
`d04238aba3b2b107da57f0df8f80d52483d3b520`. That acceptance did not
authorize a host command. This revised sheet needs its own final
acceptance before Gate B. Gate B execution is not authorized. This
sheet does not itself authorize any command.

The operator shell for every command below is root on the Control
host. Each command names its execution user, uses absolute paths, and
includes any `cd` it needs. None of them depend on the previous working
directory or on an unstated `sudo` or `su`. Substitute the approval
placeholders before running a command. A substituted path or user must
not contain a space, a single quote, or a double quote, and a path
must not have a trailing slash. Do not invent a host, a path, a user,
or a search command.

`sudo` may append an authentication log entry and may update a
timestamp file under `/run/sudo/ts`. That is not Control deployment
state. The commands do not intentionally modify deployment files. Do
not describe this inventory as free of all filesystem effects.

### Approval record

Write this record before any host command. It is not a host command.

- Approved Control FQDN: `<UNRESOLVED: approved Control FQDN>`. R1 must print this string exactly. `hostname -f` may consult DNS or `/etc/hosts`.
- `HELPER_DIR`: `<UNRESOLVED: absolute docs/deploy directory>`
- `HELPER_PARENT`: `<UNRESOLVED: absolute parent of docs/deploy>`
- `DEPLOY_USER`: `<UNRESOLVED: deploying user>`
- Fleet idle: confirmed by `<UNRESOLVED: operator name>` at `<UNRESOLVED: time>`. That means no delegate, onboard, or retire operation is in flight.

`HELPER_DIR` must be exactly `<HELPER_PARENT>/docs/deploy`. If any
field is missing, or the directory is not already known, STOP. Do not
search the host. Do not transfer files. The resolved absolute helper
directory is part of the approval.

Prerequisites, checked from the operator's knowledge of that root
shell before R1: `sudo` is available to this shell, and `DEPLOY_USER`
is an existing account. If `sudo` is missing or the account does not
exist, STOP. Do not substitute `su`. `sudo -u` with default `env_reset`
usually sets `HOME` from the target passwd entry. Some sudoers keep
the caller's `HOME`. Assignments placed before `sudo` are not a
reliable way to pass variables. Every variable in this sheet is set
inside the target shell.

### Gate B command inventory

A passing Gate B runs the required checks in order, each one named in
the approval. Optional checks stay prohibited until the approval names
them. Naming an optional check does not make it required. During Gate
B, every command not individually listed and approved in the Gate B
command inventory is prohibited.

#### Required checks

R1. Host identity. Execution user: root. Run this before any other
host-specific check. Compare the single output line with the exact
FQDN recorded in the approval. `hostname -f` may consult DNS or
`/etc/hosts` to produce that name.

```bash
env PATH=/usr/sbin:/usr/bin:/sbin:/bin hostname -f
```

STOP if the command fails, prints nothing, or the single output line
is not exactly the approved Control FQDN.

R2. Helper directory listing. Execution user: root.

```bash
ls -ld "<HELPER_DIR>" "<HELPER_PARENT>" && cd "<HELPER_DIR>" && ls -la
```

STOP if the first character of either `ls -ld` line is `l`. STOP unless
the `ls -la` names are exactly `.`, `..`, `c08cb1e-deploy-plan.md`,
`c08cb1e-guest-node-witness.sh`, `c08cb1e-preflight.sh`,
`c08cb1e-provisioner-witness.sh`, and `c08cb1e_material.py`. Any other
entry is a STOP, including `control-first-deployment-readiness.md`,
another `.py` file, or `__pycache__`.

R3. Helper file ownership and mode. Execution user: root.

```bash
cd "<HELPER_DIR>" && stat -c '%U:%G %a %F %n' c08cb1e-deploy-plan.md c08cb1e-guest-node-witness.sh c08cb1e-preflight.sh c08cb1e-provisioner-witness.sh c08cb1e_material.py
```

Pass: every owner is `root`, every `%F` is `regular file`, the plan
markdown mode is `644`, and each of the four scripts is `755`. Exact
mode `755` is intentional. It matches git mode `100755` at
`30e64213d353a487fb84d84443449461b7a76944`. `700` and `750` are tighter
and still not a pass. `775` is group-writable and not a pass. Group is
recorded. Group is not itself a failure when the mode is exactly `644`
or `755`.

R4. Helper content hashes. Execution user: root. The working directory
is inside the helper directory so `sha256sum` prints bare filenames.

```bash
cd "<HELPER_DIR>" && sha256sum c08cb1e-preflight.sh c08cb1e_material.py
```

Pass is these two lines, in this order, with two spaces before each
bare filename:

```text
78634901d4e7c3335adf8f5c231503ddbc9322b13313178b0088f971e863cff7  c08cb1e-preflight.sh
2f54b671e58120178bfa7c84ee2d3d86c0e2df236911866b246450c9abaad60d  c08cb1e_material.py
```

Those digests were computed from
`30e64213d353a487fb84d84443449461b7a76944` and match. Git blob ids at
that commit are `5b0f3294b5ad0502777b6383262ceaf626ce20ea` for the
shell wrapper and `39b31407c5bcdf20ec05f606a23448ce8ba7451c` for the
Python helper.

R5. Directory and parent trust. Execution user: root. A relative
`HELPER_DIR` is rejected before the walk. The walk then lists
`HELPER_DIR` and every ancestor, and it stops when `dirname` returns
the same path, which is the filesystem root for an absolute path.
Read pass or fail from the `stat` columns `%U` and `%a`. The `ls -ld`
type character is the symlink check.

```bash
sh -c 'd="<HELPER_DIR>"; case "$d" in /*) ;; *) echo STOP-not-absolute; exit 1;; esac; while :; do ls -ld "$d"; stat -c "%U:%G %a %F %n" "$d"; n=$(dirname "$d"); [ "$n" = "$d" ] && break; d=$n; done'
```

STOP if the command prints `STOP-not-absolute` or exits before it
reaches the filesystem root. STOP if any component is a symlink, is
not a directory, is not owned by `root`, or is group-writable or
world-writable. The last two mode digits must not be `2`, `3`, `6`,
or `7`. An untrusted account that can modify a helper file, or
replace the helper directory entry in its parent, is a STOP.

When `DEPLOY_USER` is not root, that account must have traversal
(execute) permission on every component, including `HELPER_DIR`. Case
A ownership is `root`, so each mode must end in `5` or `7`. A missing
execute bit is a STOP. Do not chmod, chown, or otherwise change
permissions to make the path traversable.

Case A is this result together with R2, R3, and R4: a root-owned tree
the deploying account cannot modify, the exact five-file set, the
modes above, and the two digests. A directory owned or writable by
`hermes`, by `DEPLOY_USER` when that user is not root, or by any other
non-root account is not case A. It is a lower-trust writable tree. Do
not run preflight as root from that tree. Replacing it with a
root-owned copy is a separate write authorization, outside Gate B.

Case B is anything else: unknown directory, extra file, wrong mode,
wrong digest, symlink, or a writable parent. STOP and request a
separate transfer authorization. Do not copy the files under this gate.

R6. Executing-user identity and `HOME`. `evidence_root` uses
`/var/lib/hermes-control-deploy/<deploy-sha>` when the effective uid
is 0. Otherwise it uses `Path.home()`, and `Path.home()` follows
`HOME`.

When `DEPLOY_USER` is root, execution user root, without `sudo -u`:

```bash
sh -c 'id -u; id -un; h=$(getent passwd "$(id -un)" | cut -d: -f6); echo "home=$h"; echo "HOME=$HOME"'
```

Pass: `0`, then `root`. Record `home=` and `HOME`. Root evidence does
not follow `HOME`.

When `DEPLOY_USER` is not root, execution user is that account. The
environment is set inside its shell:

```bash
sudo -u "<DEPLOY_USER>" sh -c 'id -u; id -un; h=$(getent passwd "$(id -un)" | cut -d: -f6); echo "home=$h"; echo "HOME=$HOME"'
```

STOP if `id -un` is not `<DEPLOY_USER>`, if `getent` fails, or if
`HOME=` is not exactly the `home=` value. That mismatch would select
an unexpected evidence directory. Do not continue to preflight.

R7. Hermes user-manager visibility. Execution user: `hermes`, started
from the root operator shell. `$(id -u)` expands inside hermes's
shell. A root shell's own `systemctl --user` is root's manager.

```bash
sudo -u hermes sh -c 'id -un; XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user show -p LoadState --value hermes-gateway-control.service'
```

The first line must be `hermes`. A bus connection failure is unknown
visibility. It is not proof the unit is absent. This command does not
enable lingering, start a user manager, or modify systemd.

R8. Read-only preflight. No arguments. Run only after R1 through R7
have passed and the Fleet-idle assertion is recorded. The wrapper at
`30e64213d353a487fb84d84443449461b7a76944` is `exec /usr/bin/python3.12`
of the absolute helper path. That `exec` does not unset or rebuild the
environment, so variables set in the invoking shell reach the
interpreter. `/usr/bin/python3.12` is Python 3.11 or newer, so
`PYTHONSAFEPATH` is not ignored by that version. `PYTHONSAFEPATH` must
be a non-empty value. `PYTHONSAFEPATH` does not suppress `PYTHONPATH`.

When `DEPLOY_USER` is root, start from an empty environment and keep
only the variables below. The wrapper finds `dirname` and `pwd` on
`PATH`. Preflight does not call `evidence_root`. That function ignores
`HOME` when the effective uid is 0. `Path.home()` follows `HOME` only
if the live scope is a user unit and the delegation-location check
runs; `HOME=/root` is the sensible root home for that call. Preflight
does not read `USER`, `LOGNAME`, `TERM`, or `XDG_*` from its own
environment. Child commands receive a new environment from `_run`.
`LANG=C` matches that child environment. Dropping the rest also drops
`BASH_ENV`, `ENV`, `CDPATH`, `PYTHONPATH`, `PYTHONHOME`,
`PYTHONUSERBASE`, `PYTHONSTARTUP`, and `PYTHONINSPECT`.

```bash
cd "<HELPER_PARENT>" && env -i HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C PYTHONDONTWRITEBYTECODE=1 PYTHONSAFEPATH=1 docs/deploy/c08cb1e-preflight.sh
```

When `DEPLOY_USER` is not root, `sudo` `env_reset` already drops the
caller's shell variables. The target shell still removes `PYTHONPATH`
and `PYTHONHOME`, then sets the two Python variables. R5 must already
show that this user can traverse every ancestor. If preflight cannot
traverse the helper directory, STOP. Do not change permissions.

```bash
sudo -u "<DEPLOY_USER>" sh -c 'cd "<HELPER_PARENT>" && env -u PYTHONPATH -u PYTHONHOME PYTHONDONTWRITEBYTECODE=1 PYTHONSAFEPATH=1 docs/deploy/c08cb1e-preflight.sh'
```

Pass: exit 0, `diagnostic=completed`, and `host-ready=yes`. Exit 4, 1,
and 2 are not passes. Extra arguments exit 2. `<scope>-journals=blocked`
is a STOP. Do not retry repeatedly or automatically.

#### Optional checks

O1. Evidence parent. Not required for a passing Gate B. Execution user
is `DEPLOY_USER`. Run the non-root form only after R6 passed.

Root:

```bash
stat -c '%U:%G %a %F' /var/lib/hermes-control-deploy
```

Non-root. `test` refuses the stat when `HOME` is not the passwd home,
because `Path.home()` follows `HOME` and a `getent` path alone is not
that directory:

```bash
sudo -u "<DEPLOY_USER>" sh -c 'h=$(getent passwd "$(id -un)" | cut -d: -f6); echo "home=$h"; echo "HOME=$HOME"; test "$HOME" = "$h" && stat -c "%U:%G %a %F" "$HOME/.local/state/hermes-control-deploy"'
```

O2. Hermes user-unit path listing. Not required for a passing Gate B.
Execution user: root. A listing does not prove the unit is absent.
User unit files may also live in `$XDG_CONFIG_HOME/systemd/user`,
`~/.local/share/systemd/user`, `/etc/systemd/user`, or
`/usr/lib/systemd/user`.

```bash
ls -l /home/hermes/.config/systemd/user/hermes-gateway-control.service /home/hermes/.config/systemd/user/hermes-gateway-control.service.d
```

### Expected results

R1: one line, the approved Control FQDN.

R2: two directory lines whose type character is not `l`, then the
seven names listed above and no others.

R3: `root` owner, `regular file`, mode `644` for the plan markdown and
`755` for the four scripts.

R4: the two digest lines above.

R5: the command reaches the filesystem root, and every component is a
root-owned directory, not a symlink, and not group-writable or
world-writable. For a non-root deploying user, every mode ends in `5`
or `7`. `STOP-not-absolute` is a failure.

R6: the deploying uid and name. For a non-root user, `HOME` equals the
passwd home.

R7: first line `hermes`, then a `LoadState` token such as `loaded` or
`not-found`, or a manager error.

O1: owner, group, mode, and file type, or `No such file`. O2: names
and modes, or a missing-path message.

Preflight prints `preflight=c08cb1e-control`, `read-only=yes`,
`diagnostic=completed`, `host-ready=yes` or `host-ready=no`,
`host-ready-blockers=...`, `system-unit=`, `user-unit=`,
`unit-scope=`, `<scope>-journals=`, `<scope>-restart-policy=`,
`<scope>-triggered-by=`, classified MCP fields, `python312`, `pyyaml`,
`node`, `npm`, and `git`. Origin is `origin-form` and
`origin-embedded-token`. The URL is not printed. Credential values are
not printed. `system-unit=` is the system manager. `user-unit=` is the
invoking user's manager after `XDG_RUNTIME_DIR` is cleared. Compare
`system-unit=` with R7. Both `loaded` is a scope conflict.

### STOP conditions

- The approval record is missing a hostname, `HELPER_DIR`, `HELPER_PARENT`, `DEPLOY_USER`, or the Fleet-idle assertion.
- R1 fails, or the hostname differs from the approved Control FQDN. `hostname -f` may consult DNS or `/etc/hosts`. A failure or a mismatch is a STOP.
- R5 prints `STOP-not-absolute`, or `HELPER_DIR` is not an absolute path.
- R2, R3, R4, or R5 is not case A. Request a separate transfer authorization. Do not copy the files under this gate.
- A non-root deploying user cannot traverse every helper-directory ancestor. Do not change permissions.
- An untrusted account can modify the helper or replace its directory entry. Do not run preflight as root from a lower-trust writable directory.
- R6 would select an unexpected evidence directory. For a non-root user that includes `HOME` differing from the passwd home.
- `<scope>-journals=blocked`, or a Fleet delegate, onboard, or retire operation is in flight. Do not retry repeatedly or automatically.
- R7's first line is not `hermes`, or the bus connection failed, or `LoadState` was not obtained.
- STOP if: User-unit visibility not established, or conflicting gateway unit scopes detected.
- Preflight exit is 4, 1, or 2. `host-ready-blockers` is not `none`. `redacted` is treated as a successful MCP check.
- A nonzero `systemctl` result is left unclassified. It may mean the manager is unreachable. It does not by itself mean the unit is absent.
- `sudo` is missing, or `DEPLOY_USER` does not exist. Do not substitute `su`.

The shared locks do not intentionally modify persistent state. While a
shared probe is held, a concurrent delegate, onboard, or retire can
fail immediately with `delegation_in_flight`, `onboard_in_flight`, or
`retire_in_flight`. `exclusive_delegation_wait` retries
`delegation_in_flight` for 5 seconds.

`PYTHONDONTWRITEBYTECODE=1` closes interpreter bytecode writes,
including a missing standard-library `.pyc`. `sys.dont_write_bytecode`
inside the helper is set only in the PyYAML helpers, after the
top-level standard-library imports. File reads may still update access
times. Short-lived `hostname`, `systemctl`, `git`, and `node -p`
processes may appear. The shared lock is taken and released. `sudo`
may write an authentication log and a timestamp file. None of those is
an intentional persistent deployment write.

### Interpreter assumptions

These assumptions remain after R2 through R5. Directory trust does not
eliminate every Python import risk.

The wrapper does not clear the environment, and the approved command
therefore reaches `/usr/bin/python3.12` with `PYTHONSAFEPATH=1` and
`PYTHONDONTWRITEBYTECODE=1`. That path is Python 3.11 or newer by its
versioned name. This was read from the wrapper at
`30e64213d353a487fb84d84443449461b7a76944`. The Control host binary was
not executed. If that binary is not CPython 3.11+ or is a wrapper that
clears the environment before the interpreter starts, `PYTHONSAFEPATH`
would not take effect. That host binary is an unresolved security
assumption. This page does not change the helper.

On a local CPython 3.12.3, which is not the Control host,
`PYTHONSAFEPATH=1` sets `sys.flags.safe_path`. An empty value does not.
`sys.flags.no_user_site` stays `0`, and `sys.flags.isolated` stays `0`.
`PYTHONPATH` is still inserted on `sys.path`. The root command uses
`env -i`, so `PYTHONPATH` and `PYTHONHOME` are absent. The non-root
command removes both inside the target shell. System site-packages,
`.pth` files, and the user site remain on the import path. R2 through
R5 do not audit those locations.

`EXEC_ENV_KEYS` refuses `PYTHONPATH`, `PYTHONHOME`, and
`PYTHONSAFEPATH` on the fleet MCP environment during configure and
rollback. That refusal does not apply to the operator shell that
launches preflight. Preflight does not insert the provisioner checkout
on `sys.path`. That insert is only in the provisioner-witness state-dir
loader.

A directory check is a point-in-time read. Case A requires root
ownership and no group or world write so the service account cannot
swap a sibling module between the check and the exec. That still does
not audit the interpreter installation.

### Transcript handling

Keep every transcript as an internal operational record. It must not
contain credential values. It can contain hostnames, service names,
repository origins, process identifiers, and filesystem paths. Do not
paste `config.yaml`, a drop-in, an env file, or `/proc/*/environ` into
the record. Do not `cat` those files to build the transcript.

### Prohibited operations

During Gate B, every command not individually listed and approved in the Gate B command inventory is prohibited.

There is no implied authorization for commands that appear harmless.
Examples of prohibited actions:

- SSH to Provisioner or guest nodes.
- Provisioner or guest-node witness execution.
- `git fetch`, `pull`, `checkout`, or other repository writes.
- `git ls-remote` unless separately authorized.
- `qm` commands.
- `systemctl start`, `stop`, `restart`, `reload`, `daemon-reload`, `enable`, `disable`, `mask`, `kill`, `edit`, `reset-failed`, or `set-property`.
- `loginctl enable-linger`.
- Package installation.
- Baseline creation, configuration, deployment, rollback, verification, or confirmation.
- Credential or configuration inspection that prints sensitive values.

The same prohibition covers `docs/deploy/c08cb1e_material.py baseline`,
`docs/deploy/c08cb1e-provisioner-witness.sh`,
`docs/deploy/c08cb1e-guest-node-witness.sh`, and
`docs/deploy/c08cb1e_material.py` with `install`, `configure`,
`restart`, `verify`, `rollback`, or `confirm`. Enabling lingering,
starting a user manager, and modifying systemd are prohibited.
Outstanding decision 4 stays open until R7 has been approved and
reviewed. Deployment planning approval must not proceed to Gate D
until the intended service scope is unambiguous.

### Separately authorized file transfers or writes

Helper transfer, replacing a lower-trust tree with a root-owned copy,
baseline, either witness, install, configure, restart, verify,
rollback, and confirm are writes or later-gate commands. Each needs
its own later authorization. None of them is part of Gate B.

## 6. Side-effect classification

READ-ONLY means no intentional persistent change. LOCAL-WRITE means
durable evidence, logs, or artifacts, with no service or config edit.
STATE-CHANGING means a checkout, config, drop-in, process, or unit
change.

| Command | Class | Persistent effect | Transient effect |
| --- | --- | --- | --- |
| R8 in the Final Gate B execution sheet. Root: `env -i` with `HOME=/root`, the fixed `PATH`, `LANG=C`, `PYTHONDONTWRITEBYTECODE=1`, and `PYTHONSAFEPATH=1`. Non-root: those two Python variables set inside the target shell, with `PYTHONPATH` and `PYTHONHOME` removed | READ-ONLY for persistent files. Not operationally noninterfering | No intentional deployment write. `PYTHONDONTWRITEBYTECODE=1` closes interpreter bytecode writes, including a missing stdlib `.pyc`. File reads may still update access times. `sudo`, when used, may append an authentication log and may update `/run/sudo/ts`. That is not Control deployment state | Shared non-blocking lock on journal `*.lock`, released before exit. A concurrent delegate, onboard, or retire can fail immediately with `delegation_in_flight`, `onboard_in_flight`, or `retire_in_flight`. Subprocess spawns listed in section 5. `node -p` executes that one expression |
| `docs/deploy/c08cb1e_material.py baseline` | STATE-CHANGING | Creates the evidence parent when missing, chmod `0700`, then the evidence directory and mode `0600` baseline files through a staging rename. Does not restart and does not create the new checkout | Exclusive flock on the evidence parent, up to 20 seconds. Same journal shared-lock probe. Runs `fleet_mcp_compatibility` before the write |
| `docs/deploy/c08cb1e-provisioner-witness.sh` | LOCAL-WRITE | Directory mode `0700` on every run. First run writes `witness.manifest` and `identity`. A matched run does not rewrite those two files | Imports and executes the deployed state-dir loader. Reads onboarding and tombstone files to hash them. Does not restart a service. The wrapper comment says it reads; the function and the runbook's write list are the authority |
| `docs/deploy/c08cb1e-guest-node-witness.sh` | LOCAL-WRITE | Directory mode `0700`. Truncates `lock` and replaces `qm-now.txt` on every run, including a later match. First run creates `qm-baseline.txt` mode `0600`. `lock` and `qm-now.txt` follow the shell umask; the directory mode is what keeps them private | `qm list` is a hypervisor read. The script's redirects are the write. No guest start, stop, or destroy. Prints `read-only=no` before the writes |
| `docs/deploy/c08cb1e_material.py install` | STATE-CHANGING | `git init` of the new checkout, `git remote add` only for a credential-free origin, `git fetch`, `git checkout --detach` of the deploy commit. May create `runtime/venv` via `install-control-runtime` and `fleet-mcp/node_modules` via `npm ci --ignore-scripts --no-audit --no-fund` | Network fetch. Does not take the evidence flock. Does not restart the gateway |
| `docs/deploy/c08cb1e_material.py configure` | STATE-CHANGING | Evidence files `fleet-retirement.conf.desired`, `config.yaml.deployed`, `config.status`. Then may create `fleet-retirement.conf` and replace `config.yaml` through `config.yaml.c08cb1e-tmp` | Exclusive evidence flock for the whole command |
| `docs/deploy/c08cb1e_material.py restart` | STATE-CHANGING | `systemctl daemon-reload` and `systemctl restart` of this unit when the live root is still stable. `restart=skipped` when the live root is already the new checkout and the drop-in is loaded. Does not rewrite evidence files | Waits about 10 seconds. Exclusive evidence flock. `NRestarts` is printed and is not required to increase |
| `docs/deploy/c08cb1e_material.py verify` | READ-ONLY for files | No evidence write and no unit change | Exclusive evidence flock. Not a Gate B command |
| `docs/deploy/c08cb1e_material.py rollback` | STATE-CHANGING | On a safe plan that is not already stable: `systemctl stop`, copy the verified drop-in to `fleet-retirement.conf.removed`, unlink the drop-in, restore or reverse `config.yaml` when required, `daemon-reload`, `systemctl start`. An unverified drop-in or an incomplete config writes nothing and does not stop | Exclusive evidence flock. A second stop is not added if the unit returns after the config write |
| `docs/deploy/c08cb1e_material.py confirm` | READ-ONLY for files | No write | Exclusive evidence flock. Not a Gate B command |

`baseline=matched` on a witness means the saved baseline file was not
replaced. It does not mean that run wrote nothing.

## 7. Security and credential-handling

Collected output may contain key names, classifications, paths, worker
counts, unit names, and checksums. It must not contain credential
values. A preflight transcript is still an internal operational
record. It can expose infrastructure metadata: hostnames, service
names, repository origins (`origin-form` and the origin host), process
identifiers, and filesystem paths. Keep the transcript inside the
operator review. Do not treat it as a public log.

Names the procedure treats as sensitive, values never printed:
`FLEET_PROVISIONER_URL`, `FLEET_PROVISIONER_CALLER_TOKEN`, and any key
matching `TOKEN`, `SECRET`, `PASSWORD`, `PRIVATE`, `NSEC`,
`CREDENTIAL`, `KEY`, or `AUTHORIZATION`. MCP text that looks like a
token, contains `://`, `@`, `?`, or `#`, or is an unapproved flag, is
printed as `redacted`. The value after a flag other than `--version`
or `--stdio` is `redacted` too.

`FLEET_CONTROL_PYTHON` and `PATH` on the recorded fleet MCP env are
`env-exec-override` even when empty. That refusal is the fleet MCP
environment during configure and rollback. It is not the operator
shell that launches preflight. The same refusal covers
`NODE_OPTIONS`, `NODE_PATH`, `PYTHONPATH`, `PYTHONHOME`,
`PYTHONSTARTUP`, `PYTHONINSPECT`, `PYTHONEXECUTABLE`,
`PYTHONUSERBASE`, `PYTHONSAFEPATH`, `PYTHONDEVMODE`, and any key that
starts with `LD_`. The value is not printed. `NODE_ENV` is not in that
set.

`FLEET_PROVISIONER_GIT_REF` must be absent on the Provisioner. The
witness stops if it is set and does not print the value.
`HERMES_FLEET_CONTROL_INTEGRATION` must be `1` at baseline.
`HERMES_FLEET_CONTROL_ROOT`, `HERMES_FLEET_MCP_SERVER`,
`FLEET_CONTROL_HERMES_PROFILE`, `FLEET_CONTROL_PROFILES_ROOT`,
`FLEET_CONTROL_ENV_FILE`, `HERMES_HOME`, `FLEET_DELEGATION_JOURNAL_DIR`,
`FLEET_ONBOARD_JOURNAL_DIR`, and `FLEET_RETIRE_JOURNAL_DIR` are
configuration names. Preflight prints a root path only when it matches
the safe-path check; otherwise it prints `absent-or-redacted`.

Do not paste `config.yaml`, a drop-in, a unit dump, profile `.env`,
the fleet env, `/proc/<pid>/environ`, `witness.manifest`, or a journal
file into chat. Do not `cat` those files to collect a transcript.
Origin URLs with a password, `?`, `#`, or `;` are not printed and are
not written into the new git config.

Subprocess environments are replaced, so a child `git` or `node` does
not inherit the operator's secret environment. That same replacement
drops `XDG_RUNTIME_DIR`.

## 8. Rollback readiness assessment

Rollback is step 10. It is Gate F. This page does not run it.

The command reads `scope` and `stable_dir` from the evidence directory,
so an inactive or failed unit can still be classified. `MainPID` 0 is
the before value when the unit is not active and running. It plans the
drop-in and the config, and whether a stop is safe, before it changes
either file and before it stops the unit.

Evidence required before a rollback can be attempted:

- The evidence directory from step 1, mode `0700`, owned by the same euid that will run rollback. A sudo rollback after a user-unit baseline stops with `baseline is missing`.
- Files from step 1: `journals.manifest`, `fleet-delegation.conf`, `config.yaml`, `mcp-server.name`, `config.mcp-identity`, `config.mode`, `fleet.env`, `profile.env`, `unit.fragment`, `mainpid`, `stable_dir`, `scope`, `config.path`, `profile.env.path`, `fleet.env.path`, `unit.fragment.path`, `delegation.path`.
- `config.mcp-identity` is the word `compatible`, the server name, and the sha256 of the baseline config bytes. A line that is only `compatible` plus the sha256 does not match. Editing `mcp-server.name` alone does not satisfy the check.
- After step 5, also `fleet-retirement.conf.desired`, `config.yaml.deployed`, and `config.status`.
- A removed drop-in is copied to `fleet-retirement.conf.removed` inside the evidence directory, not beside the live drop-in.

`rollback=done` and `STEP 10 OK` are printed only after `systemctl start`
passes its health checks: new `MainPID`, active and running, stable
root, delegation loaded, retirement drop-in unloaded,
`FLEET_CONTROL_PYTHON` unset. `rollback=already-stable` is the success
line when the gateway is already that healthy stable unit, the drop-in
is absent, `NeedDaemonReload=no`, and the config is `unchanged` or
`preserved`. That path does not stop the unit. Re-running after
`rollback=done` is that already-stable path.

These conditions stop automatic rollback and require an operator. The
helper writes nothing and does not stop the unit unless the row says
the stop already happened.

| Condition | What the helper does | Operator action |
| --- | --- | --- |
| Unverified `fleet-retirement.conf` | No unlink, no config write, no stop, no start. `dropin-rollback=unverified` | Compare the live file with `fleet-retirement.conf.desired` on the host. Delete it only when it is a regular file and the bytes match. Do not paste either file |
| Config plan `incomplete`, including a third checkout, a bad fleet entry, `env-exec-override`, `env-overrides-root`, or `yaml-unavailable` when the bytes are not the verified baseline | No write and no stop. `config-names-new` and `rollback-detail` name the class | Edit only the fleet MCP entry named by `mcp-server.name`, then re-run rollback as the same user |
| `Restart=` empty or outside the accepted set | `restart-policy-unknown`. Reason `gateway stop not attempted` | An already-stopped unit is not refused for `Restart=` alone. A running unit with an unknown policy needs an operator decision before any stop |
| Active or unreadable socket, path, or timer in `TriggeredBy` | `activation-unit-active` or `activation-unreadable`. No stop | Leave the activation unit for the operator. A crash-loop `auto-restart` is not this refusal; the helper stops that state when the rest of the plan is safe |
| `stop-failed` or `stop-unverified`, including leftover cgroup processes | No config write and no start. Reason `gateway did not stay stopped`. If the drop-in was already unlinked, it stays unlinked | Do not assume the unit is stopped. Inspect `ActiveState`, `SubState`, `MainPID`, and the unit cgroup. Re-run only when the plan is still safe |
| Unit returns after the config write | `running-root` is `new`, `stable`, or `unknown` from the new `MainPID`. `running-root=none` only when there is no main process. No second stop. Drop-in and config status lines are not printed again | Operator incident response. The helper will not stop that process on this run |
| Evidence symlink, foreign owner, or group/world writable | Stop before a write. Unsafe modes are not chmod'd | Fix ownership outside this helper, as the same deploying user. Do not widen the mode |
| Evidence without `scope`, without `mcp-server.name`, or with a mismatched identity | Rollback stops | If retirement is absent and the gateway is still the stable checkout, remove that evidence and rerun step 1 as the same user. If a deploy is in progress, keep the evidence and do not guess the server name |
| Both scopes loaded, or neither, at step 1 | Step 1 stops. Rollback uses the saved scope and does not rediscover it | Resolve scope before a new baseline |
| Stable directory is not exactly one `dcb3f950*` checkout at the pins | Baseline and install stop | Do not create a second matching directory to force a pass |
| Origin with an embedded credential or `?`, `#`, or `;` | Install does not copy the URL | Replace the remote form outside this procedure before Gate D |
| Side-file or delegation drift | Warning only. Those files are not written. `side-file-drift=` and `delegation-drift=changed` | Rollback can still proceed. Confirm does not repair the drift |
| Journal bytes changed, or the unit is inactive so only recorded files were rehashed | Warning. Journals are not deleted. `journal-warning=none-recorded-files-only` when the recorded files still match and the unit is inactive | A new journal file is not itself a rollback failure |
| Hand `systemctl start` or `restart` while `rollback=incomplete` | The helper does not do this | Forbidden until a later run prints `rollback=done` or `rollback=already-stable` |
| PyYAML missing after a non-byte-equal edit | `yaml-unavailable` or the spelling detail. No install is attempted | Restore a byte-equal baseline or install PyYAML by a separate approved change, then re-run |

A failure after a verified stop leaves the unit stopped and does not
start an incompatible configuration. A crashed run does not print
`rollback=done`. Re-running a safe plan continues from the files on
disk. An already-stopped unit is not stopped again.

The new checkout directory stays on disk after rollback. Removing it is
not part of step 10.

## 9. Explicit STOP conditions

Stop, and do not start the next step, when any of these are true.

- This page is the only approval on hand. Gate A is not Gate B, C, D, E, or F. Gate A accepted the planning approach at `d04238aba3b2b107da57f0df8f80d52483d3b520`. This revised execution sheet still needs final acceptance.
- The command's host, euid, or argv is not the one named in the approved gate.
- `hostname -f` is not the exact approved Control FQDN, or it cannot be verified. `hostname -f` may consult DNS or `/etc/hosts`.
- Helper provenance or directory trust is not case A. That includes an extra file, `__pycache__`, a symlink, a non-root owner, a wrong mode, a wrong digest, or a directory an untrusted account can modify.
- Non-root execution would use a `HOME` that is not the deploying user's passwd home.
- Preflight exits 4, 1, or 2. Exit 4 is a finished diagnostic that is not ready.
- `<scope>-journals=blocked`, or a Fleet delegate, onboard, or retire operation is in flight. Do not retry repeatedly or automatically.
- User-unit visibility not established, or conflicting gateway unit scopes detected.
- A witness, baseline, install, configure, or restart is proposed as a preflight.
- `host-ready-blockers` is not `none`.
- `redacted` is being treated as a successful MCP check.
- The deploying user would change between steps. Later steps refuse a different euid.
- `fleet-retirement.conf` is already present at step 1.
- The stable directory count is not 1, or the HEAD or tree pin does not match.
- `FLEET_CONTROL_PYTHON` is set, or `HERMES_FLEET_CONTROL_INTEGRATION` is not `1`.
- `FLEET_PROVISIONER_GIT_REF` is set on the Provisioner.
- The origin decision is `origin-copied=no`.
- `rollback=incomplete` is printed. Leave a stopped unit stopped.
- The operator would paste an env file, `config.yaml`, a drop-in, or `/proc` environ into chat.
- The action would start, stop, or destroy a guest, or touch the operator-supplied protected identifiers VM 1035, VM 1036, or template 1000.
- The action would edit the helper, the tests, or the workflow in order to make a host pass.

## 10. Approval gates

These gates are separate. Approval of one line does not approve the next.

### Gate A — readiness plan

Gate A accepted the planning approach at
`d04238aba3b2b107da57f0df8f80d52483d3b520`. That acceptance granted no
host access and no host command. This revised execution sheet was
written after that acceptance. It requires its own final acceptance
before Gate B. This page does not grant that acceptance.

### Gate B — read-only preflight

Gate B execution is not authorized. A later approval must accept this
revised sheet and name each command it runs. Required for a passing
Gate B, in order: host identity (R1); helper provenance and directory
trust (R2 through R5); executing-user identity and `HOME` (R6); hermes
user-manager visibility (R7); read-only preflight (R8). The
evidence-parent check and the hermes user-unit `ls` are optional.
Every command, required or optional, needs its own approval line.
During Gate B, every command not individually listed and approved in
the Gate B command inventory is prohibited. Approving Gate B does not
approve deployment or a helper transfer.

### Gate C — preflight evidence review

Review the transcript as an internal operational record. List blockers.
Exit 0 with `host-ready=yes` is the only preflight pass. This review
does not authorize deployment. Unresolved Provisioner and guest-node
facts remain open because preflight did not contact those hosts.

Gate C checklist:

- `diagnostic=completed` and `host-ready=yes`, or the blockers are named and the host stays unchanged.
- `<scope>-journals` is `private-nonempty`. `journals=blocked`, or a reported in-flight Fleet failure, is a STOP. Do not ask for an automatic retry.
- Resolve every nonzero `systemctl` result. `systemctl_loaded` maps exit 127 to `systemctl-absent` and any other nonzero exit to `not-loaded`. A nonzero result may mean the manager is unreachable rather than that the unit is absent. Record which one it is.
- Compare `system-unit=` with the hermes user-manager `LoadState` from the approved scope commands. STOP if: User-unit visibility not established, or conflicting gateway unit scopes detected.
- The transcript contains no credential values. It may contain hostnames, service names, origin hosts, process identifiers, and paths. Leave it in the internal record.
- `redacted` MCP fields are unresolved configuration, not a pass.

### Gate D — deployment

A separate explicit approval is required before any of steps 1–9.
Outstanding decision 4 must already be closed: the intended service
scope is unambiguous. The approval must name the host, the user, and
the command list. Steps 2 and 3 are included only when the approval
names those hosts. A successful deploy stops after step 9.

### Gate E — post-deployment verification

After Gate D, `docs/deploy/c08cb1e_material.py verify` must print
`STEP 7 OK` with the new checkout as the running root, journals matching
the baseline, side files matching step 1, and `config.yaml` matching
`config.yaml.deployed` unless step 5 recorded `config=interpolated`.
Re-run the Provisioner witness and the guest-node witness only if Gate D
authorized them, and require `baseline=matched`. This gate does not
spawn MCP and does not call `require_tools` or `project_workers`.

### Gate F — rollback or incident response

A separate approval is required before steps 10–13, and before any
manual unit change while `rollback=incomplete`. Step 11 must print
`config-mcp=stable-compatible` and `STEP 11 OK`. Steps 12 and 13 repeat
the witnesses only when those commands were already authorized.
Incident response covers `stop-unverified`, a unit that returned after
the config write, and an unverified drop-in.

## 11. Proposed deployment sequence

This sequence is the existing runbook. It becomes executable only after
the gate named on each row.

| Order | Gate | Host | Command | Success line |
| --- | --- | --- | --- | --- |
| 0 | B, then C | Control | Required checks R1 through R8 in the Final Gate B execution sheet, in that order, plus any optional check the approval names | Exit 0, `host-ready=yes`, after a recorded Fleet-idle assertion, a matching hostname, and a case A helper directory. Decision 4 stays open until R7's first line is `hermes` and its `LoadState` agrees with `system-unit=` |
| 1 | D | Control | `docs/deploy/c08cb1e_material.py baseline` | `STEP 1 OK`, `baseline=created` or a matching re-read |
| 2 | D | Provisioner, root | `docs/deploy/c08cb1e-provisioner-witness.sh` | `baseline=created` the first time, `PROVISIONER OK` |
| 3 | D | Guest node, root | `docs/deploy/c08cb1e-guest-node-witness.sh` | `host-mutation=yes`, `baseline=created` the first time, `GUEST-NODE OK` |
| 4 | D | Control | `docs/deploy/c08cb1e_material.py install` | `STEP 4 OK` |
| 5 | D | Control | `docs/deploy/c08cb1e_material.py configure` | `STEP 5 OK` |
| 6 | D | Control | `docs/deploy/c08cb1e_material.py restart` | `STEP 6 OK` |
| 7 | E | Control | `docs/deploy/c08cb1e_material.py verify` | `STEP 7 OK` |
| 8 | E | Provisioner | step 2 command | `baseline=matched` |
| 9 | E | Guest node | step 3 command | `baseline=matched` |
| 10 | F | Control | `docs/deploy/c08cb1e_material.py rollback` | `rollback=done` or `rollback=already-stable`, then `STEP 10 OK` |
| 11 | F | Control | `docs/deploy/c08cb1e_material.py confirm` | `config-mcp=stable-compatible`, `STEP 11 OK` |
| 12 | F | Provisioner | step 2 command | `PROVISIONER OK` |
| 13 | F | Guest node | step 3 command | `GUEST-NODE OK` |

A deploy that should remain on the new checkout stops after row 9.
Rows 10–13 are recovery, not the next deploy step.

## 12. Outstanding decisions that need operator approval

1. Control, Provisioner, and guest-node hostnames, and confirmation that the roles are on separate machines.
2. System unit or user unit for `hermes-gateway-control.service`, and the euid that will own the evidence directory for every Control step.
3. Final acceptance of this revised Final Gate B execution sheet. Required checks are R1 through R8. Omitting a required check does not pass Gate B. The optional evidence-parent `stat` and the hermes `ls` stay prohibited until named. Decision 4 cannot close without R7, and R8 cannot run unless R2 through R5 are case A.
4. The intended scope of `hermes-gateway-control.service`. Preflight clears `XDG_RUNTIME_DIR`, so as root it queries root's user manager and can print `unit-scope=system` while a hermes user unit is loaded. An invisible user-only unit yields `unit-scope=neither` and exit 4, which is fail-closed. `unit-scope=system` beside a hidden user unit is not. Close this decision with the Gate B scope commands before Gate D. Deployment planning approval must not proceed until the intended service scope is unambiguous.
5. The live provisioner unit name, and approval to import the deployed state loader by running the witness under Gate D.
6. Approval to let the guest witness write VMID and status rows under Gate D, without printing `qm list` names into chat.
7. Whether PyYAML is already installed for `/usr/bin/python3.12` on the Control host. This plan does not install it.
8. Whether the fleet MCP entry is absolute paths or `${HERMES_FLEET_CONTROL_ROOT}`, and that no fleet env key is an execution override.
9. That `FLEET_CONTROL_PYTHON` and `FLEET_PROVISIONER_GIT_REF` are unset, and that the two required provisioner credential names are present. Presence is visible at baseline, which is Gate D.
10. That the stable git origin is credential-free in the helper's sense.
11. Where the fleet-delegation skill is loaded from, accepting `checkout-only-not-on-skill-path` as readiness rather than as proof the process read the file.
12. Who may approve Gate D and Gate F, as separate people or separate messages from Gate A.

## Operator checklist

```
Control first-deployment card
Helper scripts: fleet-control 30e64213d353a487fb84d84443449461b7a76944
Deploy checkout: c08cb1ebd073ee7946f49005dd45071366eeb688
Historical stable checkout: dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a
Historical provisioner: b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb
Hosts: UNRESOLVED until Gate B/D name them

[ ] Gate A accepted the planning approach at
    d04238aba3b2b107da57f0df8f80d52483d3b520.
    This revised execution sheet still needs final acceptance.
    Gate B is not authorized by this page.
[ ] A later Gate B approval records the hostname, absolute helper
    directory, its parent, and the deploying user, then names each
    command it runs. Required checks are host identity, helper
    provenance and directory trust, executing-user identity, hermes
    user-manager visibility, and read-only preflight.
[ ] Operator recorded Fleet idle before any Gate B command.
[ ] Hostname -f matches the exact approved Control FQDN before any
    other host-specific check. A failure or a mismatch is a STOP.
[ ] Helper copy is case A: exact file set, root-owned, not writable by
    an untrusted account, modes 644 and 755, and both sha256 lines
    match. Otherwise STOP and request a separate transfer
    authorization.
[ ] For a non-root deploying user, HOME equals that user's passwd home.
[ ] Preflight exit is 0, with diagnostic=completed and host-ready=yes.
[ ] Scope visibility is established and one intended scope is unambiguous.
    STOP if: User-unit visibility not established, or conflicting gateway unit scopes detected.
[ ] Gate C reviewed the internal transcript and listed blockers.
    Every nonzero systemctl result is resolved as an unreachable
    manager or an absent unit. Review is not deployment approval.
[ ] Gate D is a separate approval, and only after decision 4
    names one unambiguous scope. Not before baseline or either witness.
[ ] Steps 1–9, same Control user, stop at the first non-zero exit.
[ ] Gate E: verify prints STEP 7 OK. Witness reruns only if Gate D
    included them, and they print baseline=matched.
[ ] Gate F is a separate approval before rollback.
    Success is rollback=done or rollback=already-stable.
    While the command prints rollback=incomplete, the unit stays stopped.
[ ] Do not paste config.yaml, drop-ins, env files, or /proc environ.
    Keep the preflight transcript as an internal operational record.
[ ] Do not start, stop, or destroy a guest.
    Leave operator-supplied VM 1035, VM 1036, and template 1000 unchanged.
```
