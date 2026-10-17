# First guarded Control deployment readiness

Planning only. Writing this page did not deploy, restart, roll back, SSH,
open a pull request, or contact a host. Approving this page is Gate A.
It does not approve a host command, a witness, a deployment, or a rollback.

Helper behavior is the merged tree
`30e64213d353a487fb84d84443449461b7a76944`. This page does not change
`c08cb1e_material.py`, the shell wrappers, the tests, or the workflow.
The commands below are copied from `docs/deploy/c08cb1e-deploy-plan.md`.
Run them only from a directory that contains a copied `docs/deploy/`
taken from that helper tree, not from the `dcb3f950` checkout and not
from the `c08cb1e` checkout. The scripts are mode `0755`.

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
command that leaves persistent host state unchanged is Control
preflight, and it inspects only the machine where it runs. Exit 4 means
the diagnostic finished and the host is not ready.

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
| Guest node | `<UNRESOLVED: guest-node hostname>` | The host where `qm` and `/etc/pve` are present. `hermes-gateway-control.service` must not be loaded | No product checkout is installed by this procedure | `/var/lib/hermes-control-deploy/c08cb1e-guest-node-witness` only, and only when the witness runs | Guest lifecycle. The witness does not start, stop, or destroy a guest. VMs 1035 and 1036 and template 1000 stay as they are; the repository does not record those IDs as a live inventory |

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
- When the gateway process is live, preflight hashes journal files and opens each journal `*.lock` with `O_RDONLY|O_NOFOLLOW`, takes `LOCK_SH|LOCK_NB`, and unlocks before it returns. It does not write lock contents. A lock that is already held becomes `journals=blocked` and exit 4.
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
- That a user-unit `systemctl --user` succeeds when `XDG_RUNTIME_DIR` is absent. The helper clears it for every subprocess. A connection failure is reported as not loaded, which fails closed, and can hide a real user unit.
- Network reachability of the git origin and of `FLEET_PROVISIONER_URL`. No shipped read-only command probes either one.
- Any previous evidence directory or an existing `fleet-retirement.conf`.

## 4. Prerequisite checklist

| Prerequisite | How it is verified | Shipped command | When |
| --- | --- | --- | --- |
| Helper copy of `docs/deploy/` from fleet-control `30e64213d353a487fb84d84443449461b7a76944`, mode `0755`, run from the directory that contains that copy | Operator places the copy before any host command. The product checkouts do not contain these commands | None | Before Gate B. Copying onto a host is a host write and needs its own approval inside Gate B's access decision. This plan does not perform that copy |
| `/usr/bin/python3.12` executable and outside `/home/hermes/.hermes/hermes-agent/venv` | Preflight prints `python312=outside-venv`. The wrapper exits 1 when the interpreter is missing | `docs/deploy/c08cb1e-preflight.sh` | Gate B on the Control host |
| PyYAML already installed for that interpreter | Preflight prints `pyyaml=present`. The helper never installs it. Absent PyYAML makes baseline stop with `yaml-unavailable` and makes confirm stop unless the live file is the byte-identical verified baseline | Same preflight | Gate B. Installing PyYAML is not part of this plan |
| Node major 20 or newer, and npm, on `PATH=/usr/sbin:/usr/bin:/sbin:/bin` | Preflight prints `node=ok` and `npm=present`. A binary only on another PATH is `absent` | Same preflight | Gate B. `npm ci` is step 4, Gate D |
| `cryptography==50.0.2` in the new runtime | Install imports `cryptography` and `yaml` from `runtime/venv/bin/python` and may run `install-control-runtime` | `docs/deploy/c08cb1e_material.py install` | Gate D. Not a preflight |
| git and systemctl on the fixed PATH | Preflight prints `git=present`. `systemctl` absence becomes `systemctl-absent` on the scope lines | Same preflight | Gate B |
| One loaded unit scope, gateway active and running, live `MainPID`, stable root, `FLEET_CONTROL_PYTHON` absent, `HERMES_FLEET_CONTROL_INTEGRATION=1` | Preflight `host-ready=yes` requires these. Exit 4 when any are missing | Same preflight | Gate B. Baseline checks them again and then writes |
| `fleet-delegation.conf` loaded, no later drop-in name, `fleet-retirement.conf` absent, `NeedDaemonReload=no`, effective unit does not pin the checkout | Preflight scope facts. Baseline stops if the retirement file is present | Preflight, then baseline | Gate B, then Gate D |
| Fleet MCP entry stable-compatible for the server named by `HERMES_FLEET_MCP_SERVER` | Preflight classifies command, cwd, and args. `redacted` fails readiness. Baseline runs `fleet_mcp_compatibility` before it writes | Preflight classification is not the full compatibility function | Gate B sees the classification. The full check is step 1, Gate D |
| Private non-empty journal dirs | Preflight prints `<scope>-journals=private-nonempty` or `blocked` | Preflight, including the transient shared lock probe | Gate B |
| Credential names present, values hidden | Baseline prints `present` or `absent` for `FLEET_PROVISIONER_URL` and `FLEET_PROVISIONER_CALLER_TOKEN` | `docs/deploy/c08cb1e_material.py baseline` | Gate D. No shipped read-only command reports these two names |
| Writable private evidence directory owned by the deploying euid | Baseline creates mode `0700` and refuses a symlink, a foreign owner, or group/world write. Mode `0755` is accepted. An unsafe directory is not chmod'd | Baseline | Gate D. Preflight does not stat this path |
| Known-good stable checkout on the host | Preflight prints `stable-dir-count=1`, `stable-head-is-dcb3f950=yes`, `stable-tree-is-pinned=yes` | Preflight | Gate B |
| Provisioner witness | First run `baseline=created`, later `baseline=matched`, then `PROVISIONER OK` | `docs/deploy/c08cb1e-provisioner-witness.sh` | Gate D steps 2, 8, and 12. Not Gate B |
| Guest-node witness | `host-mutation=yes`, `baseline=created` or `baseline=matched`, `GUEST-NODE OK` | `docs/deploy/c08cb1e-guest-node-witness.sh` | Gate D steps 3, 9, and 13. Not Gate B |
| Healthy gateway before deploy | Preflight exit 0 | Preflight | Gate B, reviewed at Gate C, before Gate D |
| Network to the git origin | No shipped read-only probe. The first network use is `git fetch` inside install | Install | Gate D |

## 5. Exact preflight command inventory

Gate B, if separately approved, contains one shipped command. It takes
no arguments. Extra arguments exit 2.

```bash
docs/deploy/c08cb1e-preflight.sh
```

| Field | Value |
| --- | --- |
| Target host | Control host only. Output includes `other-hosts=not-contacted` |
| Purpose | Report whether this host is ready for step 1 |
| Privileges | Root when the only loaded scope is the system unit. The same user who would later run baseline. A user unit is not assumed to be root |
| Class | READ-ONLY for persistent files and service state. See the transient effects in section 6 |
| Writes | No file, directory, chmod, fetch, install, daemon-reload, start, stop, or restart |
| Expected output | `preflight=c08cb1e-control`, `read-only=yes`, `diagnostic=completed`, `host-ready=yes` or `host-ready=no`, `host-ready-blockers=...`, scope, restart policy, triggers, classified MCP fields, `python312`, `pyyaml`, `node`, `npm`, `git`. Origin is `origin-form` and `origin-embedded-token`. The URL is not printed. Secret values are not printed |
| Pass | Exit 0, `diagnostic=completed`, and `host-ready=yes` |
| Fail | Exit 4: diagnostic completed, host not ready. Exit 1: diagnostic failed. Exit 2: bad usage |
| On failure | Stop. Leave the host unchanged. Exit 4 is not a pass and does not start step 1. Do not paste the transcript with a request to reveal redacted fields |
| Risk | Reads `/proc/<pid>/environ` and `config.yaml` in memory and prints classifications. Briefly holds a shared lock on journal `*.lock` files. Spawns `hostname`, `systemctl show`, `systemctl list-units`, `git rev-parse`, `git remote get-url`, and maybe `node -p`. User `systemctl --user` runs without `XDG_RUNTIME_DIR` |

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

Unshipped read-only checks. They are not helpers. This plan does not
approve them. A Gate B approval that wants one of them must name that
command in the approval. Do not pipe their output into chat if it
contains an env file or a config body.

| Proposed check | Host | Purpose | Class | Gap it would fill |
| --- | --- | --- | --- | --- |
| `stat` of the evidence parent path from section 2, only when the path already exists | Control, as the future deploying user | Owner and mode | READ-ONLY | Preflight does not stat evidence. `stat` must not be preceded by `mkdir` |
| `id -u`; `command -v qm`; `test -d /etc/pve`; `systemctl show -p LoadState --value hermes-gateway-control.service` | Guest node | The witness's checks before `mkdir` | READ-ONLY | Role separation without `qm list` and without the witness script |
| `systemctl show -p LoadState --value hermes-gateway-control.service` and `systemctl show -p ActiveState --value <unit>` for a unit already known to match the provisioner name rule | Provisioner | Confirm the Control unit is not loaded and see unit activity | READ-ONLY | Does not prove HEAD, `FLEET_PROVISIONER_GIT_REF`, or journal counts. Getting HEAD from `/proc/<pid>/cwd` reads process state and is still not the witness |
| No `git fetch`, `git ls-remote`, `npm ci`, `pip install`, or raw `qm list` | Any | Those are outside the read-only set | `git fetch` and `npm ci` are STATE-CHANGING inside install. Raw `qm list` can print names the witness file does not keep | Network and guest inventory stay unresolved until Gate D |

## 6. Side-effect classification

READ-ONLY means no intentional persistent change. LOCAL-WRITE means
durable evidence, logs, or artifacts, with no service or config edit.
STATE-CHANGING means a checkout, config, drop-in, process, or unit
change.

| Command | Class | Persistent effect | Transient effect |
| --- | --- | --- | --- |
| `docs/deploy/c08cb1e-preflight.sh` | READ-ONLY | None intended. The main script is not bytecode-cached. PyYAML import sets `sys.dont_write_bytecode` first | Shared non-blocking lock on journal `*.lock`, released before exit. Subprocess spawns listed in section 5. `node -p` executes that one expression |
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
counts, unit names, and checksums. It must not contain secret values.

Names the procedure treats as sensitive, values never printed:
`FLEET_PROVISIONER_URL`, `FLEET_PROVISIONER_CALLER_TOKEN`, and any key
matching `TOKEN`, `SECRET`, `PASSWORD`, `PRIVATE`, `NSEC`,
`CREDENTIAL`, `KEY`, or `AUTHORIZATION`. MCP text that looks like a
token, contains `://`, `@`, `?`, or `#`, or is an unapproved flag, is
printed as `redacted`. The value after a flag other than `--version`
or `--stdio` is `redacted` too.

`FLEET_CONTROL_PYTHON` and `PATH` on the recorded fleet MCP env are
`env-exec-override` even when empty. The same refusal covers
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

- This page is the only approval on hand. Gate A is not Gate B, C, D, E, or F.
- The command's host, euid, or argv is not the one named in the approved gate.
- Preflight exits 4, 1, or 2. Exit 4 is a finished diagnostic that is not ready.
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
- The action would start, stop, or destroy a guest, or touch VMs 1035 or 1036 or template 1000.
- The action would edit the helper, the tests, or the workflow in order to make a host pass.

## 10. Approval gates

These gates are separate. Approval of one line does not approve the next.

### Gate A — readiness plan

Approve or reject this page. No production access. No host command.

### Gate B — read-only preflight

A separate approval may name `docs/deploy/c08cb1e-preflight.sh` on the
Control host, with no arguments, run by the future deploying user.
That approval does not include baseline, either witness, install,
configure, restart, verify, rollback, or confirm. It does not include
`npm`, `pip`, `git fetch`, `systemctl start`, `systemctl stop`,
`systemctl restart`, or `daemon-reload`. Extra read-only checks from
section 5 need to be named in that same approval or they stay unapproved.

### Gate C — preflight evidence review

Review the transcript. List blockers. Exit 0 with `host-ready=yes` is
the only preflight pass. This review does not authorize deployment.
Unresolved Provisioner and guest-node facts remain open because
preflight did not contact those hosts.

### Gate D — deployment

A separate explicit approval is required before any of steps 1–9. The
approval must name the host, the user, and the command list. Steps 2
and 3 are included only when the approval names those hosts. A
successful deploy stops after step 9.

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
| 0 | B, then C | Control | `docs/deploy/c08cb1e-preflight.sh` | Exit 0, `host-ready=yes` |
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
3. Whether Gate B is only the shipped preflight, or also names specific unshipped `stat` / `systemctl show` checks from section 5.
4. Whether a user-unit preflight that cannot see the bus without `XDG_RUNTIME_DIR` is an acceptable fail-closed result.
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

[ ] Gate A approved (this page). No host access yet.
[ ] Gate B approved and names docs/deploy/c08cb1e-preflight.sh only.
[ ] Preflight exit 0, diagnostic=completed, host-ready=yes.
    Exit 4 is not a pass. Stop.
[ ] Gate C reviewed the transcript and listed blockers.
    Review is not deployment approval.
[ ] Gate D is a separate approval before baseline or either witness.
[ ] Steps 1–9, same Control user, stop at the first non-zero exit.
[ ] Gate E: verify prints STEP 7 OK. Witness reruns only if Gate D
    included them, and they print baseline=matched.
[ ] Gate F is a separate approval before rollback.
    rollback=incomplete: leave the unit stopped.
[ ] Do not paste config.yaml, drop-ins, env files, or /proc environ.
[ ] Do not start, stop, or destroy a guest.
    Leave VMs 1035 and 1036 and template 1000 unchanged.
```
