# Guarded Control deploy for c08cb1e

Paste for `c08cb1ebd073ee7946f49005dd45071366eeb688`. Writing this page
did not deploy, restart, SSH, open a pull request, or contact a host.
Do not paste evidence, a unit dump, or an env file into chat. Output is
key names, paths, worker names, and checksums. Secret values are not printed.

Stop at the first non-zero exit. Steps 1–9 deploy. Steps 10–13 roll
back. A successful deploy stops after step 9. A later step is not a
repair. Re-pasting records a baseline once, refuses to replace it, and
skips a restart that already reached the revision it checks. It does
not delete journals, reservations, tombstones, profile files, or the
stable checkout.

On the Control host, run `docs/deploy/c08cb1e-preflight.sh` before step
1. It is strictly read-only and does not create the baseline.

`6d6e25f` repeated one ~790-line Control Python prelude in steps 1, 4,
5, 6, 7, 10, and 11. This page keeps those stop conditions once and
keeps each step's action. Steps 8 and 12 are the step 2 command. Steps
9 and 13 are the step 3 command.

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

## Assumptions

Not read from a host. Commands stop when a check fails.

- Three machines. System unit if it is the only one loaded and the
  paste runs as root; user unit if it is the only one loaded. Stop if
  both or neither are loaded. No SSH.
- Process environment, not only the unit text:
  `HERMES_FLEET_CONTROL_ROOT` on the stable checkout,
  `HERMES_FLEET_CONTROL_INTEGRATION=1`, `FLEET_CONTROL_PYTHON` unset.
- `fleet-delegation.conf` is loaded. No drop-in name sorts after
  `fleet-retirement.conf`. The earlier temporary retirement drop-in is
  already gone.
- The Fleet MCP entry named by `HERMES_FLEET_MCP_SERVER` has the stable
  prefix in `command`, `args`, or `cwd`, or it uses
  `${HERMES_FLEET_CONTROL_ROOT}`. Any other stable-path occurrence stops
  step 5.
- Journal dirs (`fleet-delegations`, `fleet-onboarding`,
  `fleet-retirements`, or absolute overrides) are non-empty and private.
  Tombstones are on the Provisioner. Checksums only.
- Provisioner `FLEET_PROVISIONER_GIT_REF` is absent. Exactly one active
  unit whose name contains `provisioner`, or is `hermes-fleet.service`
  or `fleet-provisioner.service`, and at least one tombstone file.
- Node is 20 or newer. A second paste skips `npm ci` and
  `install-control-runtime` when the import and `npm ls` already match.
- Control evidence:
  `/var/lib/hermes-control-deploy/c08cb1ebd073ee7946f49005dd45071366eeb688`
  as root, else
  `$HOME/.local/state/hermes-control-deploy/c08cb1ebd073ee7946f49005dd45071366eeb688`.
  Provisioner and Proxmox witnesses are `/var/lib/hermes-control-deploy/`
  and those pastes run as root. New directories, not profile journals.

## Open questions

`c08cb1e-preflight.sh` answers these on the Control host. It does not
see the other machines. `not-on-this-host` stays open until steps 2
and 3.

1. Hostnames, and are the three roles separate?
2. Is `hermes-gateway-control.service` a system unit or a user unit?
3. Is the stable directory the full `dcb3f950…` name, and is
   `fleet-delegation.conf` still the last loaded drop-in?
4. Absolute MCP checkout paths, or `${HERMES_FLEET_CONTROL_ROOT}`?
5. Is `FLEET_CONTROL_PYTHON` unset, and is `FLEET_PROVISIONER_GIT_REF`
   unset on the stable Provisioner?
6. Provisioner unit name, and which directory holds its tombstones?
7. Does the gateway load `skills/fleet-delegation/SKILL.md` from this
   checkout or from a profile copy? This procedure does not copy the
   skill. Tool text travels with `index.js`. `skill-load=home-skills`
   means a copy under `HERMES_HOME/skills` exists; the fleet-tip loader
   prefers that over `skills.external_dirs`. That is not a process-map
   observation.
8. Is the origin URL free of an embedded token? Step 4 stores the URL
   in the new git config and does not print it. A token stays on disk.
   `origin-embedded-token=present` is URL userinfo
   (`https://user:secret@host/...`). Scp-style `git@host:path` is not.

## Control stops

Stop, without printing a secret, if any of these hold. Key names and
paths may be printed. Do not print values whose keys match `TOKEN`,
`SECRET`, `PASSWORD`, `PRIVATE`, `NSEC`, `CREDENTIAL`, or `KEY`.

- Python 3.12 is missing or resolves inside the agent virtualenv.
- Both unit scopes are loaded, or neither is. Scope is `systemctl` or
  `systemctl --user`.
- Gateway not active, or `MainPID` is not live.
- `FLEET_CONTROL_PYTHON` is set. On step 1,
  `HERMES_FLEET_CONTROL_INTEGRATION` is not `1`. After step 6 the root
  is not the new checkout.
- Stable directory is not exactly one `dcb3f950*` checkout at the pins.
  Running root is neither that directory nor the new one. A child cwd
  is a different `/opt/hermes-fleet-control/` checkout.
- `fleet-delegation.conf` is not exactly one loaded regular file, or a
  loaded drop-in name sorts after `fleet-retirement.conf`.
- A journal dir is missing, not private (`mode & 077`), empty, or holds
  a taken `*.lock`. After step 1, the sha256 manifest must match
  `journals.manifest`.
- Fleet env file is not a regular file, lacks one
  `FLEET_PROVISIONER_URL` and one `FLEET_PROVISIONER_CALLER_TOKEN`, or
  contains `BUZZ_PRIVATE_KEY`, `BUZZ_FLEET_MEMBERSHIP_TOKEN`,
  `LITELLM_MASTER_KEY`, or `PVE_TOKEN_SECRET`.
- Profile `.env` is missing, not private, or lacks `BUZZ_PRIVATE_KEY`.
- `config.yaml`, `fleet-delegation.conf`, profile `.env`, fleet env, or
  the unit fragment differs from the step 1 baseline, except the step 5
  rewrite recorded as `config.yaml.deployed`.
- `fleet-status` names or identity projection differ from the baseline.
  The projection keeps name, declared, retained, tombstone name and
  vmid, observed state, public key hex, vmid, and onboarding id and
  status.
- Node or npm is missing. `git status --porcelain=v1 -uall` on the new
  checkout shows anything outside untracked `runtime/` and
  `fleet-mcp/node_modules/`.

Step 1 writes the baseline only on the stable checkout with
`fleet-retirement.conf` absent. Files: `journals.manifest`, copies of
`fleet-delegation.conf`, `config.yaml`, the fleet env, the profile
`.env`, and the unit fragment, plus `worker-names`,
`worker-projection.json`, `mainpid`, `nrestarts`, and `stable_dir`.
Copies are mode `0600`. The directory is mode `0700`. A later paste
compares and does not replace them.

## 1. Control — baseline

Run the preflight, then the reads above, and write that baseline.
Print scope, `ActiveState`, `NRestarts`, `MainPID`, fragment, drop-in
names, environment-file key names, process path keys, presence of
`FLEET_CONTROL_PYTHON` and the token keys, journal dirs, MCP
command/cwd/args (`[not-printed]` for an unsafe arg), worker names,
`stable`, `running-root`, and `baseline=created` or `baseline=matched`.
End `STEP 1 OK`. Do not restart or create the new checkout.

## 2. Provisioner — witness

On the Provisioner, as root. The first paste writes the witness. Steps
8 and 12 run this same command and only compare.

```bash
bash -euo pipefail <<'BASH'
echo "host-role=Provisioner hostname=$(hostname -s)"
command -v python3 >/dev/null
exec python3 - <<'PY'
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

EXPECTED = "b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb"
EVIDENCE = Path("/var/lib/hermes-control-deploy/c08cb1e-provisioner-witness")
SECRET_KEY_RE = re.compile(r"(TOKEN|SECRET|PASSWORD|PRIVATE|NSEC|CREDENTIAL|KEY)$", re.IGNORECASE)


def die(message: str) -> None:
    sys.stderr.write("STOP: " + message + "\n")
    raise SystemExit(1)


def run(argv: list[str]) -> str:
    completed = subprocess.run(argv, capture_output=True, text=True, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"})
    if completed.returncode != 0:
        die(f"command failed ({completed.returncode}): {argv[0]}")
    return completed.stdout


print(f"host-role=Provisioner hostname={os.uname().nodename}")
if os.geteuid() != 0:
    die("run this command as root on the Provisioner")
if Path("/etc/pve").is_dir() and __import__("shutil").which("qm"):
    die("this host looks like the Proxmox node")
control = subprocess.run(
    ["systemctl", "show", "-p", "LoadState", "--value", "hermes-gateway-control.service"],
    capture_output=True,
    text=True,
)
if control.returncode == 0 and control.stdout.strip() == "loaded":
    die("hermes-gateway-control.service is loaded; this is not the Provisioner command")
listing = run(["systemctl", "list-units", "--type=service", "--all", "--plain", "--no-legend"])
candidates = []
for line in listing.splitlines():
    if not line.strip():
        continue
    name = line.split()[0]
    if name.startswith("hermes-gateway") or "hermes-fleet-control" in name:
        continue
    if "provisioner" in name or name in {"hermes-fleet.service", "fleet-provisioner.service"}:
        state = run(["systemctl", "show", "-p", "ActiveState", "--value", name]).strip()
        if state == "active":
            candidates.append(name)
if len(candidates) != 1:
    die("expected exactly one active provisioner unit; found " + str(len(candidates)))
unit = candidates[0]
props = {}
for line in run(["systemctl", "show", "-p", "MainPID", "-p", "NRestarts", "-p", "ActiveState", unit]).splitlines():
    key, value = line.split("=", 1)
    props[key] = value
pid = int(props["MainPID"])
if props["ActiveState"] != "active" or pid <= 1:
    die("provisioner MainPID is not live")
raw = Path(f"/proc/{pid}/environ").read_bytes()
env = {}
for item in raw.split(b"\0"):
    if b"=" not in item:
        continue
    key, value = item.split(b"=", 1)
    env[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
if env.get("FLEET_PROVISIONER_GIT_REF", "").strip():
    die("FLEET_PROVISIONER_GIT_REF is set; stable provisioner was expected to have it absent")
cwd = Path(os.path.realpath(f"/proc/{pid}/cwd"))
top = run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"]).strip()
head = run(["git", "-C", top, "rev-parse", "HEAD"]).strip()
if head != EXPECTED:
    die("provisioner checkout HEAD is not b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb")
porcelain = run(["git", "-C", top, "status", "--porcelain=v1", "-uall"])
candidates_dirs = []
for key, value in env.items():
    if SECRET_KEY_RE.search(key) or not value.startswith("/") or re.search(r"\s", value):
        continue
    upper = key.upper()
    if not any(token in upper for token in ("STATE", "DATA", "DIR", "ROOT", "JOURNAL", "TOMB", "HOME")):
        continue
    path = Path(value)
    if path.is_dir() and not path.is_symlink() and str(path) not in {"/", "/root", "/home", "/var", "/opt"}:
        candidates_dirs.append(path)
candidates_dirs.append(cwd)
seen = []
for directory in candidates_dirs:
    resolved = str(directory.resolve())
    if resolved not in seen:
        seen.append(resolved)
found: list[Path] = []
for directory in [Path(item) for item in seen]:
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        current = Path(dirpath)
        depth = len(current.relative_to(directory).parts) if current != directory else 0
        if depth > 5:
            dirnames.clear()
            continue
        dirnames[:] = [name for name in dirnames if name not in {".git", "node_modules", "venv", "proc", "sys"}]
        for name in filenames:
            path = current / name
            lowered = str(path).lower()
            if "tombstone" in lowered or "journal" in lowered:
                if path.is_symlink() or not path.is_file():
                    die("witness path is not a regular file")
                found.append(path)
            if len(found) > 4000:
                die("witness walk is too broad")
tombstones = [path for path in found if "tombstone" in str(path).lower()]
journals = [path for path in found if "journal" in str(path).lower()]
if not tombstones:
    print("candidate-dirs=" + ",".join(seen))
    die("no tombstone file was found under the provisioner process paths")
if not journals:
    print("candidate-dirs=" + ",".join(seen))
    die("no provisioner journal file was found under the provisioner process paths")
lines = []
for path in sorted(set(found), key=lambda item: str(item)):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    mode = oct(stat.S_IMODE(path.lstat().st_mode))
    lines.append(f"{digest} {mode} {path}")
manifest = "\n".join(lines) + "\n"
EVIDENCE.mkdir(parents=True, exist_ok=True)
os.chmod(EVIDENCE, 0o700)
identity = f"unit={unit}\npid={pid}\nnrestarts={props['NRestarts']}\nhead={head}\n"
identity += "porcelain-sha256=" + hashlib.sha256(porcelain.encode("utf-8")).hexdigest() + "\n"
manifest_path = EVIDENCE / "witness.manifest"
identity_path = EVIDENCE / "identity"
if not manifest_path.exists():
    manifest_path.write_text(manifest, encoding="utf-8")
    identity_path.write_text(identity, encoding="utf-8")
    os.chmod(manifest_path, 0o600)
    os.chmod(identity_path, 0o600)
    print(f"unit={unit} pid={pid} nrestarts={props['NRestarts']} head={head}")
    print(f"tombstones={len(tombstones)} journals={len(journals)}")
    print("baseline=created")
else:
    if manifest_path.read_text(encoding="utf-8") != manifest or identity_path.read_text(encoding="utf-8") != identity:
        die("provisioner witness changed")
    print(f"unit={unit} pid={pid} nrestarts={props['NRestarts']} head={head}")
    print(f"tombstones={len(tombstones)} journals={len(journals)}")
    print("baseline=matched")
print("PROVISIONER OK")
PY
BASH
```

## 3. Proxmox — VM inventory

On the Proxmox node, as root. Does not start, stop, or destroy a guest.
Steps 9 and 13 run this same command.

```bash
bash -euo pipefail <<'BASH'
echo "host-role=Proxmox hostname=$(hostname -s)"
test "$(id -u)" -eq 0
command -v qm >/dev/null
test -d /etc/pve
if [[ "$(systemctl show -p LoadState --value hermes-gateway-control.service 2>/dev/null || true)" == "loaded" ]]; then
  echo "STOP: hermes-gateway-control.service is loaded on this host" >&2
  exit 1
fi
EVIDENCE=/var/lib/hermes-control-deploy/c08cb1e-proxmox-witness
mkdir -p -- "$EVIDENCE"
chmod 700 -- "$EVIDENCE"
exec 9>"$EVIDENCE/lock"
flock -n 9
qm list | awk 'NR > 1 && $1 ~ /^[0-9]+$/ {
  status = ""
  for (i = 1; i <= NF; i++) if ($i ~ /^(running|stopped|paused)$/) status = $i
  if (status != "") print $1, status
}' | sort > "$EVIDENCE/qm-now.txt"
if [[ ! -s "$EVIDENCE/qm-now.txt" ]]; then
  echo "STOP: qm list produced no VMID/status rows" >&2
  exit 1
fi
if [[ ! -f "$EVIDENCE/qm-baseline.txt" ]]; then
  cp -- "$EVIDENCE/qm-now.txt" "$EVIDENCE/qm-baseline.txt"
  chmod 600 -- "$EVIDENCE/qm-baseline.txt"
  echo "baseline=created lines=$(wc -l < "$EVIDENCE/qm-baseline.txt")"
else
  cmp -s -- "$EVIDENCE/qm-now.txt" "$EVIDENCE/qm-baseline.txt"
  echo "baseline=matched lines=$(wc -l < "$EVIDENCE/qm-baseline.txt")"
fi
echo "PROXMOX OK"
BASH
```

## 4. Control — install the checkout beside the stable one

The stable checkout is only read. `NEW` is
`/opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688`.

Stop if `NEW` exists and is not a git directory. Otherwise, when
`NEW/.git` is absent:

```bash
mkdir -p -- /opt/hermes-fleet-control
git init --quiet /opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688
```

If `[remote "origin"]` is absent, copy the stable origin URL into
`.git/config`. Do not print it. Then:

```bash
git -C /opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688 fetch --quiet --no-tags origin c08cb1ebd073ee7946f49005dd45071366eeb688
git -C /opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688 checkout --quiet --detach c08cb1ebd073ee7946f49005dd45071366eeb688
```

Require `HEAD` and `HEAD^{tree}` to match the deploy pins. Do not force
the worktree. Do not print fetch or checkout failure output. If
`runtime/venv/bin/python` cannot import the locked `cryptography` and
`PyYAML`:

```bash
/usr/bin/python3.12 /opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688/install-control-runtime --python /usr/bin/python3.12
```

Stdout must be exactly `NEW/runtime/venv/bin/python`. Re-import from
`cwd=/` and require `sys.prefix` to be that virtualenv. In
`NEW/fleet-mcp`, `npm ls --omit=dev --depth=0` must succeed. Only if
it fails, from that directory:

```bash
npm ci --ignore-scripts --no-audit --no-fund
```

Then `npm ls` again and `node --check` on `NEW/fleet-mcp/index.js`. Do
not print `npm ci` output. Re-check the stable pins and the porcelain
rule. Print `STEP 4 OK`.

## 5. Control — drop-in and config.yaml

Require the baseline and the new virtualenv. Re-check journals and
`fleet-delegation.conf`. Write `fleet-retirement.conf` next to it only
if absent (mode `0644`). If present, the bytes must already be the
header below plus the copied environment lines. Header:

```
# Checkout override for hermes-fleet-control c08cb1ebd073ee7946f49005dd45071366eeb688.
# Loaded after fleet-delegation.conf. That file is not modified.
[Service]
Environment=HERMES_FLEET_CONTROL_ROOT=/opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688
```

Copy every other `Environment=` line from `fleet-delegation.conf` whose
value contains the stable path. Skip `HERMES_FLEET_CONTROL_ROOT`. Stop
if a secret-like key contains that path. Otherwise replace the prefix
once. Save `fleet-retirement.conf.desired`.

From the baseline `config.yaml`: leave it when the stable path is
absent and `${HERMES_FLEET_CONTROL_ROOT}` is present
(`config=interpolated`); leave it when the new path is present and the
stable path is not (`config=unchanged`); otherwise replace every stable
path with the new path. Stop if the stable path remains, if the YAML
change is not only `mcp_servers.<name>.command`, `cwd`, or `args[n]`,
or if a changed string is not that one-prefix swap. Install with
`config.yaml.c08cb1e-tmp` opened `O_EXCL`, fsync, original mode and
owner, then `os.replace`. Record `config.yaml.deployed` and
`config.changed=yes`, or `config.changed=no` when no rewrite was
needed. Any other live bytes are a stop. Print `STEP 5 OK`.

## 6. Control — reload and restart only this gateway

Re-check journals, the desired drop-in, and the proposed `config.yaml`.
If the live root is already the new checkout and the drop-in is loaded,
print `restart=skipped` and `STEP 6 OK`. Otherwise the root must still
be stable. Same scope as step 1:

```bash
systemctl daemon-reload
systemctl restart hermes-gateway-control.service
```

`systemctl --user` when step 1 selected the user unit. Require a new
`MainPID`, `NRestarts` plus exactly one, the new root,
`FLEET_CONTROL_PYTHON` unset, the new drop-in loaded,
`fleet-delegation.conf` unchanged, children only on the new checkout,
and the journal manifest unchanged. Print `STEP 6 OK`.

## 7. Control — config, status, and tools

Running root is the new checkout. Journals, `fleet-delegation.conf`,
and `config.yaml` match the reviewed bytes. MCP `command`, `args`, and
`cwd` do not name the stable checkout; they name the new checkout or
`${HERMES_FLEET_CONTROL_ROOT}`. `fleet-status` names and projection
match the baseline.

List tools with the new MCP SDK
(`@modelcontextprotocol/sdk/dist/esm/client/index.js` and `stdio.js`),
spawning `node` on `NEW/fleet-mcp/index.js`, cwd `NEW/fleet-mcp`, env
only `PATH`, `HOME`, and `LANG=C`. Require `worker_status`,
`ensure_worker`, `onboard_worker`, `delegate_worker`, and
`retire_worker`. `send_message` must be absent. Do not call a tool.
Print `STEP 7 OK`.

## 8. Provisioner — witness unchanged

Run the step 2 command again. Require `baseline=matched`.

## 9. Proxmox — inventory unchanged

Run the step 3 command again. Require `baseline=matched`.

## 10. Control — roll back to the stable checkout

Undo of steps 5 and 6 only. Compare journals first.
`fleet-delegation.conf` must match its backup. Leave `config.yaml` if
it is the baseline. If it is the proposed bytes, write the baseline
back with the same `O_EXCL`, fsync, mode, owner, and `os.replace`. Any
other bytes stop. If `fleet-retirement.conf` exists it must match
`fleet-retirement.conf.desired`; copy it to
`fleet-retirement.conf.removed`, then unlink it. If the root is already
stable, the drop-in is gone, and `config.yaml` is the baseline, print
`rollback=already-stable` and `STEP 10 OK` without restarting.
Otherwise the same scope as step 6:

```bash
systemctl daemon-reload
systemctl restart hermes-gateway-control.service
```

Require a new `MainPID`, `NRestarts` plus one, the stable root, the
baseline config, and the drop-in absent from disk and from
`DropInPaths`. The new directory stays on disk. Journals still match.
Print `STEP 10 OK`.

## 11. Control — confirm dcb3f950 is running

Root and tree are the stable pins. The drop-in is not loaded and not
on disk. `fleet-delegation.conf` and `config.yaml` match the baseline.
Worker names and projection match. No child cwd is the new checkout.
Print `STEP 11 OK`.

## 12. Provisioner — still unchanged

Run the step 2 command again.

## 13. Proxmox — still unchanged

Run the step 3 command again.
