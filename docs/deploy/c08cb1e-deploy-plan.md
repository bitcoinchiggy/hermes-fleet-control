# Guarded Control deploy for c08cb1e

This page is a procedure for a later operator paste. Preparing it did
not deploy, restart, SSH, open a pull request, or contact a host.
Do not paste an evidence file, a unit dump, or an env file into chat.
The commands print key names, checkout paths, worker names, and
checksum results. They do not print secret values.

Stop at the first non-zero exit. A later step is not a repair for an
earlier failure. Steps 1 through 9 are the deploy. Steps 10 through 13
undo it. A successful deploy stops after step 9.

Each command is safe to paste again after it stops midway. It records
a baseline once, refuses to replace that baseline, and skips a restart
that has already reached the revision it is checking. It does not
delete journals, reservations, tombstones, profile files, or the
stable checkout.

## Verified in this repository

`main` is `c08cb1ebd073ee7946f49005dd45071366eeb688`, the merge commit
of pull request #7. Its tree is `2b8888b984634b714d62646ddd5b6f48d073d160`.

`63099c4a1f38063d2c0068fa40b94baf74bfb092` is an ancestor of that
merge. Its tree is `2a0194bb8fac5c1178a34fd079e48bb54ab9e233`.
`git diff 63099c4 c08cb1e` is only
`docs/control-onboard-validation.md`: 64 insertions and 12 deletions.
That file change is commit `5868856`, whose parent is `63099c4` and
whose tree is the merge tree. The page records the pasted retirement
run. It does not change helpers, the MCP server, or tests.

`dcb3f950` is not an ancestor of `63099c4`. The coordination-channel
commits exist on both lines (`dfaf8f9`/`295fc5d`/`dcb3f95` and
`ea596e2`/`d98951e`/`5c327c0`) and each pair has the same tree. The
merge result is still `63099c4` plus that docs file.
`dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a` is an ancestor of the merge
through pull request #6. Its tree is
`3d5f940738c5d1c0061645d06e74d3f88b034ae5`.

`git diff dcb3f950 c08cb1e` is 16 files, 2739 insertions, 25 deletions:

| Path | Change |
|---|---|
| `README.md` | Documents onboard and retire |
| `docs/control-onboard-validation.md` | Adds the pasted onboard and retirement record |
| `fleet-mcp/index.js` | Registers `onboard_worker` and `retire_worker` |
| `fleet-onboard` | New one-shot helper |
| `fleet-retire` | New one-shot helper |
| `fleet_control/authorize.py` | Delegation requires a complete onboarding journal when one is present |
| `fleet_control/errors.py` | Public errors for onboard and retire |
| `fleet_control/http.py` | `POST /v1/workers/{name}/onboard` with `{}` and `POST /v1/workers/{name}/deprovision` with `{}` or `{"confirm_retained":true}` |
| `fleet_control/onboard.py` | Reservation before one POST; uncertain results are not retried |
| `fleet_control/retire.py` | Reservation bound to name, node, VM, provenance, public key, and onboarding id; one deprovision POST |
| `skills/fleet-delegation/SKILL.md` | Tells the model how to call the two tools |
| `tests/test_fleet_control_delegate.py` | Onboarding journal gate |
| `tests/test_fleet_control_onboard.py` | New |
| `tests/test_fleet_control_retire.py` | New |
| `tests/test_publication_boundary.py` | Boundary coverage |
| `tests/test_runtime.py` | Runtime coverage |

Behavior that changes when the gateway actually runs this tree:

- `onboard_worker` submits onboarding only for a name the provisioner
  already declares. Control writes a reservation under the profile
  `fleet-onboarding` directory (or `FLEET_ONBOARD_JOURNAL_DIR`) before
  one empty POST. A later call reads status and does not submit again.
- `retire_worker` reads the worker, stores that binding, then sends one
  deprovision. The default body is `{}`. `confirm_retained: true` is a
  separate call. `retry: true` does not repeat a reserved or ambiguous
  attempt. An absent or tombstone view after acceptance reports
  completion and does not send again. The tool does not delete
  onboarding reservations, delegation journals, or tombstones.
- `delegate_worker` rejects a worker whose public status includes an
  onboarding journal that is missing `status: complete` or a valid
  `onb_` id. A worker with no onboarding journal keeps the previous
  checks.
- After restart, the model can call `onboard_worker` and
  `retire_worker`. This procedure never calls them, and it never calls
  `ensure_worker` or `delegate_worker`.

`install-control-runtime` still creates `<checkout>/runtime/venv` from
`--python /usr/bin/python3.12` and prints that interpreter path. The
lock remains `cryptography==50.0.2` and `PyYAML==6.0.2`.

## Assumptions about the live hosts

None of the following was read from a host. The commands check the
items they can see and stop when a check fails.

- Control, the Provisioner, and the Proxmox node are three machines.
  The Control command uses the system unit when that unit is loaded and
  the paste runs as root. It uses the user unit when only the user unit
  is loaded. It stops when both are loaded or neither is. It does not SSH.
- The pasted stable Control checkout is the single directory
  `/opt/hermes-fleet-control/dcb3f950*` whose `HEAD` is
  `dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a`. The new directory is
  exactly `/opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688`.
- The running unit is `hermes-gateway-control.service`. Its process
  environment, not only the unit text, has
  `HERMES_FLEET_CONTROL_ROOT` on that stable checkout,
  `HERMES_FLEET_CONTROL_INTEGRATION=1`, and an unset
  `FLEET_CONTROL_PYTHON`.
- `fleet-delegation.conf` is loaded, and no drop-in name sorts after
  `fleet-retirement.conf`. The temporary retirement drop-in from the
  earlier test is already gone.
- Profile `config.yaml` `mcp_servers` holds the Fleet server named by
  `HERMES_FLEET_MCP_SERVER`. Its `command`, `args`, or `cwd` contain
  the stable checkout prefix, or they interpolate
  `${HERMES_FLEET_CONTROL_ROOT}`. The command rewrites only that
  prefix. Any other occurrence of the stable path is a stop.
- Delegation journals, onboarding reservations, and retirement records
  are the non-empty private directories the process already resolves
  (`fleet-delegations`, `fleet-onboarding`, `fleet-retirements`, or
  the absolute overrides). Tombstone files are on the Provisioner.
  This procedure checksums them and does not create or delete them.
- The pasted Provisioner checkout is `HEAD`
  `b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb`, with
  `FLEET_PROVISIONER_GIT_REF` absent. The active unit name contains
  `provisioner`, or is `hermes-fleet.service` or
  `fleet-provisioner.service`. Tombstone and journal files are under a
  directory named by that process. The Provisioner command stops when
  it cannot find exactly one such unit or any tombstone file.
- Hermes on Control is the pinned agent the operator already deployed.
  Public commit `e29f306cdbc7728f297d218be6ecda511bcf450a` exists on
  `NousResearch/hermes-agent` and reads MCP `command`, `args`, and
  `cwd` from profile `config.yaml`. This repository cannot see a
  public `fleet` branch, and this procedure does not change the agent
  checkout.
- Control can reach the git origin, the Python package index, and the
  npm registry while it fills the new checkout. A second paste skips
  that download when the virtualenv and `npm ls` already match.
- Node on Control is 20 or newer. `/usr/bin/python3.12` exists and is
  outside `/home/hermes/.hermes/hermes-agent/venv`.
- Evidence on Control is
  `/var/lib/hermes-control-deploy/c08cb1ebd073ee7946f49005dd45071366eeb688`
  when the paste runs as root. A user-unit paste uses
  `$HOME/.local/state/hermes-control-deploy/c08cb1ebd073ee7946f49005dd45071366eeb688`.
  Provisioner and Proxmox witnesses are
  `/var/lib/hermes-control-deploy/` on those hosts and those pastes run
  as root. The directories are new. They are not profile journals.

## Open questions before the first paste

1. What are the hostnames, and are the three roles actually separate?
2. Is `hermes-gateway-control.service` a system unit or a user unit?
3. Is the stable directory the full `dcb3f950…` name, and is
   `fleet-delegation.conf` still the last loaded drop-in?
4. Does the Fleet MCP entry use absolute checkout paths or
   `${HERMES_FLEET_CONTROL_ROOT}`?
5. Is `FLEET_CONTROL_PYTHON` unset, and is `FLEET_PROVISIONER_GIT_REF`
   unset on the stable Provisioner?
6. What is the Provisioner unit name, and which directory holds its
   tombstones? The command searches process paths and stops if that
   search is empty or too broad.
7. Does the gateway load `skills/fleet-delegation/SKILL.md` from this
   checkout or from a copy under the profile? This procedure does not
   copy the skill. The MCP tool descriptions travel with `index.js`.
8. Is the origin URL free of an embedded token? The fetch stores the
   URL in the new checkout's git config and does not print it. A token
   in that URL is still present on disk.

### 1. Control — read the running gateway and record the baseline

On the Control host, confirm the live process, systemd `EnvironmentFiles=`,
drop-ins, MCP paths, profile and fleet env key names, and the journal
directories. The first successful paste writes the baseline. A later paste
compares journals, `fleet-delegation.conf`, the profile `.env`, and the
fleet env file with that baseline and does not replace it.

```bash
bash -euo pipefail <<'BASH'
echo "host-role=Control hostname=$(hostname -s)"
test -x /usr/bin/python3.12
exec /usr/bin/python3.12 - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

UNIT = "hermes-gateway-control.service"
SHA = "c08cb1ebd073ee7946f49005dd45071366eeb688"
STABLE_SHA = "dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a"
TREE = "2b8888b984634b714d62646ddd5b6f48d073d160"
STABLE_TREE = "3d5f940738c5d1c0061645d06e74d3f88b034ae5"
PROVISIONER_SHA = "b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb"
NEW = Path("/opt/hermes-fleet-control") / SHA


def evidence_root() -> Path:
    """Root-owned witness, or the invoking user's state dir for a user unit."""
    if os.geteuid() == 0:
        return Path("/var/lib/hermes-control-deploy") / SHA
    return Path.home() / ".local/state/hermes-control-deploy" / SHA


EVIDENCE = evidence_root()
AGENT_VENV = Path("/home/hermes/.hermes/hermes-agent/venv")
PY = Path("/usr/bin/python3.12")
DROPIN_NAME = "fleet-retirement.conf"
PRIOR_DROPIN = "fleet-delegation.conf"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PRIVATE|NSEC|CREDENTIAL|KEY)$|^(AUTHORIZATION)$",
    re.IGNORECASE,
)
PATH_KEYS = {
    "HERMES_FLEET_CONTROL_ROOT",
    "HERMES_HOME",
    "FLEET_CONTROL_ENV_FILE",
    "FLEET_CONTROL_PROFILES_ROOT",
    "FLEET_DELEGATION_JOURNAL_DIR",
    "FLEET_ONBOARD_JOURNAL_DIR",
    "FLEET_RETIRE_JOURNAL_DIR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
}
PRESENCE_KEYS = (
    "BUZZ_PRIVATE_KEY",
    "FLEET_PROVISIONER_CALLER_TOKEN",
    "BUZZ_FLEET_MEMBERSHIP_TOKEN",
    "LITELLM_MASTER_KEY",
    "PVE_TOKEN_SECRET",
    "FLEET_CONTROL_PYTHON",
)


def die(message: str) -> None:
    sys.stderr.write("STOP: " + message + "\n")
    raise SystemExit(1)


def run(argv: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        err = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        safe = ""
        if err and len(err[-1]) < 240 and "://" not in err[-1] and "@" not in err[-1]:
            safe = ": " + err[-1]
        die(f"command failed ({completed.returncode}): {argv[0]}{safe}")
    return completed.stdout.decode("utf-8", "replace")


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git_out(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args], env=git_env()).strip()


def require_python312() -> None:
    if not PY.is_file() or not os.access(PY, os.X_OK):
        die("/usr/bin/python3.12 is missing or not executable")
    real = Path(os.path.realpath(PY))
    agent = AGENT_VENV.resolve() if AGENT_VENV.exists() else AGENT_VENV
    if real == agent or str(real).startswith(str(agent) + os.sep):
        die("/usr/bin/python3.12 resolves inside the Hermes agent virtualenv")


def systemctl_scope() -> list[str]:
    def loaded(user: bool) -> bool:
        argv = ["systemctl"]
        if user:
            argv.append("--user")
        argv.extend(["show", "-p", "LoadState", "--value", UNIT])
        completed = subprocess.run(argv, capture_output=True, text=True)
        return completed.returncode == 0 and completed.stdout.strip() == "loaded"

    system_loaded = loaded(False)
    user_loaded = loaded(True)
    if system_loaded and user_loaded:
        die("both system and user hermes-gateway-control.service are loaded")
    if system_loaded:
        if os.geteuid() != 0:
            die("the system unit requires this command to run as root")
        return ["systemctl"]
    if user_loaded:
        return ["systemctl", "--user"]
    die("hermes-gateway-control.service is not loaded")


def show(ctl: list[str], *props: str) -> dict[str, str]:
    text = run([*ctl, "show", *[f"-p{prop}" for prop in props], "--value", UNIT])
    lines = text.splitlines()
    if len(lines) != len(props):
        # systemctl --value prints one line per property; empty values still occupy a line
        # only when at least one property is empty at the end. Re-read without relying on blanks.
        raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
        found: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            found[key] = value
        missing = [prop for prop in props if prop not in found]
        if missing:
            die("systemctl show omitted properties")
        return {prop: found[prop] for prop in props}
    return dict(zip(props, lines))


def show_safe(ctl: list[str]) -> dict[str, str]:
    props = (
        "LoadState",
        "ActiveState",
        "SubState",
        "MainPID",
        "NRestarts",
        "FragmentPath",
        "DropInPaths",
        "EnvironmentFiles",
        "User",
        "Group",
        "WorkingDirectory",
        "ExecMainStartTimestamp",
    )
    raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
    found: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in props:
            found[key] = value
    missing = [prop for prop in props if prop not in found]
    if missing:
        die("systemctl show omitted " + ",".join(missing))
    return {prop: found[prop] for prop in props}


def read_environ(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    env: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            env[key.decode("utf-8")] = value.decode("utf-8")
        except UnicodeDecodeError:
            die("gateway environ has a non-utf8 entry")
    return env


def descendants(pid: int) -> list[int]:
    found: list[int] = []

    def walk(parent: int) -> None:
        child_file = Path(f"/proc/{parent}/task/{parent}/children")
        try:
            text = child_file.read_text()
        except OSError:
            return
        for token in text.split():
            child = int(token)
            found.append(child)
            walk(child)

    walk(pid)
    return found


def checkout_dirs_of(pid: int) -> list[Path]:
    paths: list[Path] = []
    for proc in [pid, *descendants(pid)]:
        link = Path(f"/proc/{proc}/cwd")
        try:
            cwd = Path(os.path.realpath(link))
        except OSError:
            continue
        text = str(cwd)
        marker = "/opt/hermes-fleet-control/"
        if marker in text:
            root = Path(text.split(marker, 1)[0] + marker + text.split(marker, 1)[1].split("/", 1)[0])
            paths.append(root)
    return paths


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.lstat().st_mode))


def regular_files(directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        die(f"not a real directory: {directory}")
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        current = Path(dirpath)
        if current.is_symlink():
            die(f"symlink inside witness tree: {current}")
        dirnames[:] = sorted(name for name in dirnames if name not in {".git"})
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                die(f"symlink inside witness tree: {path}")
            if path.is_file():
                found.append(path)
    return found


def manifest_lines(paths: list[Path]) -> str:
    lines = []
    for path in sorted(paths, key=lambda item: str(item)):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            die(f"not a regular file: {path}")
        lines.append(f"{sha256_file(path)} {file_mode(path)} {path}")
    return "\n".join(lines) + ("\n" if lines else "")


def hold_manifest(path: Path, text: str, *, create: bool) -> None:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current != text:
            die(f"baseline differs and will not be replaced: {path.name}")
        return
    if not create:
        die(f"baseline is missing: {path.name}")
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def copy_once(source: Path, dest: Path) -> None:
    if source.is_symlink() or not source.is_file():
        die(f"refusing to back up a non-regular file: {source}")
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if dest.exists():
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            die(f"backup already exists and differs: {dest.name}")
        return
    dest.write_bytes(data)
    os.chmod(dest, 0o600)


def discover_stable() -> Path:
    root = Path("/opt/hermes-fleet-control")
    if not root.is_dir():
        die("/opt/hermes-fleet-control is absent")
    matches = sorted(path for path in root.glob("dcb3f950*") if path.is_dir() and not path.is_symlink())
    if len(matches) != 1:
        die("expected exactly one /opt/hermes-fleet-control/dcb3f950* checkout")
    stable = matches[0]
    if stable.resolve() == NEW.resolve():
        die("stable and new checkout paths are the same")
    if git_out(stable, "rev-parse", "HEAD") != STABLE_SHA:
        die("stable checkout HEAD is not dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a")
    if git_out(stable, "rev-parse", "HEAD^{tree}") != STABLE_TREE:
        die("stable checkout tree is not the dcb3f950 tree")
    return stable


def origin_description(repo: Path) -> str:
    url = git_out(repo, "remote", "get-url", "origin")
    if "://" not in url and ":" in url:
        return "origin=scp-like"
    if "@" in url.split("://", 1)[-1].split("/", 1)[0]:
        return "origin=url-with-userinfo"
    scheme, rest = url.split("://", 1)
    host = rest.split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", host):
        return "origin=present"
    return f"origin={scheme}://{host}"


def journal_dirs(env: dict[str, str]) -> dict[str, Path]:
    profile = env.get("FLEET_CONTROL_HERMES_PROFILE", "")
    if not NAME_RE.fullmatch(profile):
        die("FLEET_CONTROL_HERMES_PROFILE is absent or not a profile name")
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    if not root.startswith("/"):
        die("profiles root is not absolute")
    overrides = {
        "delegations": env.get("FLEET_DELEGATION_JOURNAL_DIR") or str(Path(root) / profile / "fleet-delegations"),
        "onboarding": env.get("FLEET_ONBOARD_JOURNAL_DIR") or str(Path(root) / profile / "fleet-onboarding"),
        "retirements": env.get("FLEET_RETIRE_JOURNAL_DIR") or str(Path(root) / profile / "fleet-retirements"),
    }
    paths = {name: Path(value) for name, value in overrides.items()}
    for path in paths.values():
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            die(f"journal directory is absent: {path}")
        mode = stat.S_IMODE(path.lstat().st_mode)
        if mode & 0o077:
            die(f"journal directory is not private: {path}")
    return paths


def private_dir_files(path: Path) -> list[Path]:
    files = regular_files(path)
    if not files:
        die(f"journal directory is empty: {path}")
    for file in files:
        if file.name.endswith(".lock"):
            fd = os.open(file, os.O_RDONLY)
            try:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                die(f"journal lock is held: {file.name}")
            finally:
                os.close(fd)
    return files


def parse_env_assignments(path: Path) -> list[tuple[str, str]]:
    if path.is_symlink() or not path.is_file():
        die(f"env file is not a regular file: {path}")
    rows: list[tuple[str, str]] = []
    for raw in path.read_bytes().splitlines():
        if raw.endswith(b"\\"):
            die("env file has a continuation line; refusing to parse it")
        line = raw.decode("utf-8", "replace").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            die("env file has a line without an assignment")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            die("env file has an unusual key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        rows.append((key, value))
    return rows


def classify_value(key: str, value: str) -> str:
    if value == "":
        return f"{key}=empty"
    if key in PATH_KEYS and value.startswith("/") and not re.search(r"\s", value):
        return f"{key}={value}"
    if key == "FLEET_PROVISIONER_URL":
        if value.startswith("https://") and "@" not in value and " " not in value:
            return "FLEET_PROVISIONER_URL=https-origin"
        return "FLEET_PROVISIONER_URL=present-not-printed"
    if SECRET_KEY_RE.search(key) or key in PRESENCE_KEYS:
        return f"{key}=present"
    return f"{key}=present"


def env_report(rows: list[tuple[str, str]]) -> list[str]:
    return [classify_value(key, value) for key, value in rows]


def require_assignment(rows: list[tuple[str, str]], key: str) -> str:
    values = [value for name, value in rows if name == key]
    if len(values) != 1 or values[0] == "":
        die(f"{key} is not present exactly once")
    return values[0]


def dropin_paths(shown: dict[str, str]) -> list[Path]:
    text = shown.get("DropInPaths", "").strip()
    if not text:
        die("the gateway unit has no drop-ins")
    return [Path(part) for part in text.split()]


def environment_files(shown: dict[str, str]) -> list[Path]:
    text = shown.get("EnvironmentFiles", "").strip()
    if text in {"", "[not set]", "n/a"}:
        return []
    paths = []
    for match in re.findall(r"-?(/[^()\s]+)", text):
        paths.append(Path(match))
    return paths


def prior_dropin(paths: list[Path]) -> Path:
    matches = [path for path in paths if path.name == PRIOR_DROPIN]
    if len(matches) != 1:
        die("fleet-delegation.conf is not exactly one loaded drop-in")
    path = matches[0]
    if path.is_symlink() or not path.is_file():
        die("fleet-delegation.conf is not a regular file")
    names = sorted(path.name for path in paths)
    if any(name > DROPIN_NAME for name in names):
        die("a drop-in sorts after fleet-retirement.conf")
    return path


def desired_dropin(prior: Path, stable: Path, new: Path) -> str:
    lines = [
        "# Checkout override for hermes-fleet-control " + SHA + ".",
        "# Loaded after fleet-delegation.conf. That file is not modified.",
        "[Service]",
        f"Environment=HERMES_FLEET_CONTROL_ROOT={new}",
    ]
    for raw in prior.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("Environment="):
            continue
        body = line[len("Environment=") :]
        if len(body) >= 2 and body[0] == body[-1] == '"':
            body = body[1:-1]
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        if key == "HERMES_FLEET_CONTROL_ROOT":
            if not value.startswith(str(stable)):
                die("fleet-delegation.conf roots the checkout somewhere else")
            continue
        if str(stable) in value:
            if SECRET_KEY_RE.search(key):
                die("a secret-like drop-in key contains the checkout path")
            lines.append(f"Environment={key}={value.replace(str(stable), str(new), 1)}")
    text = "\n".join(lines) + "\n"
    if "\n" in text.strip().split("HERMES_FLEET_CONTROL_ROOT=", 1)[-1].split("\n", 1)[0]:
        die("drop-in path is not a single line")
    return text


def yaml_loader():
    stable = discover_stable()
    candidate = stable / "runtime" / "venv" / "bin" / "python"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    die("stable checkout has no runtime/venv/bin/python to parse config.yaml")


def mcp_view(config_path: Path, parser: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink():
    raise SystemExit("config.yaml is a symlink")
text = path.read_text(encoding="utf-8")
import yaml
data = yaml.safe_load(text)
if not isinstance(data, dict):
    raise SystemExit("config.yaml is not a mapping")
servers = data.get("mcp_servers")
if not isinstance(servers, dict):
    raise SystemExit("mcp_servers is absent")
view = {}
for name, cfg in servers.items():
    if not isinstance(cfg, dict):
        raise SystemExit("mcp server entry is not a mapping")
    args = cfg.get("args")
    if args is None:
        args = []
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise SystemExit("mcp args are not strings")
    command = cfg.get("command")
    cwd = cfg.get("cwd")
    if command is not None and not isinstance(command, str):
        raise SystemExit("mcp command is not a string")
    if cwd is not None and not isinstance(cwd, str):
        raise SystemExit("mcp cwd is not a string")
    env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
    view[name] = {
        "command": command,
        "args": args,
        "cwd": cwd,
        "env_keys": sorted(str(key) for key in env),
    }
json.dump({"text_sha": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(), "servers": view}, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(config_path)], text=True)
    return json.loads(raw)


def config_path_from(env: dict[str, str]) -> Path:
    profile = env["FLEET_CONTROL_HERMES_PROFILE"]
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    path = Path(root) / profile / "config.yaml"
    if path.is_symlink() or not path.is_file():
        die("profile config.yaml is absent")
    return path


def rewrite_config(text: str, stable: Path, new: Path) -> tuple[str, str]:
    """Return (new_text, reason). reason is unchanged, interpolated, or rewritten."""
    stable_text = str(stable)
    new_text = str(new)
    if stable_text not in text and new_text not in text and "${HERMES_FLEET_CONTROL_ROOT}" in text:
        return text, "interpolated"
    if stable_text not in text and new_text in text:
        return text, "unchanged"
    if stable_text not in text:
        die("config.yaml does not reference the stable checkout or HERMES_FLEET_CONTROL_ROOT")
    return text.replace(stable_text, new_text), "rewritten"


def mcp_path_changed(before: dict, after: dict) -> bool:
    if before.keys() != after.keys():
        die("mcp server names would change")
    for name in before:
        for field in ("command", "args", "cwd", "env_keys"):
            if before[name][field] != after[name][field]:
                if field == "env_keys":
                    die("mcp env keys would change")
                old = before[name][field]
                new = after[name][field]
                if isinstance(old, list):
                    if not isinstance(new, list) or len(old) != len(new):
                        die("mcp args shape would change")
                    for left, right in zip(old, new):
                        if right != left.replace(str(discover_stable()), str(NEW)):
                            die("an mcp arg change is not the checkout prefix")
                elif isinstance(old, str):
                    if new != old.replace(str(discover_stable()), str(NEW)):
                        die("an mcp path change is not the checkout prefix")
                elif old is None and new is None:
                    continue
                else:
                    die("mcp field type would change")
    return True


def status_env(env_file: Path, gateway_env: dict[str, str]) -> dict[str, str]:
    child = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": gateway_env.get("HOME", "/root"),
        "LANG": "C",
        "FLEET_CONTROL_ENV_FILE": str(env_file),
    }
    for key in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE"):
        value = gateway_env.get(key, "")
        if value.startswith("/") and Path(value).exists() and not Path(value).is_symlink():
            child[key] = value
    return child


def run_status(checkout: Path, env_file: Path, gateway_env: dict[str, str], args: list[str]) -> dict:
    binary = checkout / "runtime" / "venv" / "bin" / "python"
    script = checkout / "fleet-status"
    if not binary.is_file() or not script.is_file():
        die("fleet-status runtime is absent in " + checkout.name)
    completed = subprocess.run(
        [str(binary), str(script), *args],
        cwd="/",
        env=status_env(env_file, gateway_env),
        capture_output=True,
    )
    if completed.returncode != 0:
        die("authenticated status read failed")
    if len(completed.stdout) > 1_000_000:
        die("status response is too large")
    try:
        body = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        die("status response is not json")
    if not isinstance(body, dict):
        die("status response is not an object")
    return body


def worker_names(body: dict) -> list[str]:
    if body.get("api_version") != "v1" or body.get("kind") != "WorkerList":
        die("status list is not a WorkerList")
    workers = body.get("workers")
    names: list[str] = []
    if isinstance(workers, list):
        for item in workers:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
            else:
                die("worker list entry has no name")
    elif isinstance(workers, dict):
        names.extend(str(key) for key in workers)
    else:
        die("workers field is not a list")
    for name in names:
        if not NAME_RE.fullmatch(name):
            die("worker list contains a name that is not safe to record")
    return sorted(set(names))


def project_worker(body: dict) -> dict:
    if body.get("api_version") != "v1" or body.get("kind") != "Worker":
        die("status read is not one worker")
    observed = body.get("observed") if isinstance(body.get("observed"), dict) else {}
    onboarding = body.get("onboarding") if isinstance(body.get("onboarding"), dict) else None
    tombstone = body.get("tombstone")
    tombstone_view = None
    if isinstance(tombstone, dict):
        tombstone_view = {
            "name": tombstone.get("name"),
            "vmid": tombstone.get("vmid"),
        }
    return {
        "name": body.get("name"),
        "declared": body.get("declared"),
        "retained": body.get("retained"),
        "tombstone": tombstone_view,
        "observed_state": observed.get("state"),
        "public_key_hex": observed.get("buzz_public_key_hex"),
        "vmid": observed.get("vmid"),
        "onboarding_id": None if onboarding is None else onboarding.get("id"),
        "onboarding_status": None if onboarding is None else onboarding.get("status"),
    }


def read_text(path: Path) -> str:
    if not path.is_file():
        die(f"missing evidence {path.name}")
    return path.read_text(encoding="utf-8")


def prepare_evidence() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.chmod(EVIDENCE, 0o700)
    if EVIDENCE.is_symlink():
        die("evidence directory is a symlink")


def lock_evidence() -> None:
    prepare_evidence()
    lock_path = EVIDENCE / "lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        die("another paste holds the evidence lock")
    # Hold the lock for the process lifetime.
    os.dup2(fd, 9)


def gateway_pid(shown: dict[str, str]) -> int:
    if shown["ActiveState"] != "active":
        die("hermes-gateway-control.service is not active")
    try:
        pid = int(shown["MainPID"])
    except ValueError:
        die("MainPID is not numeric")
    if pid <= 1 or not Path(f"/proc/{pid}").exists():
        die("MainPID is not a live process")
    return pid


def require_checkout_identity(path: Path, commit: str, tree: str) -> None:
    if git_out(path, "rev-parse", "HEAD") != commit:
        die(path.name + " HEAD is not " + commit)
    if git_out(path, "rev-parse", "HEAD^{tree}") != tree:
        die(path.name + " tree does not match")


def porcelain_allowed(repo: Path) -> None:
    text = run(["git", "-C", str(repo), "status", "--porcelain=v1", "-uall"], env=git_env())
    for line in text.splitlines():
        if len(line) < 4:
            die("unexpected git status line")
        path = line[3:]
        if " -> " in path:
            die("checkout has a rename")
        if not (
            path == "runtime"
            or path.startswith("runtime/")
            or path == "fleet-mcp/node_modules"
            or path.startswith("fleet-mcp/node_modules/")
        ):
            die("new checkout has an unexpected untracked or modified path")
        if not line.startswith("?? "):
            die("new checkout has a tracked change")


def yaml_leaves(parser: Path, path: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
import yaml
data = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
leaves = {}
def walk(obj, prefix):
    if isinstance(obj, dict):
        for key, value in obj.items():
            walk(value, f"{prefix}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            walk(value, f"{prefix}[{index}]")
    else:
        leaves[prefix] = obj
walk(data, "")
json.dump(leaves, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(path)], text=True)
    body = json.loads(raw)
    if not isinstance(body, dict):
        die("config.yaml leaves are not an object")
    return body


def assert_checkout_swap(old_leaves: dict, new_leaves: dict, stable: Path, new: Path) -> None:
    allowed = re.compile(r"^\.mcp_servers\.[^.]+\.(command|cwd|args\[\d+\])$")
    keys = set(old_leaves) | set(new_leaves)
    for key in sorted(keys):
        left = old_leaves.get(key)
        right = new_leaves.get(key)
        if left == right:
            continue
        if not allowed.fullmatch(key):
            die("config.yaml would change a field other than mcp command, args, or cwd")
        if not isinstance(left, str) or not isinstance(right, str):
            die("mcp path field is not a string")
        if right != left.replace(str(stable), str(new)):
            die("mcp path change is not the checkout prefix")


def node_bin() -> Path:
    found = shutil.which("node")
    if not found:
        die("node is not on PATH")
    path = Path(found)
    if not path.is_file() or not os.access(path, os.X_OK):
        die("node is not executable")
    version = run([str(path), "--version"]).strip()
    match = re.fullmatch(r"v(\d+)\..*", version)
    if not match or int(match.group(1)) < 20:
        die("node is older than 20")
    return path


def npm_bin() -> Path:
    found = shutil.which("npm")
    if not found:
        die("npm is not on PATH")
    path = Path(found)
    if not os.access(path, os.X_OK):
        die("npm is not executable")
    return path

print(f"host-role=Control hostname={os.uname().nodename}")
require_python312()
lock_evidence()
ctl = systemctl_scope()
(EVIDENCE / "systemctl").write_text(" ".join(ctl) + "\n", encoding="utf-8")
os.chmod(EVIDENCE / "systemctl", 0o600)
shown = show_safe(ctl)
pid = gateway_pid(shown)
env = read_environ(pid)
if env.get("FLEET_CONTROL_PYTHON", "").strip():
    die("FLEET_CONTROL_PYTHON is set on the running gateway")
if env.get("HERMES_FLEET_CONTROL_INTEGRATION") != "1":
    die("HERMES_FLEET_CONTROL_INTEGRATION is not 1")
stable = discover_stable()
root = env.get("HERMES_FLEET_CONTROL_ROOT", "")
if Path(root).resolve() != stable.resolve() and Path(root).resolve() != NEW.resolve():
    die("running HERMES_FLEET_CONTROL_ROOT is neither the stable nor the new checkout")
require_checkout_identity(Path(root), STABLE_SHA if Path(root).resolve() == stable.resolve() else SHA, STABLE_TREE if Path(root).resolve() == stable.resolve() else TREE)
child_roots = {path.resolve() for path in checkout_dirs_of(pid)}
if any(path != Path(root).resolve() for path in child_roots):
    die("a gateway child is using a different hermes-fleet-control checkout")
paths = dropin_paths(shown)
prior = prior_dropin(paths)
retirement = prior.with_name(DROPIN_NAME)
if retirement.exists() and not (EVIDENCE / "journals.manifest").exists():
    die("fleet-retirement.conf exists and there is no baseline yet")
dirs = journal_dirs(env)
files: list[Path] = []
for directory in dirs.values():
    files.extend(private_dir_files(directory))
config = config_path_from(env)
parser = yaml_loader()
view = mcp_view(config, parser)
server_name = env.get("HERMES_FLEET_MCP_SERVER", "")
if not NAME_RE.fullmatch(server_name) or server_name not in view["servers"]:
    die("HERMES_FLEET_MCP_SERVER does not name a configured MCP server")
server = view["servers"][server_name]
env_file = Path(env.get("FLEET_CONTROL_ENV_FILE", ""))
if not env_file.is_absolute() or env_file.is_symlink() or not env_file.is_file():
    die("FLEET_CONTROL_ENV_FILE is not a regular file")
fleet_rows = parse_env_assignments(env_file)
require_assignment(fleet_rows, "FLEET_PROVISIONER_URL")
require_assignment(fleet_rows, "FLEET_PROVISIONER_CALLER_TOKEN")
for forbidden in ("BUZZ_PRIVATE_KEY", "BUZZ_FLEET_MEMBERSHIP_TOKEN", "LITELLM_MASTER_KEY", "PVE_TOKEN_SECRET"):
    if any(key == forbidden for key, _value in fleet_rows):
        die("fleet env file contains a forbidden key")
profile = env["FLEET_CONTROL_HERMES_PROFILE"]
profiles_root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
profile_env = Path(profiles_root) / profile / ".env"
if profile_env.is_symlink() or not profile_env.is_file():
    die("profile .env is absent")
if stat.S_IMODE(profile_env.lstat().st_mode) & 0o077:
    die("profile .env is not private")
profile_rows = parse_env_assignments(profile_env)
require_assignment(profile_rows, "BUZZ_PRIVATE_KEY")
node = node_bin()
npm = npm_bin()
print("node=" + run([str(node), "--version"]).strip())
print("npm=" + npm.name)
print(f"scope={'user' if '--user' in ctl else 'system'}")
print(f"active={shown['ActiveState']} nrestarts={shown['NRestarts']} mainpid={pid}")
print(f"fragment={shown['FragmentPath']}")
print("dropins=" + ",".join(path.name for path in paths))
print("environment-files=" + ("none" if not environment_files(shown) else str(len(environment_files(shown)))))
print("fleet-env-listed-in-EnvironmentFiles=" + ("yes" if env_file in environment_files(shown) else "no"))
for path in environment_files(shown):
    if path.is_symlink() or not path.is_file():
        die(f"EnvironmentFile is not a regular file: {path}")
    print("environment-file-keys=" + ",".join(key for key, _value in parse_env_assignments(path)))
print("process-path-keys:")
for key in sorted(PATH_KEYS):
    if key in env:
        print(classify_value(key, env[key]))
print("process-presence:")
for key in PRESENCE_KEYS:
    print(f"{key}={'present' if env.get(key, '').strip() else 'absent'}")
print("fleet-env=" + ",".join(env_report(fleet_rows)))
print("profile-env-keys=" + ",".join(key for key, _value in profile_rows))
print(f"profile-env-mode={file_mode(profile_env)} bytes={profile_env.stat().st_size}")
print(f"journals delegations={dirs['delegations']} onboarding={dirs['onboarding']} retirements={dirs['retirements']}")
safe_args = []
for arg in server["args"]:
    if re.fullmatch(r"[A-Za-z0-9_./:${}-]+", arg or ""):
        safe_args.append(arg)
    else:
        safe_args.append("[not-printed]")
print(
    f"mcp-server={server_name} command={server['command']} cwd={server['cwd']} "
    f"args={' '.join(safe_args) if safe_args else 'none'} env-keys={','.join(server['env_keys']) or 'none'}"
)
checkout = stable if Path(root).resolve() == stable.resolve() else NEW
listed = run_status(checkout, env_file, env, [])
names = worker_names(listed)
print("worker-names=" + ",".join(names))
projection_text = json.dumps(
    {name: project_worker(run_status(checkout, env_file, env, [name])) for name in names},
    sort_keys=True,
) + "\n"
baseline_exists = (EVIDENCE / "journals.manifest").exists()
if not baseline_exists:
    if Path(root).resolve() != stable.resolve():
        die("refusing to create a baseline while the gateway is not on the stable checkout")
    if retirement.exists():
        die("refusing to create a baseline while fleet-retirement.conf exists")
hold_manifest(EVIDENCE / "journals.manifest", manifest_lines(files), create=not baseline_exists)
for source, dest in (
    (prior, EVIDENCE / "fleet-delegation.conf"),
    (config, EVIDENCE / "config.yaml.baseline"),
    (env_file, EVIDENCE / "fleet.env.baseline"),
    (profile_env, EVIDENCE / "profile.env.baseline"),
    (Path(shown["FragmentPath"]), EVIDENCE / "unit.baseline"),
):
    if not dest.exists():
        if baseline_exists:
            die(f"baseline is incomplete, missing {dest.name}")
        copy_once(source, dest)
changed = (EVIDENCE / "config.changed").read_text(encoding="utf-8").strip() if (EVIDENCE / "config.changed").exists() else ""
if changed == "yes":
    deployed = EVIDENCE / "config.yaml.deployed"
    if sha256_file(config) != sha256_file(deployed):
        die("config.yaml matches neither the recorded deploy copy nor a fresh baseline")
elif sha256_file(config) != sha256_file(EVIDENCE / "config.yaml.baseline"):
    die("config.yaml changed before this procedure recorded a deploy edit")
if sha256_file(prior) != sha256_file(EVIDENCE / "fleet-delegation.conf"):
    die("fleet-delegation.conf changed")
if sha256_file(profile_env) != sha256_file(EVIDENCE / "profile.env.baseline"):
    die("profile .env changed")
if sha256_file(env_file) != sha256_file(EVIDENCE / "fleet.env.baseline"):
    die("fleet env file changed")
fragment = Path(shown["FragmentPath"])
if fragment.is_file() and (EVIDENCE / "unit.baseline").exists():
    if sha256_file(fragment) != sha256_file(EVIDENCE / "unit.baseline"):
        die("unit fragment changed")
hold_manifest(EVIDENCE / "worker-names", "\n".join(names) + "\n", create=not (EVIDENCE / "worker-names").exists())
hold_manifest(EVIDENCE / "worker-projection.json", projection_text, create=not (EVIDENCE / "worker-projection.json").exists())
if not (EVIDENCE / "mainpid").exists():
    (EVIDENCE / "mainpid").write_text(str(pid) + "\n", encoding="utf-8")
    (EVIDENCE / "nrestarts").write_text(shown["NRestarts"] + "\n", encoding="utf-8")
    os.chmod(EVIDENCE / "mainpid", 0o600)
    os.chmod(EVIDENCE / "nrestarts", 0o600)
(EVIDENCE / "stable_dir").write_text(str(stable) + "\n", encoding="utf-8")
os.chmod(EVIDENCE / "stable_dir", 0o600)
print(f"stable={stable}")
print(f"running-root={root}")
print(f"baseline={'created' if not baseline_exists else 'matched'}")
print("STEP 1 OK")
PY
BASH
```

### 2. Provisioner — read the revision, journals, and tombstones

On the Provisioner, confirm the active provisioner unit is `HEAD`
`b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb`, `FLEET_PROVISIONER_GIT_REF` is
absent, and tombstone and journal files can be checksummed. The first paste
writes the witness. A later paste, including steps 8 and 12, only compares.

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

### 3. Proxmox node — read VMID and status

On the Proxmox node, record each VMID and its `running`, `stopped`, or
`paused` status. This command does not start, stop, or destroy a guest.

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

### 4. Control — install the new checkout beside the stable one

On the Control host, create `/opt/hermes-fleet-control/c08cb1ebd073ee7946f49005dd45071366eeb688`,
fetch that commit, and check it out detached. Require its tree to be
`2b8888b984634b714d62646ddd5b6f48d073d160`. In that directory only, run
`install-control-runtime --python /usr/bin/python3.12` when the virtualenv
is missing or fails its import check, then `npm ci --ignore-scripts
--no-audit --no-fund` in `fleet-mcp` when `npm ls` does not already match.
The stable checkout is only read.

```bash
bash -euo pipefail <<'BASH'
echo "host-role=Control hostname=$(hostname -s)"
test -x /usr/bin/python3.12
exec /usr/bin/python3.12 - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

UNIT = "hermes-gateway-control.service"
SHA = "c08cb1ebd073ee7946f49005dd45071366eeb688"
STABLE_SHA = "dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a"
TREE = "2b8888b984634b714d62646ddd5b6f48d073d160"
STABLE_TREE = "3d5f940738c5d1c0061645d06e74d3f88b034ae5"
PROVISIONER_SHA = "b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb"
NEW = Path("/opt/hermes-fleet-control") / SHA


def evidence_root() -> Path:
    """Root-owned witness, or the invoking user's state dir for a user unit."""
    if os.geteuid() == 0:
        return Path("/var/lib/hermes-control-deploy") / SHA
    return Path.home() / ".local/state/hermes-control-deploy" / SHA


EVIDENCE = evidence_root()
AGENT_VENV = Path("/home/hermes/.hermes/hermes-agent/venv")
PY = Path("/usr/bin/python3.12")
DROPIN_NAME = "fleet-retirement.conf"
PRIOR_DROPIN = "fleet-delegation.conf"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PRIVATE|NSEC|CREDENTIAL|KEY)$|^(AUTHORIZATION)$",
    re.IGNORECASE,
)
PATH_KEYS = {
    "HERMES_FLEET_CONTROL_ROOT",
    "HERMES_HOME",
    "FLEET_CONTROL_ENV_FILE",
    "FLEET_CONTROL_PROFILES_ROOT",
    "FLEET_DELEGATION_JOURNAL_DIR",
    "FLEET_ONBOARD_JOURNAL_DIR",
    "FLEET_RETIRE_JOURNAL_DIR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
}
PRESENCE_KEYS = (
    "BUZZ_PRIVATE_KEY",
    "FLEET_PROVISIONER_CALLER_TOKEN",
    "BUZZ_FLEET_MEMBERSHIP_TOKEN",
    "LITELLM_MASTER_KEY",
    "PVE_TOKEN_SECRET",
    "FLEET_CONTROL_PYTHON",
)


def die(message: str) -> None:
    sys.stderr.write("STOP: " + message + "\n")
    raise SystemExit(1)


def run(argv: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        err = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        safe = ""
        if err and len(err[-1]) < 240 and "://" not in err[-1] and "@" not in err[-1]:
            safe = ": " + err[-1]
        die(f"command failed ({completed.returncode}): {argv[0]}{safe}")
    return completed.stdout.decode("utf-8", "replace")


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git_out(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args], env=git_env()).strip()


def require_python312() -> None:
    if not PY.is_file() or not os.access(PY, os.X_OK):
        die("/usr/bin/python3.12 is missing or not executable")
    real = Path(os.path.realpath(PY))
    agent = AGENT_VENV.resolve() if AGENT_VENV.exists() else AGENT_VENV
    if real == agent or str(real).startswith(str(agent) + os.sep):
        die("/usr/bin/python3.12 resolves inside the Hermes agent virtualenv")


def systemctl_scope() -> list[str]:
    def loaded(user: bool) -> bool:
        argv = ["systemctl"]
        if user:
            argv.append("--user")
        argv.extend(["show", "-p", "LoadState", "--value", UNIT])
        completed = subprocess.run(argv, capture_output=True, text=True)
        return completed.returncode == 0 and completed.stdout.strip() == "loaded"

    system_loaded = loaded(False)
    user_loaded = loaded(True)
    if system_loaded and user_loaded:
        die("both system and user hermes-gateway-control.service are loaded")
    if system_loaded:
        if os.geteuid() != 0:
            die("the system unit requires this command to run as root")
        return ["systemctl"]
    if user_loaded:
        return ["systemctl", "--user"]
    die("hermes-gateway-control.service is not loaded")


def show(ctl: list[str], *props: str) -> dict[str, str]:
    text = run([*ctl, "show", *[f"-p{prop}" for prop in props], "--value", UNIT])
    lines = text.splitlines()
    if len(lines) != len(props):
        # systemctl --value prints one line per property; empty values still occupy a line
        # only when at least one property is empty at the end. Re-read without relying on blanks.
        raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
        found: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            found[key] = value
        missing = [prop for prop in props if prop not in found]
        if missing:
            die("systemctl show omitted properties")
        return {prop: found[prop] for prop in props}
    return dict(zip(props, lines))


def show_safe(ctl: list[str]) -> dict[str, str]:
    props = (
        "LoadState",
        "ActiveState",
        "SubState",
        "MainPID",
        "NRestarts",
        "FragmentPath",
        "DropInPaths",
        "EnvironmentFiles",
        "User",
        "Group",
        "WorkingDirectory",
        "ExecMainStartTimestamp",
    )
    raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
    found: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in props:
            found[key] = value
    missing = [prop for prop in props if prop not in found]
    if missing:
        die("systemctl show omitted " + ",".join(missing))
    return {prop: found[prop] for prop in props}


def read_environ(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    env: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            env[key.decode("utf-8")] = value.decode("utf-8")
        except UnicodeDecodeError:
            die("gateway environ has a non-utf8 entry")
    return env


def descendants(pid: int) -> list[int]:
    found: list[int] = []

    def walk(parent: int) -> None:
        child_file = Path(f"/proc/{parent}/task/{parent}/children")
        try:
            text = child_file.read_text()
        except OSError:
            return
        for token in text.split():
            child = int(token)
            found.append(child)
            walk(child)

    walk(pid)
    return found


def checkout_dirs_of(pid: int) -> list[Path]:
    paths: list[Path] = []
    for proc in [pid, *descendants(pid)]:
        link = Path(f"/proc/{proc}/cwd")
        try:
            cwd = Path(os.path.realpath(link))
        except OSError:
            continue
        text = str(cwd)
        marker = "/opt/hermes-fleet-control/"
        if marker in text:
            root = Path(text.split(marker, 1)[0] + marker + text.split(marker, 1)[1].split("/", 1)[0])
            paths.append(root)
    return paths


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.lstat().st_mode))


def regular_files(directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        die(f"not a real directory: {directory}")
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        current = Path(dirpath)
        if current.is_symlink():
            die(f"symlink inside witness tree: {current}")
        dirnames[:] = sorted(name for name in dirnames if name not in {".git"})
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                die(f"symlink inside witness tree: {path}")
            if path.is_file():
                found.append(path)
    return found


def manifest_lines(paths: list[Path]) -> str:
    lines = []
    for path in sorted(paths, key=lambda item: str(item)):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            die(f"not a regular file: {path}")
        lines.append(f"{sha256_file(path)} {file_mode(path)} {path}")
    return "\n".join(lines) + ("\n" if lines else "")


def hold_manifest(path: Path, text: str, *, create: bool) -> None:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current != text:
            die(f"baseline differs and will not be replaced: {path.name}")
        return
    if not create:
        die(f"baseline is missing: {path.name}")
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def copy_once(source: Path, dest: Path) -> None:
    if source.is_symlink() or not source.is_file():
        die(f"refusing to back up a non-regular file: {source}")
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if dest.exists():
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            die(f"backup already exists and differs: {dest.name}")
        return
    dest.write_bytes(data)
    os.chmod(dest, 0o600)


def discover_stable() -> Path:
    root = Path("/opt/hermes-fleet-control")
    if not root.is_dir():
        die("/opt/hermes-fleet-control is absent")
    matches = sorted(path for path in root.glob("dcb3f950*") if path.is_dir() and not path.is_symlink())
    if len(matches) != 1:
        die("expected exactly one /opt/hermes-fleet-control/dcb3f950* checkout")
    stable = matches[0]
    if stable.resolve() == NEW.resolve():
        die("stable and new checkout paths are the same")
    if git_out(stable, "rev-parse", "HEAD") != STABLE_SHA:
        die("stable checkout HEAD is not dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a")
    if git_out(stable, "rev-parse", "HEAD^{tree}") != STABLE_TREE:
        die("stable checkout tree is not the dcb3f950 tree")
    return stable


def origin_description(repo: Path) -> str:
    url = git_out(repo, "remote", "get-url", "origin")
    if "://" not in url and ":" in url:
        return "origin=scp-like"
    if "@" in url.split("://", 1)[-1].split("/", 1)[0]:
        return "origin=url-with-userinfo"
    scheme, rest = url.split("://", 1)
    host = rest.split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", host):
        return "origin=present"
    return f"origin={scheme}://{host}"


def journal_dirs(env: dict[str, str]) -> dict[str, Path]:
    profile = env.get("FLEET_CONTROL_HERMES_PROFILE", "")
    if not NAME_RE.fullmatch(profile):
        die("FLEET_CONTROL_HERMES_PROFILE is absent or not a profile name")
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    if not root.startswith("/"):
        die("profiles root is not absolute")
    overrides = {
        "delegations": env.get("FLEET_DELEGATION_JOURNAL_DIR") or str(Path(root) / profile / "fleet-delegations"),
        "onboarding": env.get("FLEET_ONBOARD_JOURNAL_DIR") or str(Path(root) / profile / "fleet-onboarding"),
        "retirements": env.get("FLEET_RETIRE_JOURNAL_DIR") or str(Path(root) / profile / "fleet-retirements"),
    }
    paths = {name: Path(value) for name, value in overrides.items()}
    for path in paths.values():
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            die(f"journal directory is absent: {path}")
        mode = stat.S_IMODE(path.lstat().st_mode)
        if mode & 0o077:
            die(f"journal directory is not private: {path}")
    return paths


def private_dir_files(path: Path) -> list[Path]:
    files = regular_files(path)
    if not files:
        die(f"journal directory is empty: {path}")
    for file in files:
        if file.name.endswith(".lock"):
            fd = os.open(file, os.O_RDONLY)
            try:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                die(f"journal lock is held: {file.name}")
            finally:
                os.close(fd)
    return files


def parse_env_assignments(path: Path) -> list[tuple[str, str]]:
    if path.is_symlink() or not path.is_file():
        die(f"env file is not a regular file: {path}")
    rows: list[tuple[str, str]] = []
    for raw in path.read_bytes().splitlines():
        if raw.endswith(b"\\"):
            die("env file has a continuation line; refusing to parse it")
        line = raw.decode("utf-8", "replace").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            die("env file has a line without an assignment")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            die("env file has an unusual key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        rows.append((key, value))
    return rows


def classify_value(key: str, value: str) -> str:
    if value == "":
        return f"{key}=empty"
    if key in PATH_KEYS and value.startswith("/") and not re.search(r"\s", value):
        return f"{key}={value}"
    if key == "FLEET_PROVISIONER_URL":
        if value.startswith("https://") and "@" not in value and " " not in value:
            return "FLEET_PROVISIONER_URL=https-origin"
        return "FLEET_PROVISIONER_URL=present-not-printed"
    if SECRET_KEY_RE.search(key) or key in PRESENCE_KEYS:
        return f"{key}=present"
    return f"{key}=present"


def env_report(rows: list[tuple[str, str]]) -> list[str]:
    return [classify_value(key, value) for key, value in rows]


def require_assignment(rows: list[tuple[str, str]], key: str) -> str:
    values = [value for name, value in rows if name == key]
    if len(values) != 1 or values[0] == "":
        die(f"{key} is not present exactly once")
    return values[0]


def dropin_paths(shown: dict[str, str]) -> list[Path]:
    text = shown.get("DropInPaths", "").strip()
    if not text:
        die("the gateway unit has no drop-ins")
    return [Path(part) for part in text.split()]


def environment_files(shown: dict[str, str]) -> list[Path]:
    text = shown.get("EnvironmentFiles", "").strip()
    if text in {"", "[not set]", "n/a"}:
        return []
    paths = []
    for match in re.findall(r"-?(/[^()\s]+)", text):
        paths.append(Path(match))
    return paths


def prior_dropin(paths: list[Path]) -> Path:
    matches = [path for path in paths if path.name == PRIOR_DROPIN]
    if len(matches) != 1:
        die("fleet-delegation.conf is not exactly one loaded drop-in")
    path = matches[0]
    if path.is_symlink() or not path.is_file():
        die("fleet-delegation.conf is not a regular file")
    names = sorted(path.name for path in paths)
    if any(name > DROPIN_NAME for name in names):
        die("a drop-in sorts after fleet-retirement.conf")
    return path


def desired_dropin(prior: Path, stable: Path, new: Path) -> str:
    lines = [
        "# Checkout override for hermes-fleet-control " + SHA + ".",
        "# Loaded after fleet-delegation.conf. That file is not modified.",
        "[Service]",
        f"Environment=HERMES_FLEET_CONTROL_ROOT={new}",
    ]
    for raw in prior.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("Environment="):
            continue
        body = line[len("Environment=") :]
        if len(body) >= 2 and body[0] == body[-1] == '"':
            body = body[1:-1]
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        if key == "HERMES_FLEET_CONTROL_ROOT":
            if not value.startswith(str(stable)):
                die("fleet-delegation.conf roots the checkout somewhere else")
            continue
        if str(stable) in value:
            if SECRET_KEY_RE.search(key):
                die("a secret-like drop-in key contains the checkout path")
            lines.append(f"Environment={key}={value.replace(str(stable), str(new), 1)}")
    text = "\n".join(lines) + "\n"
    if "\n" in text.strip().split("HERMES_FLEET_CONTROL_ROOT=", 1)[-1].split("\n", 1)[0]:
        die("drop-in path is not a single line")
    return text


def yaml_loader():
    stable = discover_stable()
    candidate = stable / "runtime" / "venv" / "bin" / "python"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    die("stable checkout has no runtime/venv/bin/python to parse config.yaml")


def mcp_view(config_path: Path, parser: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink():
    raise SystemExit("config.yaml is a symlink")
text = path.read_text(encoding="utf-8")
import yaml
data = yaml.safe_load(text)
if not isinstance(data, dict):
    raise SystemExit("config.yaml is not a mapping")
servers = data.get("mcp_servers")
if not isinstance(servers, dict):
    raise SystemExit("mcp_servers is absent")
view = {}
for name, cfg in servers.items():
    if not isinstance(cfg, dict):
        raise SystemExit("mcp server entry is not a mapping")
    args = cfg.get("args")
    if args is None:
        args = []
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise SystemExit("mcp args are not strings")
    command = cfg.get("command")
    cwd = cfg.get("cwd")
    if command is not None and not isinstance(command, str):
        raise SystemExit("mcp command is not a string")
    if cwd is not None and not isinstance(cwd, str):
        raise SystemExit("mcp cwd is not a string")
    env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
    view[name] = {
        "command": command,
        "args": args,
        "cwd": cwd,
        "env_keys": sorted(str(key) for key in env),
    }
json.dump({"text_sha": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(), "servers": view}, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(config_path)], text=True)
    return json.loads(raw)


def config_path_from(env: dict[str, str]) -> Path:
    profile = env["FLEET_CONTROL_HERMES_PROFILE"]
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    path = Path(root) / profile / "config.yaml"
    if path.is_symlink() or not path.is_file():
        die("profile config.yaml is absent")
    return path


def rewrite_config(text: str, stable: Path, new: Path) -> tuple[str, str]:
    """Return (new_text, reason). reason is unchanged, interpolated, or rewritten."""
    stable_text = str(stable)
    new_text = str(new)
    if stable_text not in text and new_text not in text and "${HERMES_FLEET_CONTROL_ROOT}" in text:
        return text, "interpolated"
    if stable_text not in text and new_text in text:
        return text, "unchanged"
    if stable_text not in text:
        die("config.yaml does not reference the stable checkout or HERMES_FLEET_CONTROL_ROOT")
    return text.replace(stable_text, new_text), "rewritten"


def mcp_path_changed(before: dict, after: dict) -> bool:
    if before.keys() != after.keys():
        die("mcp server names would change")
    for name in before:
        for field in ("command", "args", "cwd", "env_keys"):
            if before[name][field] != after[name][field]:
                if field == "env_keys":
                    die("mcp env keys would change")
                old = before[name][field]
                new = after[name][field]
                if isinstance(old, list):
                    if not isinstance(new, list) or len(old) != len(new):
                        die("mcp args shape would change")
                    for left, right in zip(old, new):
                        if right != left.replace(str(discover_stable()), str(NEW)):
                            die("an mcp arg change is not the checkout prefix")
                elif isinstance(old, str):
                    if new != old.replace(str(discover_stable()), str(NEW)):
                        die("an mcp path change is not the checkout prefix")
                elif old is None and new is None:
                    continue
                else:
                    die("mcp field type would change")
    return True


def status_env(env_file: Path, gateway_env: dict[str, str]) -> dict[str, str]:
    child = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": gateway_env.get("HOME", "/root"),
        "LANG": "C",
        "FLEET_CONTROL_ENV_FILE": str(env_file),
    }
    for key in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE"):
        value = gateway_env.get(key, "")
        if value.startswith("/") and Path(value).exists() and not Path(value).is_symlink():
            child[key] = value
    return child


def run_status(checkout: Path, env_file: Path, gateway_env: dict[str, str], args: list[str]) -> dict:
    binary = checkout / "runtime" / "venv" / "bin" / "python"
    script = checkout / "fleet-status"
    if not binary.is_file() or not script.is_file():
        die("fleet-status runtime is absent in " + checkout.name)
    completed = subprocess.run(
        [str(binary), str(script), *args],
        cwd="/",
        env=status_env(env_file, gateway_env),
        capture_output=True,
    )
    if completed.returncode != 0:
        die("authenticated status read failed")
    if len(completed.stdout) > 1_000_000:
        die("status response is too large")
    try:
        body = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        die("status response is not json")
    if not isinstance(body, dict):
        die("status response is not an object")
    return body


def worker_names(body: dict) -> list[str]:
    if body.get("api_version") != "v1" or body.get("kind") != "WorkerList":
        die("status list is not a WorkerList")
    workers = body.get("workers")
    names: list[str] = []
    if isinstance(workers, list):
        for item in workers:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
            else:
                die("worker list entry has no name")
    elif isinstance(workers, dict):
        names.extend(str(key) for key in workers)
    else:
        die("workers field is not a list")
    for name in names:
        if not NAME_RE.fullmatch(name):
            die("worker list contains a name that is not safe to record")
    return sorted(set(names))


def project_worker(body: dict) -> dict:
    if body.get("api_version") != "v1" or body.get("kind") != "Worker":
        die("status read is not one worker")
    observed = body.get("observed") if isinstance(body.get("observed"), dict) else {}
    onboarding = body.get("onboarding") if isinstance(body.get("onboarding"), dict) else None
    tombstone = body.get("tombstone")
    tombstone_view = None
    if isinstance(tombstone, dict):
        tombstone_view = {
            "name": tombstone.get("name"),
            "vmid": tombstone.get("vmid"),
        }
    return {
        "name": body.get("name"),
        "declared": body.get("declared"),
        "retained": body.get("retained"),
        "tombstone": tombstone_view,
        "observed_state": observed.get("state"),
        "public_key_hex": observed.get("buzz_public_key_hex"),
        "vmid": observed.get("vmid"),
        "onboarding_id": None if onboarding is None else onboarding.get("id"),
        "onboarding_status": None if onboarding is None else onboarding.get("status"),
    }


def read_text(path: Path) -> str:
    if not path.is_file():
        die(f"missing evidence {path.name}")
    return path.read_text(encoding="utf-8")


def prepare_evidence() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.chmod(EVIDENCE, 0o700)
    if EVIDENCE.is_symlink():
        die("evidence directory is a symlink")


def lock_evidence() -> None:
    prepare_evidence()
    lock_path = EVIDENCE / "lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        die("another paste holds the evidence lock")
    # Hold the lock for the process lifetime.
    os.dup2(fd, 9)


def gateway_pid(shown: dict[str, str]) -> int:
    if shown["ActiveState"] != "active":
        die("hermes-gateway-control.service is not active")
    try:
        pid = int(shown["MainPID"])
    except ValueError:
        die("MainPID is not numeric")
    if pid <= 1 or not Path(f"/proc/{pid}").exists():
        die("MainPID is not a live process")
    return pid


def require_checkout_identity(path: Path, commit: str, tree: str) -> None:
    if git_out(path, "rev-parse", "HEAD") != commit:
        die(path.name + " HEAD is not " + commit)
    if git_out(path, "rev-parse", "HEAD^{tree}") != tree:
        die(path.name + " tree does not match")


def porcelain_allowed(repo: Path) -> None:
    text = run(["git", "-C", str(repo), "status", "--porcelain=v1", "-uall"], env=git_env())
    for line in text.splitlines():
        if len(line) < 4:
            die("unexpected git status line")
        path = line[3:]
        if " -> " in path:
            die("checkout has a rename")
        if not (
            path == "runtime"
            or path.startswith("runtime/")
            or path == "fleet-mcp/node_modules"
            or path.startswith("fleet-mcp/node_modules/")
        ):
            die("new checkout has an unexpected untracked or modified path")
        if not line.startswith("?? "):
            die("new checkout has a tracked change")


def yaml_leaves(parser: Path, path: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
import yaml
data = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
leaves = {}
def walk(obj, prefix):
    if isinstance(obj, dict):
        for key, value in obj.items():
            walk(value, f"{prefix}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            walk(value, f"{prefix}[{index}]")
    else:
        leaves[prefix] = obj
walk(data, "")
json.dump(leaves, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(path)], text=True)
    body = json.loads(raw)
    if not isinstance(body, dict):
        die("config.yaml leaves are not an object")
    return body


def assert_checkout_swap(old_leaves: dict, new_leaves: dict, stable: Path, new: Path) -> None:
    allowed = re.compile(r"^\.mcp_servers\.[^.]+\.(command|cwd|args\[\d+\])$")
    keys = set(old_leaves) | set(new_leaves)
    for key in sorted(keys):
        left = old_leaves.get(key)
        right = new_leaves.get(key)
        if left == right:
            continue
        if not allowed.fullmatch(key):
            die("config.yaml would change a field other than mcp command, args, or cwd")
        if not isinstance(left, str) or not isinstance(right, str):
            die("mcp path field is not a string")
        if right != left.replace(str(stable), str(new)):
            die("mcp path change is not the checkout prefix")


def node_bin() -> Path:
    found = shutil.which("node")
    if not found:
        die("node is not on PATH")
    path = Path(found)
    if not path.is_file() or not os.access(path, os.X_OK):
        die("node is not executable")
    version = run([str(path), "--version"]).strip()
    match = re.fullmatch(r"v(\d+)\..*", version)
    if not match or int(match.group(1)) < 20:
        die("node is older than 20")
    return path


def npm_bin() -> Path:
    found = shutil.which("npm")
    if not found:
        die("npm is not on PATH")
    path = Path(found)
    if not os.access(path, os.X_OK):
        die("npm is not executable")
    return path

print(f"host-role=Control hostname={os.uname().nodename}")
require_python312()
lock_evidence()
if not (EVIDENCE / "journals.manifest").is_file():
    die("step 1 baseline is missing")
stable = discover_stable()
if (EVIDENCE / "stable_dir").read_text(encoding="utf-8").strip() != str(stable):
    die("stable checkout path changed after the baseline")
ctl = systemctl_scope()
shown = show_safe(ctl)
pid = gateway_pid(shown)
env = read_environ(pid)
root = Path(env.get("HERMES_FLEET_CONTROL_ROOT", ""))
if root.resolve() not in {stable.resolve(), NEW.resolve()}:
    die("gateway checkout changed to an unexpected directory")
dirs = journal_dirs(env)
files: list[Path] = []
for directory in dirs.values():
    files.extend(private_dir_files(directory))
hold_manifest(EVIDENCE / "journals.manifest", manifest_lines(files), create=False)
if sha256_file(prior_dropin(dropin_paths(shown))) != sha256_file(EVIDENCE / "fleet-delegation.conf"):
    die("fleet-delegation.conf changed")
node = node_bin()
npm = npm_bin()
print(origin_description(stable))
if NEW.exists() and not (NEW / ".git").is_dir():
    die("the new checkout path exists and is not a git repository")
if not (NEW / ".git").is_dir():
    NEW.parent.mkdir(parents=True, exist_ok=True)
    init = subprocess.run(["git", "init", "--quiet", str(NEW)], env=git_env(), capture_output=True)
    if init.returncode != 0:
        die("git init of the new checkout failed")
url = git_out(stable, "remote", "get-url", "origin")
if "\n" in url or "\r" in url or "\x00" in url:
    die("origin URL is not a single line")
config_file = NEW / ".git" / "config"
config_text = config_file.read_text(encoding="utf-8")
if '[remote "origin"]' not in config_text:
    config_file.write_text(
        config_text
        + '\n[remote "origin"]\n\turl = '
        + url
        + "\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n",
        encoding="utf-8",
    )
    os.chmod(config_file, 0o600)
fetch = subprocess.run(
    ["git", "-C", str(NEW), "fetch", "--quiet", "--no-tags", "origin", SHA],
    env=git_env(),
    capture_output=True,
)
if fetch.returncode != 0:
    die("git fetch of the exact commit failed; fetch output was not printed")
checkout = subprocess.run(
    ["git", "-C", str(NEW), "checkout", "--quiet", "--detach", SHA],
    env=git_env(),
    capture_output=True,
)
if checkout.returncode != 0:
    die("git checkout of the exact commit failed; the worktree was not forced")
require_checkout_identity(NEW, SHA, TREE)
porcelain_allowed(NEW)
require_checkout_identity(stable, STABLE_SHA, STABLE_TREE)
venv_python = NEW / "runtime" / "venv" / "bin" / "python"
ready = False
if venv_python.is_file() and os.access(venv_python, os.X_OK):
    probe = subprocess.run(
        [str(venv_python), "-c", "import cryptography, yaml, sys; assert sys.prefix and cryptography.__version__=='50.0.2' and yaml.__version__=='6.0.2'"],
        cwd=str(NEW),
        capture_output=True,
    )
    ready = probe.returncode == 0 and Path(os.path.realpath(venv_python)).is_file()
if not ready:
    install = subprocess.run(
        [str(PY), str(NEW / "install-control-runtime"), "--python", str(PY)],
        cwd=str(NEW),
        capture_output=True,
        text=True,
    )
    if install.returncode != 0:
        die("install-control-runtime failed")
    printed = install.stdout.strip()
    if printed != str(venv_python):
        die("install-control-runtime printed an unexpected interpreter path")
probe = subprocess.run(
    [
        str(venv_python),
        "-c",
        "import sys; from pathlib import Path; import cryptography, yaml; expected=Path(sys.argv[1]).resolve(); assert Path(sys.prefix).resolve()==expected; assert (expected/'pyvenv.cfg').is_file(); assert cryptography.__version__=='50.0.2'; assert yaml.__version__=='6.0.2'",
        str(NEW / "runtime" / "venv"),
    ],
    cwd="/",
    capture_output=True,
)
if probe.returncode != 0:
    die("new virtualenv does not import the locked packages")
print(f"venv-python={venv_python}")
fleet_mcp = NEW / "fleet-mcp"
installed = subprocess.run(
    [str(npm), "ls", "--omit=dev", "--depth=0"],
    cwd=str(fleet_mcp),
    capture_output=True,
)
if installed.returncode != 0:
    npm_ci = subprocess.run(
        [str(npm), "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=str(fleet_mcp),
        capture_output=True,
        text=True,
    )
    if npm_ci.returncode != 0:
        die("npm ci failed; its output was not printed")
    installed = subprocess.run([str(npm), "ls", "--omit=dev", "--depth=0"], cwd=str(fleet_mcp), capture_output=True)
    if installed.returncode != 0:
        die("npm ls still fails after npm ci")
check = subprocess.run([str(node), "--check", str(fleet_mcp / "index.js")], capture_output=True)
if check.returncode != 0:
    die("node --check failed for fleet-mcp/index.js")
porcelain_allowed(NEW)
require_checkout_identity(stable, STABLE_SHA, STABLE_TREE)
print("STEP 4 OK")
PY
BASH
```

### 5. Control — point a new drop-in at the new checkout

On the Control host, add `fleet-retirement.conf` in the same drop-in
directory as `fleet-delegation.conf`. It sets `HERMES_FLEET_CONTROL_ROOT`
to the new checkout and rewrites any other non-secret `Environment=` value
in `fleet-delegation.conf` that contains the stable path. When the baseline
`config.yaml` contains that path inside MCP `command`, `args`, or `cwd`,
replace only that prefix. Leave `fleet-delegation.conf` unchanged. Do not
reload or restart in this step.

```bash
bash -euo pipefail <<'BASH'
echo "host-role=Control hostname=$(hostname -s)"
test -x /usr/bin/python3.12
exec /usr/bin/python3.12 - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

UNIT = "hermes-gateway-control.service"
SHA = "c08cb1ebd073ee7946f49005dd45071366eeb688"
STABLE_SHA = "dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a"
TREE = "2b8888b984634b714d62646ddd5b6f48d073d160"
STABLE_TREE = "3d5f940738c5d1c0061645d06e74d3f88b034ae5"
PROVISIONER_SHA = "b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb"
NEW = Path("/opt/hermes-fleet-control") / SHA


def evidence_root() -> Path:
    """Root-owned witness, or the invoking user's state dir for a user unit."""
    if os.geteuid() == 0:
        return Path("/var/lib/hermes-control-deploy") / SHA
    return Path.home() / ".local/state/hermes-control-deploy" / SHA


EVIDENCE = evidence_root()
AGENT_VENV = Path("/home/hermes/.hermes/hermes-agent/venv")
PY = Path("/usr/bin/python3.12")
DROPIN_NAME = "fleet-retirement.conf"
PRIOR_DROPIN = "fleet-delegation.conf"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PRIVATE|NSEC|CREDENTIAL|KEY)$|^(AUTHORIZATION)$",
    re.IGNORECASE,
)
PATH_KEYS = {
    "HERMES_FLEET_CONTROL_ROOT",
    "HERMES_HOME",
    "FLEET_CONTROL_ENV_FILE",
    "FLEET_CONTROL_PROFILES_ROOT",
    "FLEET_DELEGATION_JOURNAL_DIR",
    "FLEET_ONBOARD_JOURNAL_DIR",
    "FLEET_RETIRE_JOURNAL_DIR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
}
PRESENCE_KEYS = (
    "BUZZ_PRIVATE_KEY",
    "FLEET_PROVISIONER_CALLER_TOKEN",
    "BUZZ_FLEET_MEMBERSHIP_TOKEN",
    "LITELLM_MASTER_KEY",
    "PVE_TOKEN_SECRET",
    "FLEET_CONTROL_PYTHON",
)


def die(message: str) -> None:
    sys.stderr.write("STOP: " + message + "\n")
    raise SystemExit(1)


def run(argv: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        err = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        safe = ""
        if err and len(err[-1]) < 240 and "://" not in err[-1] and "@" not in err[-1]:
            safe = ": " + err[-1]
        die(f"command failed ({completed.returncode}): {argv[0]}{safe}")
    return completed.stdout.decode("utf-8", "replace")


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git_out(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args], env=git_env()).strip()


def require_python312() -> None:
    if not PY.is_file() or not os.access(PY, os.X_OK):
        die("/usr/bin/python3.12 is missing or not executable")
    real = Path(os.path.realpath(PY))
    agent = AGENT_VENV.resolve() if AGENT_VENV.exists() else AGENT_VENV
    if real == agent or str(real).startswith(str(agent) + os.sep):
        die("/usr/bin/python3.12 resolves inside the Hermes agent virtualenv")


def systemctl_scope() -> list[str]:
    def loaded(user: bool) -> bool:
        argv = ["systemctl"]
        if user:
            argv.append("--user")
        argv.extend(["show", "-p", "LoadState", "--value", UNIT])
        completed = subprocess.run(argv, capture_output=True, text=True)
        return completed.returncode == 0 and completed.stdout.strip() == "loaded"

    system_loaded = loaded(False)
    user_loaded = loaded(True)
    if system_loaded and user_loaded:
        die("both system and user hermes-gateway-control.service are loaded")
    if system_loaded:
        if os.geteuid() != 0:
            die("the system unit requires this command to run as root")
        return ["systemctl"]
    if user_loaded:
        return ["systemctl", "--user"]
    die("hermes-gateway-control.service is not loaded")


def show(ctl: list[str], *props: str) -> dict[str, str]:
    text = run([*ctl, "show", *[f"-p{prop}" for prop in props], "--value", UNIT])
    lines = text.splitlines()
    if len(lines) != len(props):
        # systemctl --value prints one line per property; empty values still occupy a line
        # only when at least one property is empty at the end. Re-read without relying on blanks.
        raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
        found: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            found[key] = value
        missing = [prop for prop in props if prop not in found]
        if missing:
            die("systemctl show omitted properties")
        return {prop: found[prop] for prop in props}
    return dict(zip(props, lines))


def show_safe(ctl: list[str]) -> dict[str, str]:
    props = (
        "LoadState",
        "ActiveState",
        "SubState",
        "MainPID",
        "NRestarts",
        "FragmentPath",
        "DropInPaths",
        "EnvironmentFiles",
        "User",
        "Group",
        "WorkingDirectory",
        "ExecMainStartTimestamp",
    )
    raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
    found: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in props:
            found[key] = value
    missing = [prop for prop in props if prop not in found]
    if missing:
        die("systemctl show omitted " + ",".join(missing))
    return {prop: found[prop] for prop in props}


def read_environ(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    env: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            env[key.decode("utf-8")] = value.decode("utf-8")
        except UnicodeDecodeError:
            die("gateway environ has a non-utf8 entry")
    return env


def descendants(pid: int) -> list[int]:
    found: list[int] = []

    def walk(parent: int) -> None:
        child_file = Path(f"/proc/{parent}/task/{parent}/children")
        try:
            text = child_file.read_text()
        except OSError:
            return
        for token in text.split():
            child = int(token)
            found.append(child)
            walk(child)

    walk(pid)
    return found


def checkout_dirs_of(pid: int) -> list[Path]:
    paths: list[Path] = []
    for proc in [pid, *descendants(pid)]:
        link = Path(f"/proc/{proc}/cwd")
        try:
            cwd = Path(os.path.realpath(link))
        except OSError:
            continue
        text = str(cwd)
        marker = "/opt/hermes-fleet-control/"
        if marker in text:
            root = Path(text.split(marker, 1)[0] + marker + text.split(marker, 1)[1].split("/", 1)[0])
            paths.append(root)
    return paths


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.lstat().st_mode))


def regular_files(directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        die(f"not a real directory: {directory}")
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        current = Path(dirpath)
        if current.is_symlink():
            die(f"symlink inside witness tree: {current}")
        dirnames[:] = sorted(name for name in dirnames if name not in {".git"})
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                die(f"symlink inside witness tree: {path}")
            if path.is_file():
                found.append(path)
    return found


def manifest_lines(paths: list[Path]) -> str:
    lines = []
    for path in sorted(paths, key=lambda item: str(item)):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            die(f"not a regular file: {path}")
        lines.append(f"{sha256_file(path)} {file_mode(path)} {path}")
    return "\n".join(lines) + ("\n" if lines else "")


def hold_manifest(path: Path, text: str, *, create: bool) -> None:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current != text:
            die(f"baseline differs and will not be replaced: {path.name}")
        return
    if not create:
        die(f"baseline is missing: {path.name}")
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def copy_once(source: Path, dest: Path) -> None:
    if source.is_symlink() or not source.is_file():
        die(f"refusing to back up a non-regular file: {source}")
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if dest.exists():
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            die(f"backup already exists and differs: {dest.name}")
        return
    dest.write_bytes(data)
    os.chmod(dest, 0o600)


def discover_stable() -> Path:
    root = Path("/opt/hermes-fleet-control")
    if not root.is_dir():
        die("/opt/hermes-fleet-control is absent")
    matches = sorted(path for path in root.glob("dcb3f950*") if path.is_dir() and not path.is_symlink())
    if len(matches) != 1:
        die("expected exactly one /opt/hermes-fleet-control/dcb3f950* checkout")
    stable = matches[0]
    if stable.resolve() == NEW.resolve():
        die("stable and new checkout paths are the same")
    if git_out(stable, "rev-parse", "HEAD") != STABLE_SHA:
        die("stable checkout HEAD is not dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a")
    if git_out(stable, "rev-parse", "HEAD^{tree}") != STABLE_TREE:
        die("stable checkout tree is not the dcb3f950 tree")
    return stable


def origin_description(repo: Path) -> str:
    url = git_out(repo, "remote", "get-url", "origin")
    if "://" not in url and ":" in url:
        return "origin=scp-like"
    if "@" in url.split("://", 1)[-1].split("/", 1)[0]:
        return "origin=url-with-userinfo"
    scheme, rest = url.split("://", 1)
    host = rest.split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", host):
        return "origin=present"
    return f"origin={scheme}://{host}"


def journal_dirs(env: dict[str, str]) -> dict[str, Path]:
    profile = env.get("FLEET_CONTROL_HERMES_PROFILE", "")
    if not NAME_RE.fullmatch(profile):
        die("FLEET_CONTROL_HERMES_PROFILE is absent or not a profile name")
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    if not root.startswith("/"):
        die("profiles root is not absolute")
    overrides = {
        "delegations": env.get("FLEET_DELEGATION_JOURNAL_DIR") or str(Path(root) / profile / "fleet-delegations"),
        "onboarding": env.get("FLEET_ONBOARD_JOURNAL_DIR") or str(Path(root) / profile / "fleet-onboarding"),
        "retirements": env.get("FLEET_RETIRE_JOURNAL_DIR") or str(Path(root) / profile / "fleet-retirements"),
    }
    paths = {name: Path(value) for name, value in overrides.items()}
    for path in paths.values():
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            die(f"journal directory is absent: {path}")
        mode = stat.S_IMODE(path.lstat().st_mode)
        if mode & 0o077:
            die(f"journal directory is not private: {path}")
    return paths


def private_dir_files(path: Path) -> list[Path]:
    files = regular_files(path)
    if not files:
        die(f"journal directory is empty: {path}")
    for file in files:
        if file.name.endswith(".lock"):
            fd = os.open(file, os.O_RDONLY)
            try:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                die(f"journal lock is held: {file.name}")
            finally:
                os.close(fd)
    return files


def parse_env_assignments(path: Path) -> list[tuple[str, str]]:
    if path.is_symlink() or not path.is_file():
        die(f"env file is not a regular file: {path}")
    rows: list[tuple[str, str]] = []
    for raw in path.read_bytes().splitlines():
        if raw.endswith(b"\\"):
            die("env file has a continuation line; refusing to parse it")
        line = raw.decode("utf-8", "replace").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            die("env file has a line without an assignment")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            die("env file has an unusual key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        rows.append((key, value))
    return rows


def classify_value(key: str, value: str) -> str:
    if value == "":
        return f"{key}=empty"
    if key in PATH_KEYS and value.startswith("/") and not re.search(r"\s", value):
        return f"{key}={value}"
    if key == "FLEET_PROVISIONER_URL":
        if value.startswith("https://") and "@" not in value and " " not in value:
            return "FLEET_PROVISIONER_URL=https-origin"
        return "FLEET_PROVISIONER_URL=present-not-printed"
    if SECRET_KEY_RE.search(key) or key in PRESENCE_KEYS:
        return f"{key}=present"
    return f"{key}=present"


def env_report(rows: list[tuple[str, str]]) -> list[str]:
    return [classify_value(key, value) for key, value in rows]


def require_assignment(rows: list[tuple[str, str]], key: str) -> str:
    values = [value for name, value in rows if name == key]
    if len(values) != 1 or values[0] == "":
        die(f"{key} is not present exactly once")
    return values[0]


def dropin_paths(shown: dict[str, str]) -> list[Path]:
    text = shown.get("DropInPaths", "").strip()
    if not text:
        die("the gateway unit has no drop-ins")
    return [Path(part) for part in text.split()]


def environment_files(shown: dict[str, str]) -> list[Path]:
    text = shown.get("EnvironmentFiles", "").strip()
    if text in {"", "[not set]", "n/a"}:
        return []
    paths = []
    for match in re.findall(r"-?(/[^()\s]+)", text):
        paths.append(Path(match))
    return paths


def prior_dropin(paths: list[Path]) -> Path:
    matches = [path for path in paths if path.name == PRIOR_DROPIN]
    if len(matches) != 1:
        die("fleet-delegation.conf is not exactly one loaded drop-in")
    path = matches[0]
    if path.is_symlink() or not path.is_file():
        die("fleet-delegation.conf is not a regular file")
    names = sorted(path.name for path in paths)
    if any(name > DROPIN_NAME for name in names):
        die("a drop-in sorts after fleet-retirement.conf")
    return path


def desired_dropin(prior: Path, stable: Path, new: Path) -> str:
    lines = [
        "# Checkout override for hermes-fleet-control " + SHA + ".",
        "# Loaded after fleet-delegation.conf. That file is not modified.",
        "[Service]",
        f"Environment=HERMES_FLEET_CONTROL_ROOT={new}",
    ]
    for raw in prior.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("Environment="):
            continue
        body = line[len("Environment=") :]
        if len(body) >= 2 and body[0] == body[-1] == '"':
            body = body[1:-1]
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        if key == "HERMES_FLEET_CONTROL_ROOT":
            if not value.startswith(str(stable)):
                die("fleet-delegation.conf roots the checkout somewhere else")
            continue
        if str(stable) in value:
            if SECRET_KEY_RE.search(key):
                die("a secret-like drop-in key contains the checkout path")
            lines.append(f"Environment={key}={value.replace(str(stable), str(new), 1)}")
    text = "\n".join(lines) + "\n"
    if "\n" in text.strip().split("HERMES_FLEET_CONTROL_ROOT=", 1)[-1].split("\n", 1)[0]:
        die("drop-in path is not a single line")
    return text


def yaml_loader():
    stable = discover_stable()
    candidate = stable / "runtime" / "venv" / "bin" / "python"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    die("stable checkout has no runtime/venv/bin/python to parse config.yaml")


def mcp_view(config_path: Path, parser: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink():
    raise SystemExit("config.yaml is a symlink")
text = path.read_text(encoding="utf-8")
import yaml
data = yaml.safe_load(text)
if not isinstance(data, dict):
    raise SystemExit("config.yaml is not a mapping")
servers = data.get("mcp_servers")
if not isinstance(servers, dict):
    raise SystemExit("mcp_servers is absent")
view = {}
for name, cfg in servers.items():
    if not isinstance(cfg, dict):
        raise SystemExit("mcp server entry is not a mapping")
    args = cfg.get("args")
    if args is None:
        args = []
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise SystemExit("mcp args are not strings")
    command = cfg.get("command")
    cwd = cfg.get("cwd")
    if command is not None and not isinstance(command, str):
        raise SystemExit("mcp command is not a string")
    if cwd is not None and not isinstance(cwd, str):
        raise SystemExit("mcp cwd is not a string")
    env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
    view[name] = {
        "command": command,
        "args": args,
        "cwd": cwd,
        "env_keys": sorted(str(key) for key in env),
    }
json.dump({"text_sha": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(), "servers": view}, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(config_path)], text=True)
    return json.loads(raw)


def config_path_from(env: dict[str, str]) -> Path:
    profile = env["FLEET_CONTROL_HERMES_PROFILE"]
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    path = Path(root) / profile / "config.yaml"
    if path.is_symlink() or not path.is_file():
        die("profile config.yaml is absent")
    return path


def rewrite_config(text: str, stable: Path, new: Path) -> tuple[str, str]:
    """Return (new_text, reason). reason is unchanged, interpolated, or rewritten."""
    stable_text = str(stable)
    new_text = str(new)
    if stable_text not in text and new_text not in text and "${HERMES_FLEET_CONTROL_ROOT}" in text:
        return text, "interpolated"
    if stable_text not in text and new_text in text:
        return text, "unchanged"
    if stable_text not in text:
        die("config.yaml does not reference the stable checkout or HERMES_FLEET_CONTROL_ROOT")
    return text.replace(stable_text, new_text), "rewritten"


def mcp_path_changed(before: dict, after: dict) -> bool:
    if before.keys() != after.keys():
        die("mcp server names would change")
    for name in before:
        for field in ("command", "args", "cwd", "env_keys"):
            if before[name][field] != after[name][field]:
                if field == "env_keys":
                    die("mcp env keys would change")
                old = before[name][field]
                new = after[name][field]
                if isinstance(old, list):
                    if not isinstance(new, list) or len(old) != len(new):
                        die("mcp args shape would change")
                    for left, right in zip(old, new):
                        if right != left.replace(str(discover_stable()), str(NEW)):
                            die("an mcp arg change is not the checkout prefix")
                elif isinstance(old, str):
                    if new != old.replace(str(discover_stable()), str(NEW)):
                        die("an mcp path change is not the checkout prefix")
                elif old is None and new is None:
                    continue
                else:
                    die("mcp field type would change")
    return True


def status_env(env_file: Path, gateway_env: dict[str, str]) -> dict[str, str]:
    child = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": gateway_env.get("HOME", "/root"),
        "LANG": "C",
        "FLEET_CONTROL_ENV_FILE": str(env_file),
    }
    for key in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE"):
        value = gateway_env.get(key, "")
        if value.startswith("/") and Path(value).exists() and not Path(value).is_symlink():
            child[key] = value
    return child


def run_status(checkout: Path, env_file: Path, gateway_env: dict[str, str], args: list[str]) -> dict:
    binary = checkout / "runtime" / "venv" / "bin" / "python"
    script = checkout / "fleet-status"
    if not binary.is_file() or not script.is_file():
        die("fleet-status runtime is absent in " + checkout.name)
    completed = subprocess.run(
        [str(binary), str(script), *args],
        cwd="/",
        env=status_env(env_file, gateway_env),
        capture_output=True,
    )
    if completed.returncode != 0:
        die("authenticated status read failed")
    if len(completed.stdout) > 1_000_000:
        die("status response is too large")
    try:
        body = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        die("status response is not json")
    if not isinstance(body, dict):
        die("status response is not an object")
    return body


def worker_names(body: dict) -> list[str]:
    if body.get("api_version") != "v1" or body.get("kind") != "WorkerList":
        die("status list is not a WorkerList")
    workers = body.get("workers")
    names: list[str] = []
    if isinstance(workers, list):
        for item in workers:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
            else:
                die("worker list entry has no name")
    elif isinstance(workers, dict):
        names.extend(str(key) for key in workers)
    else:
        die("workers field is not a list")
    for name in names:
        if not NAME_RE.fullmatch(name):
            die("worker list contains a name that is not safe to record")
    return sorted(set(names))


def project_worker(body: dict) -> dict:
    if body.get("api_version") != "v1" or body.get("kind") != "Worker":
        die("status read is not one worker")
    observed = body.get("observed") if isinstance(body.get("observed"), dict) else {}
    onboarding = body.get("onboarding") if isinstance(body.get("onboarding"), dict) else None
    tombstone = body.get("tombstone")
    tombstone_view = None
    if isinstance(tombstone, dict):
        tombstone_view = {
            "name": tombstone.get("name"),
            "vmid": tombstone.get("vmid"),
        }
    return {
        "name": body.get("name"),
        "declared": body.get("declared"),
        "retained": body.get("retained"),
        "tombstone": tombstone_view,
        "observed_state": observed.get("state"),
        "public_key_hex": observed.get("buzz_public_key_hex"),
        "vmid": observed.get("vmid"),
        "onboarding_id": None if onboarding is None else onboarding.get("id"),
        "onboarding_status": None if onboarding is None else onboarding.get("status"),
    }


def read_text(path: Path) -> str:
    if not path.is_file():
        die(f"missing evidence {path.name}")
    return path.read_text(encoding="utf-8")


def prepare_evidence() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.chmod(EVIDENCE, 0o700)
    if EVIDENCE.is_symlink():
        die("evidence directory is a symlink")


def lock_evidence() -> None:
    prepare_evidence()
    lock_path = EVIDENCE / "lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        die("another paste holds the evidence lock")
    # Hold the lock for the process lifetime.
    os.dup2(fd, 9)


def gateway_pid(shown: dict[str, str]) -> int:
    if shown["ActiveState"] != "active":
        die("hermes-gateway-control.service is not active")
    try:
        pid = int(shown["MainPID"])
    except ValueError:
        die("MainPID is not numeric")
    if pid <= 1 or not Path(f"/proc/{pid}").exists():
        die("MainPID is not a live process")
    return pid


def require_checkout_identity(path: Path, commit: str, tree: str) -> None:
    if git_out(path, "rev-parse", "HEAD") != commit:
        die(path.name + " HEAD is not " + commit)
    if git_out(path, "rev-parse", "HEAD^{tree}") != tree:
        die(path.name + " tree does not match")


def porcelain_allowed(repo: Path) -> None:
    text = run(["git", "-C", str(repo), "status", "--porcelain=v1", "-uall"], env=git_env())
    for line in text.splitlines():
        if len(line) < 4:
            die("unexpected git status line")
        path = line[3:]
        if " -> " in path:
            die("checkout has a rename")
        if not (
            path == "runtime"
            or path.startswith("runtime/")
            or path == "fleet-mcp/node_modules"
            or path.startswith("fleet-mcp/node_modules/")
        ):
            die("new checkout has an unexpected untracked or modified path")
        if not line.startswith("?? "):
            die("new checkout has a tracked change")


def yaml_leaves(parser: Path, path: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
import yaml
data = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
leaves = {}
def walk(obj, prefix):
    if isinstance(obj, dict):
        for key, value in obj.items():
            walk(value, f"{prefix}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            walk(value, f"{prefix}[{index}]")
    else:
        leaves[prefix] = obj
walk(data, "")
json.dump(leaves, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(path)], text=True)
    body = json.loads(raw)
    if not isinstance(body, dict):
        die("config.yaml leaves are not an object")
    return body


def assert_checkout_swap(old_leaves: dict, new_leaves: dict, stable: Path, new: Path) -> None:
    allowed = re.compile(r"^\.mcp_servers\.[^.]+\.(command|cwd|args\[\d+\])$")
    keys = set(old_leaves) | set(new_leaves)
    for key in sorted(keys):
        left = old_leaves.get(key)
        right = new_leaves.get(key)
        if left == right:
            continue
        if not allowed.fullmatch(key):
            die("config.yaml would change a field other than mcp command, args, or cwd")
        if not isinstance(left, str) or not isinstance(right, str):
            die("mcp path field is not a string")
        if right != left.replace(str(stable), str(new)):
            die("mcp path change is not the checkout prefix")


def node_bin() -> Path:
    found = shutil.which("node")
    if not found:
        die("node is not on PATH")
    path = Path(found)
    if not path.is_file() or not os.access(path, os.X_OK):
        die("node is not executable")
    version = run([str(path), "--version"]).strip()
    match = re.fullmatch(r"v(\d+)\..*", version)
    if not match or int(match.group(1)) < 20:
        die("node is older than 20")
    return path


def npm_bin() -> Path:
    found = shutil.which("npm")
    if not found:
        die("npm is not on PATH")
    path = Path(found)
    if not os.access(path, os.X_OK):
        die("npm is not executable")
    return path

print(f"host-role=Control hostname={os.uname().nodename}")
require_python312()
lock_evidence()
if not (EVIDENCE / "journals.manifest").is_file():
    die("step 1 baseline is missing")
stable = discover_stable()
require_checkout_identity(NEW, SHA, TREE)
if not (NEW / "runtime" / "venv" / "bin" / "python").is_file():
    die("new checkout has no runtime/venv/bin/python")
ctl = systemctl_scope()
shown = show_safe(ctl)
pid = gateway_pid(shown)
env = read_environ(pid)
if env.get("FLEET_CONTROL_PYTHON", "").strip():
    die("FLEET_CONTROL_PYTHON is set on the running gateway")
root = Path(env.get("HERMES_FLEET_CONTROL_ROOT", ""))
if root.resolve() not in {stable.resolve(), NEW.resolve()}:
    die("gateway checkout changed to an unexpected directory")
dirs = journal_dirs(env)
journal_files: list[Path] = []
for directory in dirs.values():
    journal_files.extend(private_dir_files(directory))
hold_manifest(EVIDENCE / "journals.manifest", manifest_lines(journal_files), create=False)
paths = dropin_paths(shown)
prior = prior_dropin(paths)
if sha256_file(prior) != sha256_file(EVIDENCE / "fleet-delegation.conf"):
    die("fleet-delegation.conf changed")
desired = desired_dropin(prior, stable, NEW)
retirement = prior.with_name(DROPIN_NAME)
if retirement.exists():
    if retirement.is_symlink() or retirement.read_text(encoding="utf-8") != desired:
        die("fleet-retirement.conf exists with unexpected contents")
else:
    retirement.write_text(desired, encoding="utf-8")
    os.chmod(retirement, 0o644)
copy_once(retirement, EVIDENCE / "fleet-retirement.conf.desired")
config = config_path_from(env)
if config.is_symlink():
    die("config.yaml is a symlink")
baseline_path = EVIDENCE / "config.yaml.baseline"
baseline = baseline_path.read_text(encoding="utf-8")
proposed_text, reason = rewrite_config(baseline, stable, NEW)
proposed_path = EVIDENCE / "config.yaml.proposed"
proposed_path.write_text(proposed_text, encoding="utf-8")
os.chmod(proposed_path, 0o600)
if reason == "rewritten":
    parser = yaml_loader()
    assert_checkout_swap(yaml_leaves(parser, baseline_path), yaml_leaves(parser, proposed_path), stable, NEW)
    if str(stable) in proposed_text:
        die("proposed config.yaml still names the stable checkout")
live = config.read_text(encoding="utf-8")
marker = EVIDENCE / "config.changed"
if live == baseline and proposed_text == baseline:
    if marker.exists() and marker.read_text(encoding="utf-8").strip() != "no":
        die("config.changed marker disagrees with an unchanged config")
    if not marker.exists():
        marker.write_text("no\n", encoding="utf-8")
        os.chmod(marker, 0o600)
elif live == baseline and proposed_text != baseline:
    info = config.lstat()
    tmp = config.with_name(config.name + ".c08cb1e-tmp")
    if tmp.exists() or tmp.is_symlink():
        die("config.yaml temp path already exists")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IMODE(info.st_mode))
    try:
        os.write(fd, proposed_text.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(tmp, stat.S_IMODE(info.st_mode))
    os.chown(tmp, info.st_uid, info.st_gid)
    os.replace(tmp, config)
    copy_once(config, EVIDENCE / "config.yaml.deployed")
    marker.write_text("yes\n", encoding="utf-8")
    os.chmod(marker, 0o600)
elif live == proposed_text and proposed_text != baseline:
    copy_once(config, EVIDENCE / "config.yaml.deployed")
    if marker.exists() and marker.read_text(encoding="utf-8").strip() != "yes":
        die("config.changed marker disagrees with the deployed config")
    if not marker.exists():
        marker.write_text("yes\n", encoding="utf-8")
        os.chmod(marker, 0o600)
else:
    die("config.yaml matches neither the baseline nor the proposed deploy bytes")
print(f"drop-in={retirement}")
print(f"config={reason}")
print("STEP 5 OK")
PY
BASH
```

### 6. Control — reload systemd and restart only the Control gateway

On the Control host, `daemon-reload` and restart `hermes-gateway-control.service`
only when the live process is still the stable checkout. A paste that
already finds the new root and the loaded drop-in does not restart again.
`NRestarts` must increase by one when a restart happens.

```bash
bash -euo pipefail <<'BASH'
echo "host-role=Control hostname=$(hostname -s)"
test -x /usr/bin/python3.12
exec /usr/bin/python3.12 - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

UNIT = "hermes-gateway-control.service"
SHA = "c08cb1ebd073ee7946f49005dd45071366eeb688"
STABLE_SHA = "dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a"
TREE = "2b8888b984634b714d62646ddd5b6f48d073d160"
STABLE_TREE = "3d5f940738c5d1c0061645d06e74d3f88b034ae5"
PROVISIONER_SHA = "b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb"
NEW = Path("/opt/hermes-fleet-control") / SHA


def evidence_root() -> Path:
    """Root-owned witness, or the invoking user's state dir for a user unit."""
    if os.geteuid() == 0:
        return Path("/var/lib/hermes-control-deploy") / SHA
    return Path.home() / ".local/state/hermes-control-deploy" / SHA


EVIDENCE = evidence_root()
AGENT_VENV = Path("/home/hermes/.hermes/hermes-agent/venv")
PY = Path("/usr/bin/python3.12")
DROPIN_NAME = "fleet-retirement.conf"
PRIOR_DROPIN = "fleet-delegation.conf"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PRIVATE|NSEC|CREDENTIAL|KEY)$|^(AUTHORIZATION)$",
    re.IGNORECASE,
)
PATH_KEYS = {
    "HERMES_FLEET_CONTROL_ROOT",
    "HERMES_HOME",
    "FLEET_CONTROL_ENV_FILE",
    "FLEET_CONTROL_PROFILES_ROOT",
    "FLEET_DELEGATION_JOURNAL_DIR",
    "FLEET_ONBOARD_JOURNAL_DIR",
    "FLEET_RETIRE_JOURNAL_DIR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
}
PRESENCE_KEYS = (
    "BUZZ_PRIVATE_KEY",
    "FLEET_PROVISIONER_CALLER_TOKEN",
    "BUZZ_FLEET_MEMBERSHIP_TOKEN",
    "LITELLM_MASTER_KEY",
    "PVE_TOKEN_SECRET",
    "FLEET_CONTROL_PYTHON",
)


def die(message: str) -> None:
    sys.stderr.write("STOP: " + message + "\n")
    raise SystemExit(1)


def run(argv: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        err = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        safe = ""
        if err and len(err[-1]) < 240 and "://" not in err[-1] and "@" not in err[-1]:
            safe = ": " + err[-1]
        die(f"command failed ({completed.returncode}): {argv[0]}{safe}")
    return completed.stdout.decode("utf-8", "replace")


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git_out(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args], env=git_env()).strip()


def require_python312() -> None:
    if not PY.is_file() or not os.access(PY, os.X_OK):
        die("/usr/bin/python3.12 is missing or not executable")
    real = Path(os.path.realpath(PY))
    agent = AGENT_VENV.resolve() if AGENT_VENV.exists() else AGENT_VENV
    if real == agent or str(real).startswith(str(agent) + os.sep):
        die("/usr/bin/python3.12 resolves inside the Hermes agent virtualenv")


def systemctl_scope() -> list[str]:
    def loaded(user: bool) -> bool:
        argv = ["systemctl"]
        if user:
            argv.append("--user")
        argv.extend(["show", "-p", "LoadState", "--value", UNIT])
        completed = subprocess.run(argv, capture_output=True, text=True)
        return completed.returncode == 0 and completed.stdout.strip() == "loaded"

    system_loaded = loaded(False)
    user_loaded = loaded(True)
    if system_loaded and user_loaded:
        die("both system and user hermes-gateway-control.service are loaded")
    if system_loaded:
        if os.geteuid() != 0:
            die("the system unit requires this command to run as root")
        return ["systemctl"]
    if user_loaded:
        return ["systemctl", "--user"]
    die("hermes-gateway-control.service is not loaded")


def show(ctl: list[str], *props: str) -> dict[str, str]:
    text = run([*ctl, "show", *[f"-p{prop}" for prop in props], "--value", UNIT])
    lines = text.splitlines()
    if len(lines) != len(props):
        # systemctl --value prints one line per property; empty values still occupy a line
        # only when at least one property is empty at the end. Re-read without relying on blanks.
        raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
        found: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            found[key] = value
        missing = [prop for prop in props if prop not in found]
        if missing:
            die("systemctl show omitted properties")
        return {prop: found[prop] for prop in props}
    return dict(zip(props, lines))


def show_safe(ctl: list[str]) -> dict[str, str]:
    props = (
        "LoadState",
        "ActiveState",
        "SubState",
        "MainPID",
        "NRestarts",
        "FragmentPath",
        "DropInPaths",
        "EnvironmentFiles",
        "User",
        "Group",
        "WorkingDirectory",
        "ExecMainStartTimestamp",
    )
    raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
    found: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in props:
            found[key] = value
    missing = [prop for prop in props if prop not in found]
    if missing:
        die("systemctl show omitted " + ",".join(missing))
    return {prop: found[prop] for prop in props}


def read_environ(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    env: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            env[key.decode("utf-8")] = value.decode("utf-8")
        except UnicodeDecodeError:
            die("gateway environ has a non-utf8 entry")
    return env


def descendants(pid: int) -> list[int]:
    found: list[int] = []

    def walk(parent: int) -> None:
        child_file = Path(f"/proc/{parent}/task/{parent}/children")
        try:
            text = child_file.read_text()
        except OSError:
            return
        for token in text.split():
            child = int(token)
            found.append(child)
            walk(child)

    walk(pid)
    return found


def checkout_dirs_of(pid: int) -> list[Path]:
    paths: list[Path] = []
    for proc in [pid, *descendants(pid)]:
        link = Path(f"/proc/{proc}/cwd")
        try:
            cwd = Path(os.path.realpath(link))
        except OSError:
            continue
        text = str(cwd)
        marker = "/opt/hermes-fleet-control/"
        if marker in text:
            root = Path(text.split(marker, 1)[0] + marker + text.split(marker, 1)[1].split("/", 1)[0])
            paths.append(root)
    return paths


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.lstat().st_mode))


def regular_files(directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        die(f"not a real directory: {directory}")
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        current = Path(dirpath)
        if current.is_symlink():
            die(f"symlink inside witness tree: {current}")
        dirnames[:] = sorted(name for name in dirnames if name not in {".git"})
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                die(f"symlink inside witness tree: {path}")
            if path.is_file():
                found.append(path)
    return found


def manifest_lines(paths: list[Path]) -> str:
    lines = []
    for path in sorted(paths, key=lambda item: str(item)):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            die(f"not a regular file: {path}")
        lines.append(f"{sha256_file(path)} {file_mode(path)} {path}")
    return "\n".join(lines) + ("\n" if lines else "")


def hold_manifest(path: Path, text: str, *, create: bool) -> None:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current != text:
            die(f"baseline differs and will not be replaced: {path.name}")
        return
    if not create:
        die(f"baseline is missing: {path.name}")
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def copy_once(source: Path, dest: Path) -> None:
    if source.is_symlink() or not source.is_file():
        die(f"refusing to back up a non-regular file: {source}")
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if dest.exists():
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            die(f"backup already exists and differs: {dest.name}")
        return
    dest.write_bytes(data)
    os.chmod(dest, 0o600)


def discover_stable() -> Path:
    root = Path("/opt/hermes-fleet-control")
    if not root.is_dir():
        die("/opt/hermes-fleet-control is absent")
    matches = sorted(path for path in root.glob("dcb3f950*") if path.is_dir() and not path.is_symlink())
    if len(matches) != 1:
        die("expected exactly one /opt/hermes-fleet-control/dcb3f950* checkout")
    stable = matches[0]
    if stable.resolve() == NEW.resolve():
        die("stable and new checkout paths are the same")
    if git_out(stable, "rev-parse", "HEAD") != STABLE_SHA:
        die("stable checkout HEAD is not dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a")
    if git_out(stable, "rev-parse", "HEAD^{tree}") != STABLE_TREE:
        die("stable checkout tree is not the dcb3f950 tree")
    return stable


def origin_description(repo: Path) -> str:
    url = git_out(repo, "remote", "get-url", "origin")
    if "://" not in url and ":" in url:
        return "origin=scp-like"
    if "@" in url.split("://", 1)[-1].split("/", 1)[0]:
        return "origin=url-with-userinfo"
    scheme, rest = url.split("://", 1)
    host = rest.split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", host):
        return "origin=present"
    return f"origin={scheme}://{host}"


def journal_dirs(env: dict[str, str]) -> dict[str, Path]:
    profile = env.get("FLEET_CONTROL_HERMES_PROFILE", "")
    if not NAME_RE.fullmatch(profile):
        die("FLEET_CONTROL_HERMES_PROFILE is absent or not a profile name")
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    if not root.startswith("/"):
        die("profiles root is not absolute")
    overrides = {
        "delegations": env.get("FLEET_DELEGATION_JOURNAL_DIR") or str(Path(root) / profile / "fleet-delegations"),
        "onboarding": env.get("FLEET_ONBOARD_JOURNAL_DIR") or str(Path(root) / profile / "fleet-onboarding"),
        "retirements": env.get("FLEET_RETIRE_JOURNAL_DIR") or str(Path(root) / profile / "fleet-retirements"),
    }
    paths = {name: Path(value) for name, value in overrides.items()}
    for path in paths.values():
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            die(f"journal directory is absent: {path}")
        mode = stat.S_IMODE(path.lstat().st_mode)
        if mode & 0o077:
            die(f"journal directory is not private: {path}")
    return paths


def private_dir_files(path: Path) -> list[Path]:
    files = regular_files(path)
    if not files:
        die(f"journal directory is empty: {path}")
    for file in files:
        if file.name.endswith(".lock"):
            fd = os.open(file, os.O_RDONLY)
            try:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                die(f"journal lock is held: {file.name}")
            finally:
                os.close(fd)
    return files


def parse_env_assignments(path: Path) -> list[tuple[str, str]]:
    if path.is_symlink() or not path.is_file():
        die(f"env file is not a regular file: {path}")
    rows: list[tuple[str, str]] = []
    for raw in path.read_bytes().splitlines():
        if raw.endswith(b"\\"):
            die("env file has a continuation line; refusing to parse it")
        line = raw.decode("utf-8", "replace").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            die("env file has a line without an assignment")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            die("env file has an unusual key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        rows.append((key, value))
    return rows


def classify_value(key: str, value: str) -> str:
    if value == "":
        return f"{key}=empty"
    if key in PATH_KEYS and value.startswith("/") and not re.search(r"\s", value):
        return f"{key}={value}"
    if key == "FLEET_PROVISIONER_URL":
        if value.startswith("https://") and "@" not in value and " " not in value:
            return "FLEET_PROVISIONER_URL=https-origin"
        return "FLEET_PROVISIONER_URL=present-not-printed"
    if SECRET_KEY_RE.search(key) or key in PRESENCE_KEYS:
        return f"{key}=present"
    return f"{key}=present"


def env_report(rows: list[tuple[str, str]]) -> list[str]:
    return [classify_value(key, value) for key, value in rows]


def require_assignment(rows: list[tuple[str, str]], key: str) -> str:
    values = [value for name, value in rows if name == key]
    if len(values) != 1 or values[0] == "":
        die(f"{key} is not present exactly once")
    return values[0]


def dropin_paths(shown: dict[str, str]) -> list[Path]:
    text = shown.get("DropInPaths", "").strip()
    if not text:
        die("the gateway unit has no drop-ins")
    return [Path(part) for part in text.split()]


def environment_files(shown: dict[str, str]) -> list[Path]:
    text = shown.get("EnvironmentFiles", "").strip()
    if text in {"", "[not set]", "n/a"}:
        return []
    paths = []
    for match in re.findall(r"-?(/[^()\s]+)", text):
        paths.append(Path(match))
    return paths


def prior_dropin(paths: list[Path]) -> Path:
    matches = [path for path in paths if path.name == PRIOR_DROPIN]
    if len(matches) != 1:
        die("fleet-delegation.conf is not exactly one loaded drop-in")
    path = matches[0]
    if path.is_symlink() or not path.is_file():
        die("fleet-delegation.conf is not a regular file")
    names = sorted(path.name for path in paths)
    if any(name > DROPIN_NAME for name in names):
        die("a drop-in sorts after fleet-retirement.conf")
    return path


def desired_dropin(prior: Path, stable: Path, new: Path) -> str:
    lines = [
        "# Checkout override for hermes-fleet-control " + SHA + ".",
        "# Loaded after fleet-delegation.conf. That file is not modified.",
        "[Service]",
        f"Environment=HERMES_FLEET_CONTROL_ROOT={new}",
    ]
    for raw in prior.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("Environment="):
            continue
        body = line[len("Environment=") :]
        if len(body) >= 2 and body[0] == body[-1] == '"':
            body = body[1:-1]
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        if key == "HERMES_FLEET_CONTROL_ROOT":
            if not value.startswith(str(stable)):
                die("fleet-delegation.conf roots the checkout somewhere else")
            continue
        if str(stable) in value:
            if SECRET_KEY_RE.search(key):
                die("a secret-like drop-in key contains the checkout path")
            lines.append(f"Environment={key}={value.replace(str(stable), str(new), 1)}")
    text = "\n".join(lines) + "\n"
    if "\n" in text.strip().split("HERMES_FLEET_CONTROL_ROOT=", 1)[-1].split("\n", 1)[0]:
        die("drop-in path is not a single line")
    return text


def yaml_loader():
    stable = discover_stable()
    candidate = stable / "runtime" / "venv" / "bin" / "python"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    die("stable checkout has no runtime/venv/bin/python to parse config.yaml")


def mcp_view(config_path: Path, parser: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink():
    raise SystemExit("config.yaml is a symlink")
text = path.read_text(encoding="utf-8")
import yaml
data = yaml.safe_load(text)
if not isinstance(data, dict):
    raise SystemExit("config.yaml is not a mapping")
servers = data.get("mcp_servers")
if not isinstance(servers, dict):
    raise SystemExit("mcp_servers is absent")
view = {}
for name, cfg in servers.items():
    if not isinstance(cfg, dict):
        raise SystemExit("mcp server entry is not a mapping")
    args = cfg.get("args")
    if args is None:
        args = []
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise SystemExit("mcp args are not strings")
    command = cfg.get("command")
    cwd = cfg.get("cwd")
    if command is not None and not isinstance(command, str):
        raise SystemExit("mcp command is not a string")
    if cwd is not None and not isinstance(cwd, str):
        raise SystemExit("mcp cwd is not a string")
    env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
    view[name] = {
        "command": command,
        "args": args,
        "cwd": cwd,
        "env_keys": sorted(str(key) for key in env),
    }
json.dump({"text_sha": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(), "servers": view}, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(config_path)], text=True)
    return json.loads(raw)


def config_path_from(env: dict[str, str]) -> Path:
    profile = env["FLEET_CONTROL_HERMES_PROFILE"]
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    path = Path(root) / profile / "config.yaml"
    if path.is_symlink() or not path.is_file():
        die("profile config.yaml is absent")
    return path


def rewrite_config(text: str, stable: Path, new: Path) -> tuple[str, str]:
    """Return (new_text, reason). reason is unchanged, interpolated, or rewritten."""
    stable_text = str(stable)
    new_text = str(new)
    if stable_text not in text and new_text not in text and "${HERMES_FLEET_CONTROL_ROOT}" in text:
        return text, "interpolated"
    if stable_text not in text and new_text in text:
        return text, "unchanged"
    if stable_text not in text:
        die("config.yaml does not reference the stable checkout or HERMES_FLEET_CONTROL_ROOT")
    return text.replace(stable_text, new_text), "rewritten"


def mcp_path_changed(before: dict, after: dict) -> bool:
    if before.keys() != after.keys():
        die("mcp server names would change")
    for name in before:
        for field in ("command", "args", "cwd", "env_keys"):
            if before[name][field] != after[name][field]:
                if field == "env_keys":
                    die("mcp env keys would change")
                old = before[name][field]
                new = after[name][field]
                if isinstance(old, list):
                    if not isinstance(new, list) or len(old) != len(new):
                        die("mcp args shape would change")
                    for left, right in zip(old, new):
                        if right != left.replace(str(discover_stable()), str(NEW)):
                            die("an mcp arg change is not the checkout prefix")
                elif isinstance(old, str):
                    if new != old.replace(str(discover_stable()), str(NEW)):
                        die("an mcp path change is not the checkout prefix")
                elif old is None and new is None:
                    continue
                else:
                    die("mcp field type would change")
    return True


def status_env(env_file: Path, gateway_env: dict[str, str]) -> dict[str, str]:
    child = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": gateway_env.get("HOME", "/root"),
        "LANG": "C",
        "FLEET_CONTROL_ENV_FILE": str(env_file),
    }
    for key in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE"):
        value = gateway_env.get(key, "")
        if value.startswith("/") and Path(value).exists() and not Path(value).is_symlink():
            child[key] = value
    return child


def run_status(checkout: Path, env_file: Path, gateway_env: dict[str, str], args: list[str]) -> dict:
    binary = checkout / "runtime" / "venv" / "bin" / "python"
    script = checkout / "fleet-status"
    if not binary.is_file() or not script.is_file():
        die("fleet-status runtime is absent in " + checkout.name)
    completed = subprocess.run(
        [str(binary), str(script), *args],
        cwd="/",
        env=status_env(env_file, gateway_env),
        capture_output=True,
    )
    if completed.returncode != 0:
        die("authenticated status read failed")
    if len(completed.stdout) > 1_000_000:
        die("status response is too large")
    try:
        body = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        die("status response is not json")
    if not isinstance(body, dict):
        die("status response is not an object")
    return body


def worker_names(body: dict) -> list[str]:
    if body.get("api_version") != "v1" or body.get("kind") != "WorkerList":
        die("status list is not a WorkerList")
    workers = body.get("workers")
    names: list[str] = []
    if isinstance(workers, list):
        for item in workers:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
            else:
                die("worker list entry has no name")
    elif isinstance(workers, dict):
        names.extend(str(key) for key in workers)
    else:
        die("workers field is not a list")
    for name in names:
        if not NAME_RE.fullmatch(name):
            die("worker list contains a name that is not safe to record")
    return sorted(set(names))


def project_worker(body: dict) -> dict:
    if body.get("api_version") != "v1" or body.get("kind") != "Worker":
        die("status read is not one worker")
    observed = body.get("observed") if isinstance(body.get("observed"), dict) else {}
    onboarding = body.get("onboarding") if isinstance(body.get("onboarding"), dict) else None
    tombstone = body.get("tombstone")
    tombstone_view = None
    if isinstance(tombstone, dict):
        tombstone_view = {
            "name": tombstone.get("name"),
            "vmid": tombstone.get("vmid"),
        }
    return {
        "name": body.get("name"),
        "declared": body.get("declared"),
        "retained": body.get("retained"),
        "tombstone": tombstone_view,
        "observed_state": observed.get("state"),
        "public_key_hex": observed.get("buzz_public_key_hex"),
        "vmid": observed.get("vmid"),
        "onboarding_id": None if onboarding is None else onboarding.get("id"),
        "onboarding_status": None if onboarding is None else onboarding.get("status"),
    }


def read_text(path: Path) -> str:
    if not path.is_file():
        die(f"missing evidence {path.name}")
    return path.read_text(encoding="utf-8")


def prepare_evidence() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.chmod(EVIDENCE, 0o700)
    if EVIDENCE.is_symlink():
        die("evidence directory is a symlink")


def lock_evidence() -> None:
    prepare_evidence()
    lock_path = EVIDENCE / "lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        die("another paste holds the evidence lock")
    # Hold the lock for the process lifetime.
    os.dup2(fd, 9)


def gateway_pid(shown: dict[str, str]) -> int:
    if shown["ActiveState"] != "active":
        die("hermes-gateway-control.service is not active")
    try:
        pid = int(shown["MainPID"])
    except ValueError:
        die("MainPID is not numeric")
    if pid <= 1 or not Path(f"/proc/{pid}").exists():
        die("MainPID is not a live process")
    return pid


def require_checkout_identity(path: Path, commit: str, tree: str) -> None:
    if git_out(path, "rev-parse", "HEAD") != commit:
        die(path.name + " HEAD is not " + commit)
    if git_out(path, "rev-parse", "HEAD^{tree}") != tree:
        die(path.name + " tree does not match")


def porcelain_allowed(repo: Path) -> None:
    text = run(["git", "-C", str(repo), "status", "--porcelain=v1", "-uall"], env=git_env())
    for line in text.splitlines():
        if len(line) < 4:
            die("unexpected git status line")
        path = line[3:]
        if " -> " in path:
            die("checkout has a rename")
        if not (
            path == "runtime"
            or path.startswith("runtime/")
            or path == "fleet-mcp/node_modules"
            or path.startswith("fleet-mcp/node_modules/")
        ):
            die("new checkout has an unexpected untracked or modified path")
        if not line.startswith("?? "):
            die("new checkout has a tracked change")


def yaml_leaves(parser: Path, path: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
import yaml
data = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
leaves = {}
def walk(obj, prefix):
    if isinstance(obj, dict):
        for key, value in obj.items():
            walk(value, f"{prefix}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            walk(value, f"{prefix}[{index}]")
    else:
        leaves[prefix] = obj
walk(data, "")
json.dump(leaves, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(path)], text=True)
    body = json.loads(raw)
    if not isinstance(body, dict):
        die("config.yaml leaves are not an object")
    return body


def assert_checkout_swap(old_leaves: dict, new_leaves: dict, stable: Path, new: Path) -> None:
    allowed = re.compile(r"^\.mcp_servers\.[^.]+\.(command|cwd|args\[\d+\])$")
    keys = set(old_leaves) | set(new_leaves)
    for key in sorted(keys):
        left = old_leaves.get(key)
        right = new_leaves.get(key)
        if left == right:
            continue
        if not allowed.fullmatch(key):
            die("config.yaml would change a field other than mcp command, args, or cwd")
        if not isinstance(left, str) or not isinstance(right, str):
            die("mcp path field is not a string")
        if right != left.replace(str(stable), str(new)):
            die("mcp path change is not the checkout prefix")


def node_bin() -> Path:
    found = shutil.which("node")
    if not found:
        die("node is not on PATH")
    path = Path(found)
    if not path.is_file() or not os.access(path, os.X_OK):
        die("node is not executable")
    version = run([str(path), "--version"]).strip()
    match = re.fullmatch(r"v(\d+)\..*", version)
    if not match or int(match.group(1)) < 20:
        die("node is older than 20")
    return path


def npm_bin() -> Path:
    found = shutil.which("npm")
    if not found:
        die("npm is not on PATH")
    path = Path(found)
    if not os.access(path, os.X_OK):
        die("npm is not executable")
    return path

print(f"host-role=Control hostname={os.uname().nodename}")
require_python312()
lock_evidence()
stable = discover_stable()
require_checkout_identity(NEW, SHA, TREE)
ctl = systemctl_scope()
shown = show_safe(ctl)
pid = gateway_pid(shown)
env = read_environ(pid)
dirs = journal_dirs(env)
journal_files: list[Path] = []
for directory in dirs.values():
    journal_files.extend(private_dir_files(directory))
hold_manifest(EVIDENCE / "journals.manifest", manifest_lines(journal_files), create=False)
paths = dropin_paths(shown)
prior = prior_dropin(paths)
if sha256_file(prior) != sha256_file(EVIDENCE / "fleet-delegation.conf"):
    die("fleet-delegation.conf changed")
desired = (EVIDENCE / "fleet-retirement.conf.desired").read_text(encoding="utf-8")
retirement = prior.with_name(DROPIN_NAME)
if not retirement.is_file() or retirement.is_symlink() or retirement.read_text(encoding="utf-8") != desired:
    die("fleet-retirement.conf is not the reviewed drop-in; re-run step 5")
config = config_path_from(env)
proposed = (EVIDENCE / "config.yaml.proposed").read_text(encoding="utf-8")
if config.read_text(encoding="utf-8") != proposed:
    die("config.yaml is not the reviewed bytes; re-run step 5")
root = Path(env.get("HERMES_FLEET_CONTROL_ROOT", ""))
already = root.resolve() == NEW.resolve() and any(path.name == DROPIN_NAME for path in paths)
if already:
    child_roots = {path.resolve() for path in checkout_dirs_of(pid)}
    if any(path != NEW.resolve() for path in child_roots):
        die("gateway root is new but a child still uses another checkout")
    print("restart=skipped")
    print("STEP 6 OK")
    raise SystemExit(0)
if root.resolve() != stable.resolve():
    die("gateway is neither on the stable checkout nor fully on the new one")
before_restarts = int(shown["NRestarts"])
reload = subprocess.run([*ctl, "daemon-reload"], capture_output=True)
if reload.returncode != 0:
    die("daemon-reload failed")
restart = subprocess.run([*ctl, "restart", UNIT], capture_output=True)
if restart.returncode != 0:
    die("restart of hermes-gateway-control.service failed")
shown = show_safe(ctl)
new_pid = gateway_pid(shown)
if new_pid == pid:
    die("restart left the same MainPID")
if int(shown["NRestarts"]) != before_restarts + 1:
    die("NRestarts did not increase by exactly one")
env = read_environ(new_pid)
if Path(env.get("HERMES_FLEET_CONTROL_ROOT", "")).resolve() != NEW.resolve():
    die("restarted gateway is not rooted at the new checkout")
if env.get("FLEET_CONTROL_PYTHON", "").strip():
    die("FLEET_CONTROL_PYTHON is set after restart")
require_checkout_identity(NEW, SHA, TREE)
require_checkout_identity(stable, STABLE_SHA, STABLE_TREE)
child_roots = {path.resolve() for path in checkout_dirs_of(new_pid)}
if any(path != NEW.resolve() for path in child_roots):
    die("a restarted child is using a different checkout")
if DROPIN_NAME not in {path.name for path in dropin_paths(shown)}:
    die("fleet-retirement.conf is not loaded")
if sha256_file(prior_dropin(dropin_paths(shown))) != sha256_file(EVIDENCE / "fleet-delegation.conf"):
    die("fleet-delegation.conf changed during restart")
journal_files = []
for directory in journal_dirs(env).values():
    journal_files.extend(private_dir_files(directory))
hold_manifest(EVIDENCE / "journals.manifest", manifest_lines(journal_files), create=False)
print(f"restarted mainpid={new_pid} nrestarts={shown['NRestarts']}")
print("STEP 6 OK")
PY
BASH
```

### 7. Control — read config, status, and the tool list

On the Control host, confirm the running root, the reviewed config, and
unchanged journal checksums. `fleet-status` performs authenticated GETs
for the worker list and each baseline name. A separate MCP client sends
`tools/list` and then closes. `onboard_worker` and `retire_worker` must
be listed. No tool is called.

```bash
bash -euo pipefail <<'BASH'
echo "host-role=Control hostname=$(hostname -s)"
test -x /usr/bin/python3.12
exec /usr/bin/python3.12 - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

UNIT = "hermes-gateway-control.service"
SHA = "c08cb1ebd073ee7946f49005dd45071366eeb688"
STABLE_SHA = "dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a"
TREE = "2b8888b984634b714d62646ddd5b6f48d073d160"
STABLE_TREE = "3d5f940738c5d1c0061645d06e74d3f88b034ae5"
PROVISIONER_SHA = "b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb"
NEW = Path("/opt/hermes-fleet-control") / SHA


def evidence_root() -> Path:
    """Root-owned witness, or the invoking user's state dir for a user unit."""
    if os.geteuid() == 0:
        return Path("/var/lib/hermes-control-deploy") / SHA
    return Path.home() / ".local/state/hermes-control-deploy" / SHA


EVIDENCE = evidence_root()
AGENT_VENV = Path("/home/hermes/.hermes/hermes-agent/venv")
PY = Path("/usr/bin/python3.12")
DROPIN_NAME = "fleet-retirement.conf"
PRIOR_DROPIN = "fleet-delegation.conf"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PRIVATE|NSEC|CREDENTIAL|KEY)$|^(AUTHORIZATION)$",
    re.IGNORECASE,
)
PATH_KEYS = {
    "HERMES_FLEET_CONTROL_ROOT",
    "HERMES_HOME",
    "FLEET_CONTROL_ENV_FILE",
    "FLEET_CONTROL_PROFILES_ROOT",
    "FLEET_DELEGATION_JOURNAL_DIR",
    "FLEET_ONBOARD_JOURNAL_DIR",
    "FLEET_RETIRE_JOURNAL_DIR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
}
PRESENCE_KEYS = (
    "BUZZ_PRIVATE_KEY",
    "FLEET_PROVISIONER_CALLER_TOKEN",
    "BUZZ_FLEET_MEMBERSHIP_TOKEN",
    "LITELLM_MASTER_KEY",
    "PVE_TOKEN_SECRET",
    "FLEET_CONTROL_PYTHON",
)


def die(message: str) -> None:
    sys.stderr.write("STOP: " + message + "\n")
    raise SystemExit(1)


def run(argv: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        err = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        safe = ""
        if err and len(err[-1]) < 240 and "://" not in err[-1] and "@" not in err[-1]:
            safe = ": " + err[-1]
        die(f"command failed ({completed.returncode}): {argv[0]}{safe}")
    return completed.stdout.decode("utf-8", "replace")


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git_out(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args], env=git_env()).strip()


def require_python312() -> None:
    if not PY.is_file() or not os.access(PY, os.X_OK):
        die("/usr/bin/python3.12 is missing or not executable")
    real = Path(os.path.realpath(PY))
    agent = AGENT_VENV.resolve() if AGENT_VENV.exists() else AGENT_VENV
    if real == agent or str(real).startswith(str(agent) + os.sep):
        die("/usr/bin/python3.12 resolves inside the Hermes agent virtualenv")


def systemctl_scope() -> list[str]:
    def loaded(user: bool) -> bool:
        argv = ["systemctl"]
        if user:
            argv.append("--user")
        argv.extend(["show", "-p", "LoadState", "--value", UNIT])
        completed = subprocess.run(argv, capture_output=True, text=True)
        return completed.returncode == 0 and completed.stdout.strip() == "loaded"

    system_loaded = loaded(False)
    user_loaded = loaded(True)
    if system_loaded and user_loaded:
        die("both system and user hermes-gateway-control.service are loaded")
    if system_loaded:
        if os.geteuid() != 0:
            die("the system unit requires this command to run as root")
        return ["systemctl"]
    if user_loaded:
        return ["systemctl", "--user"]
    die("hermes-gateway-control.service is not loaded")


def show(ctl: list[str], *props: str) -> dict[str, str]:
    text = run([*ctl, "show", *[f"-p{prop}" for prop in props], "--value", UNIT])
    lines = text.splitlines()
    if len(lines) != len(props):
        # systemctl --value prints one line per property; empty values still occupy a line
        # only when at least one property is empty at the end. Re-read without relying on blanks.
        raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
        found: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            found[key] = value
        missing = [prop for prop in props if prop not in found]
        if missing:
            die("systemctl show omitted properties")
        return {prop: found[prop] for prop in props}
    return dict(zip(props, lines))


def show_safe(ctl: list[str]) -> dict[str, str]:
    props = (
        "LoadState",
        "ActiveState",
        "SubState",
        "MainPID",
        "NRestarts",
        "FragmentPath",
        "DropInPaths",
        "EnvironmentFiles",
        "User",
        "Group",
        "WorkingDirectory",
        "ExecMainStartTimestamp",
    )
    raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
    found: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in props:
            found[key] = value
    missing = [prop for prop in props if prop not in found]
    if missing:
        die("systemctl show omitted " + ",".join(missing))
    return {prop: found[prop] for prop in props}


def read_environ(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    env: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            env[key.decode("utf-8")] = value.decode("utf-8")
        except UnicodeDecodeError:
            die("gateway environ has a non-utf8 entry")
    return env


def descendants(pid: int) -> list[int]:
    found: list[int] = []

    def walk(parent: int) -> None:
        child_file = Path(f"/proc/{parent}/task/{parent}/children")
        try:
            text = child_file.read_text()
        except OSError:
            return
        for token in text.split():
            child = int(token)
            found.append(child)
            walk(child)

    walk(pid)
    return found


def checkout_dirs_of(pid: int) -> list[Path]:
    paths: list[Path] = []
    for proc in [pid, *descendants(pid)]:
        link = Path(f"/proc/{proc}/cwd")
        try:
            cwd = Path(os.path.realpath(link))
        except OSError:
            continue
        text = str(cwd)
        marker = "/opt/hermes-fleet-control/"
        if marker in text:
            root = Path(text.split(marker, 1)[0] + marker + text.split(marker, 1)[1].split("/", 1)[0])
            paths.append(root)
    return paths


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.lstat().st_mode))


def regular_files(directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        die(f"not a real directory: {directory}")
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        current = Path(dirpath)
        if current.is_symlink():
            die(f"symlink inside witness tree: {current}")
        dirnames[:] = sorted(name for name in dirnames if name not in {".git"})
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                die(f"symlink inside witness tree: {path}")
            if path.is_file():
                found.append(path)
    return found


def manifest_lines(paths: list[Path]) -> str:
    lines = []
    for path in sorted(paths, key=lambda item: str(item)):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            die(f"not a regular file: {path}")
        lines.append(f"{sha256_file(path)} {file_mode(path)} {path}")
    return "\n".join(lines) + ("\n" if lines else "")


def hold_manifest(path: Path, text: str, *, create: bool) -> None:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current != text:
            die(f"baseline differs and will not be replaced: {path.name}")
        return
    if not create:
        die(f"baseline is missing: {path.name}")
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def copy_once(source: Path, dest: Path) -> None:
    if source.is_symlink() or not source.is_file():
        die(f"refusing to back up a non-regular file: {source}")
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if dest.exists():
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            die(f"backup already exists and differs: {dest.name}")
        return
    dest.write_bytes(data)
    os.chmod(dest, 0o600)


def discover_stable() -> Path:
    root = Path("/opt/hermes-fleet-control")
    if not root.is_dir():
        die("/opt/hermes-fleet-control is absent")
    matches = sorted(path for path in root.glob("dcb3f950*") if path.is_dir() and not path.is_symlink())
    if len(matches) != 1:
        die("expected exactly one /opt/hermes-fleet-control/dcb3f950* checkout")
    stable = matches[0]
    if stable.resolve() == NEW.resolve():
        die("stable and new checkout paths are the same")
    if git_out(stable, "rev-parse", "HEAD") != STABLE_SHA:
        die("stable checkout HEAD is not dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a")
    if git_out(stable, "rev-parse", "HEAD^{tree}") != STABLE_TREE:
        die("stable checkout tree is not the dcb3f950 tree")
    return stable


def origin_description(repo: Path) -> str:
    url = git_out(repo, "remote", "get-url", "origin")
    if "://" not in url and ":" in url:
        return "origin=scp-like"
    if "@" in url.split("://", 1)[-1].split("/", 1)[0]:
        return "origin=url-with-userinfo"
    scheme, rest = url.split("://", 1)
    host = rest.split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", host):
        return "origin=present"
    return f"origin={scheme}://{host}"


def journal_dirs(env: dict[str, str]) -> dict[str, Path]:
    profile = env.get("FLEET_CONTROL_HERMES_PROFILE", "")
    if not NAME_RE.fullmatch(profile):
        die("FLEET_CONTROL_HERMES_PROFILE is absent or not a profile name")
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    if not root.startswith("/"):
        die("profiles root is not absolute")
    overrides = {
        "delegations": env.get("FLEET_DELEGATION_JOURNAL_DIR") or str(Path(root) / profile / "fleet-delegations"),
        "onboarding": env.get("FLEET_ONBOARD_JOURNAL_DIR") or str(Path(root) / profile / "fleet-onboarding"),
        "retirements": env.get("FLEET_RETIRE_JOURNAL_DIR") or str(Path(root) / profile / "fleet-retirements"),
    }
    paths = {name: Path(value) for name, value in overrides.items()}
    for path in paths.values():
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            die(f"journal directory is absent: {path}")
        mode = stat.S_IMODE(path.lstat().st_mode)
        if mode & 0o077:
            die(f"journal directory is not private: {path}")
    return paths


def private_dir_files(path: Path) -> list[Path]:
    files = regular_files(path)
    if not files:
        die(f"journal directory is empty: {path}")
    for file in files:
        if file.name.endswith(".lock"):
            fd = os.open(file, os.O_RDONLY)
            try:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                die(f"journal lock is held: {file.name}")
            finally:
                os.close(fd)
    return files


def parse_env_assignments(path: Path) -> list[tuple[str, str]]:
    if path.is_symlink() or not path.is_file():
        die(f"env file is not a regular file: {path}")
    rows: list[tuple[str, str]] = []
    for raw in path.read_bytes().splitlines():
        if raw.endswith(b"\\"):
            die("env file has a continuation line; refusing to parse it")
        line = raw.decode("utf-8", "replace").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            die("env file has a line without an assignment")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            die("env file has an unusual key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        rows.append((key, value))
    return rows


def classify_value(key: str, value: str) -> str:
    if value == "":
        return f"{key}=empty"
    if key in PATH_KEYS and value.startswith("/") and not re.search(r"\s", value):
        return f"{key}={value}"
    if key == "FLEET_PROVISIONER_URL":
        if value.startswith("https://") and "@" not in value and " " not in value:
            return "FLEET_PROVISIONER_URL=https-origin"
        return "FLEET_PROVISIONER_URL=present-not-printed"
    if SECRET_KEY_RE.search(key) or key in PRESENCE_KEYS:
        return f"{key}=present"
    return f"{key}=present"


def env_report(rows: list[tuple[str, str]]) -> list[str]:
    return [classify_value(key, value) for key, value in rows]


def require_assignment(rows: list[tuple[str, str]], key: str) -> str:
    values = [value for name, value in rows if name == key]
    if len(values) != 1 or values[0] == "":
        die(f"{key} is not present exactly once")
    return values[0]


def dropin_paths(shown: dict[str, str]) -> list[Path]:
    text = shown.get("DropInPaths", "").strip()
    if not text:
        die("the gateway unit has no drop-ins")
    return [Path(part) for part in text.split()]


def environment_files(shown: dict[str, str]) -> list[Path]:
    text = shown.get("EnvironmentFiles", "").strip()
    if text in {"", "[not set]", "n/a"}:
        return []
    paths = []
    for match in re.findall(r"-?(/[^()\s]+)", text):
        paths.append(Path(match))
    return paths


def prior_dropin(paths: list[Path]) -> Path:
    matches = [path for path in paths if path.name == PRIOR_DROPIN]
    if len(matches) != 1:
        die("fleet-delegation.conf is not exactly one loaded drop-in")
    path = matches[0]
    if path.is_symlink() or not path.is_file():
        die("fleet-delegation.conf is not a regular file")
    names = sorted(path.name for path in paths)
    if any(name > DROPIN_NAME for name in names):
        die("a drop-in sorts after fleet-retirement.conf")
    return path


def desired_dropin(prior: Path, stable: Path, new: Path) -> str:
    lines = [
        "# Checkout override for hermes-fleet-control " + SHA + ".",
        "# Loaded after fleet-delegation.conf. That file is not modified.",
        "[Service]",
        f"Environment=HERMES_FLEET_CONTROL_ROOT={new}",
    ]
    for raw in prior.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("Environment="):
            continue
        body = line[len("Environment=") :]
        if len(body) >= 2 and body[0] == body[-1] == '"':
            body = body[1:-1]
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        if key == "HERMES_FLEET_CONTROL_ROOT":
            if not value.startswith(str(stable)):
                die("fleet-delegation.conf roots the checkout somewhere else")
            continue
        if str(stable) in value:
            if SECRET_KEY_RE.search(key):
                die("a secret-like drop-in key contains the checkout path")
            lines.append(f"Environment={key}={value.replace(str(stable), str(new), 1)}")
    text = "\n".join(lines) + "\n"
    if "\n" in text.strip().split("HERMES_FLEET_CONTROL_ROOT=", 1)[-1].split("\n", 1)[0]:
        die("drop-in path is not a single line")
    return text


def yaml_loader():
    stable = discover_stable()
    candidate = stable / "runtime" / "venv" / "bin" / "python"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    die("stable checkout has no runtime/venv/bin/python to parse config.yaml")


def mcp_view(config_path: Path, parser: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink():
    raise SystemExit("config.yaml is a symlink")
text = path.read_text(encoding="utf-8")
import yaml
data = yaml.safe_load(text)
if not isinstance(data, dict):
    raise SystemExit("config.yaml is not a mapping")
servers = data.get("mcp_servers")
if not isinstance(servers, dict):
    raise SystemExit("mcp_servers is absent")
view = {}
for name, cfg in servers.items():
    if not isinstance(cfg, dict):
        raise SystemExit("mcp server entry is not a mapping")
    args = cfg.get("args")
    if args is None:
        args = []
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise SystemExit("mcp args are not strings")
    command = cfg.get("command")
    cwd = cfg.get("cwd")
    if command is not None and not isinstance(command, str):
        raise SystemExit("mcp command is not a string")
    if cwd is not None and not isinstance(cwd, str):
        raise SystemExit("mcp cwd is not a string")
    env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
    view[name] = {
        "command": command,
        "args": args,
        "cwd": cwd,
        "env_keys": sorted(str(key) for key in env),
    }
json.dump({"text_sha": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(), "servers": view}, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(config_path)], text=True)
    return json.loads(raw)


def config_path_from(env: dict[str, str]) -> Path:
    profile = env["FLEET_CONTROL_HERMES_PROFILE"]
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    path = Path(root) / profile / "config.yaml"
    if path.is_symlink() or not path.is_file():
        die("profile config.yaml is absent")
    return path


def rewrite_config(text: str, stable: Path, new: Path) -> tuple[str, str]:
    """Return (new_text, reason). reason is unchanged, interpolated, or rewritten."""
    stable_text = str(stable)
    new_text = str(new)
    if stable_text not in text and new_text not in text and "${HERMES_FLEET_CONTROL_ROOT}" in text:
        return text, "interpolated"
    if stable_text not in text and new_text in text:
        return text, "unchanged"
    if stable_text not in text:
        die("config.yaml does not reference the stable checkout or HERMES_FLEET_CONTROL_ROOT")
    return text.replace(stable_text, new_text), "rewritten"


def mcp_path_changed(before: dict, after: dict) -> bool:
    if before.keys() != after.keys():
        die("mcp server names would change")
    for name in before:
        for field in ("command", "args", "cwd", "env_keys"):
            if before[name][field] != after[name][field]:
                if field == "env_keys":
                    die("mcp env keys would change")
                old = before[name][field]
                new = after[name][field]
                if isinstance(old, list):
                    if not isinstance(new, list) or len(old) != len(new):
                        die("mcp args shape would change")
                    for left, right in zip(old, new):
                        if right != left.replace(str(discover_stable()), str(NEW)):
                            die("an mcp arg change is not the checkout prefix")
                elif isinstance(old, str):
                    if new != old.replace(str(discover_stable()), str(NEW)):
                        die("an mcp path change is not the checkout prefix")
                elif old is None and new is None:
                    continue
                else:
                    die("mcp field type would change")
    return True


def status_env(env_file: Path, gateway_env: dict[str, str]) -> dict[str, str]:
    child = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": gateway_env.get("HOME", "/root"),
        "LANG": "C",
        "FLEET_CONTROL_ENV_FILE": str(env_file),
    }
    for key in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE"):
        value = gateway_env.get(key, "")
        if value.startswith("/") and Path(value).exists() and not Path(value).is_symlink():
            child[key] = value
    return child


def run_status(checkout: Path, env_file: Path, gateway_env: dict[str, str], args: list[str]) -> dict:
    binary = checkout / "runtime" / "venv" / "bin" / "python"
    script = checkout / "fleet-status"
    if not binary.is_file() or not script.is_file():
        die("fleet-status runtime is absent in " + checkout.name)
    completed = subprocess.run(
        [str(binary), str(script), *args],
        cwd="/",
        env=status_env(env_file, gateway_env),
        capture_output=True,
    )
    if completed.returncode != 0:
        die("authenticated status read failed")
    if len(completed.stdout) > 1_000_000:
        die("status response is too large")
    try:
        body = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        die("status response is not json")
    if not isinstance(body, dict):
        die("status response is not an object")
    return body


def worker_names(body: dict) -> list[str]:
    if body.get("api_version") != "v1" or body.get("kind") != "WorkerList":
        die("status list is not a WorkerList")
    workers = body.get("workers")
    names: list[str] = []
    if isinstance(workers, list):
        for item in workers:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
            else:
                die("worker list entry has no name")
    elif isinstance(workers, dict):
        names.extend(str(key) for key in workers)
    else:
        die("workers field is not a list")
    for name in names:
        if not NAME_RE.fullmatch(name):
            die("worker list contains a name that is not safe to record")
    return sorted(set(names))


def project_worker(body: dict) -> dict:
    if body.get("api_version") != "v1" or body.get("kind") != "Worker":
        die("status read is not one worker")
    observed = body.get("observed") if isinstance(body.get("observed"), dict) else {}
    onboarding = body.get("onboarding") if isinstance(body.get("onboarding"), dict) else None
    tombstone = body.get("tombstone")
    tombstone_view = None
    if isinstance(tombstone, dict):
        tombstone_view = {
            "name": tombstone.get("name"),
            "vmid": tombstone.get("vmid"),
        }
    return {
        "name": body.get("name"),
        "declared": body.get("declared"),
        "retained": body.get("retained"),
        "tombstone": tombstone_view,
        "observed_state": observed.get("state"),
        "public_key_hex": observed.get("buzz_public_key_hex"),
        "vmid": observed.get("vmid"),
        "onboarding_id": None if onboarding is None else onboarding.get("id"),
        "onboarding_status": None if onboarding is None else onboarding.get("status"),
    }


def read_text(path: Path) -> str:
    if not path.is_file():
        die(f"missing evidence {path.name}")
    return path.read_text(encoding="utf-8")


def prepare_evidence() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.chmod(EVIDENCE, 0o700)
    if EVIDENCE.is_symlink():
        die("evidence directory is a symlink")


def lock_evidence() -> None:
    prepare_evidence()
    lock_path = EVIDENCE / "lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        die("another paste holds the evidence lock")
    # Hold the lock for the process lifetime.
    os.dup2(fd, 9)


def gateway_pid(shown: dict[str, str]) -> int:
    if shown["ActiveState"] != "active":
        die("hermes-gateway-control.service is not active")
    try:
        pid = int(shown["MainPID"])
    except ValueError:
        die("MainPID is not numeric")
    if pid <= 1 or not Path(f"/proc/{pid}").exists():
        die("MainPID is not a live process")
    return pid


def require_checkout_identity(path: Path, commit: str, tree: str) -> None:
    if git_out(path, "rev-parse", "HEAD") != commit:
        die(path.name + " HEAD is not " + commit)
    if git_out(path, "rev-parse", "HEAD^{tree}") != tree:
        die(path.name + " tree does not match")


def porcelain_allowed(repo: Path) -> None:
    text = run(["git", "-C", str(repo), "status", "--porcelain=v1", "-uall"], env=git_env())
    for line in text.splitlines():
        if len(line) < 4:
            die("unexpected git status line")
        path = line[3:]
        if " -> " in path:
            die("checkout has a rename")
        if not (
            path == "runtime"
            or path.startswith("runtime/")
            or path == "fleet-mcp/node_modules"
            or path.startswith("fleet-mcp/node_modules/")
        ):
            die("new checkout has an unexpected untracked or modified path")
        if not line.startswith("?? "):
            die("new checkout has a tracked change")


def yaml_leaves(parser: Path, path: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
import yaml
data = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
leaves = {}
def walk(obj, prefix):
    if isinstance(obj, dict):
        for key, value in obj.items():
            walk(value, f"{prefix}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            walk(value, f"{prefix}[{index}]")
    else:
        leaves[prefix] = obj
walk(data, "")
json.dump(leaves, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(path)], text=True)
    body = json.loads(raw)
    if not isinstance(body, dict):
        die("config.yaml leaves are not an object")
    return body


def assert_checkout_swap(old_leaves: dict, new_leaves: dict, stable: Path, new: Path) -> None:
    allowed = re.compile(r"^\.mcp_servers\.[^.]+\.(command|cwd|args\[\d+\])$")
    keys = set(old_leaves) | set(new_leaves)
    for key in sorted(keys):
        left = old_leaves.get(key)
        right = new_leaves.get(key)
        if left == right:
            continue
        if not allowed.fullmatch(key):
            die("config.yaml would change a field other than mcp command, args, or cwd")
        if not isinstance(left, str) or not isinstance(right, str):
            die("mcp path field is not a string")
        if right != left.replace(str(stable), str(new)):
            die("mcp path change is not the checkout prefix")


def node_bin() -> Path:
    found = shutil.which("node")
    if not found:
        die("node is not on PATH")
    path = Path(found)
    if not path.is_file() or not os.access(path, os.X_OK):
        die("node is not executable")
    version = run([str(path), "--version"]).strip()
    match = re.fullmatch(r"v(\d+)\..*", version)
    if not match or int(match.group(1)) < 20:
        die("node is older than 20")
    return path


def npm_bin() -> Path:
    found = shutil.which("npm")
    if not found:
        die("npm is not on PATH")
    path = Path(found)
    if not os.access(path, os.X_OK):
        die("npm is not executable")
    return path

print(f"host-role=Control hostname={os.uname().nodename}")
require_python312()
lock_evidence()
stable = discover_stable()
require_checkout_identity(NEW, SHA, TREE)
require_checkout_identity(stable, STABLE_SHA, STABLE_TREE)
ctl = systemctl_scope()
shown = show_safe(ctl)
pid = gateway_pid(shown)
env = read_environ(pid)
if Path(env.get("HERMES_FLEET_CONTROL_ROOT", "")).resolve() != NEW.resolve():
    die("running gateway is not the new checkout")
if env.get("FLEET_CONTROL_PYTHON", "").strip():
    die("FLEET_CONTROL_PYTHON is set")
if env.get("HERMES_FLEET_CONTROL_INTEGRATION") != "1":
    die("HERMES_FLEET_CONTROL_INTEGRATION is not 1")
dirs = journal_dirs(env)
journal_files: list[Path] = []
for directory in dirs.values():
    journal_files.extend(private_dir_files(directory))
hold_manifest(EVIDENCE / "journals.manifest", manifest_lines(journal_files), create=False)
if sha256_file(prior_dropin(dropin_paths(shown))) != sha256_file(EVIDENCE / "fleet-delegation.conf"):
    die("fleet-delegation.conf changed")
config = config_path_from(env)
if config.read_text(encoding="utf-8") != (EVIDENCE / "config.yaml.proposed").read_text(encoding="utf-8"):
    die("loaded config.yaml is not the reviewed bytes")
parser = yaml_loader()
view = mcp_view(config, parser)
server_name = env.get("HERMES_FLEET_MCP_SERVER", "")
server = view["servers"].get(server_name)
if server is None:
    die("MCP server name is not configured")
joined = " ".join([server.get("command") or "", server.get("cwd") or "", *(server.get("args") or [])])
if str(stable) in joined:
    die("MCP command, args, or cwd still names the stable checkout")
if str(NEW) not in joined and "${HERMES_FLEET_CONTROL_ROOT}" not in joined:
    die("MCP command, args, and cwd do not name the new checkout")
env_file = Path(env["FLEET_CONTROL_ENV_FILE"])
listed = run_status(NEW, env_file, env, [])
names = worker_names(listed)
expected_names = [line for line in (EVIDENCE / "worker-names").read_text(encoding="utf-8").splitlines() if line]
if names != expected_names:
    die("worker name set changed")
projection = {name: project_worker(run_status(NEW, env_file, env, [name])) for name in names}
expected_projection = json.loads((EVIDENCE / "worker-projection.json").read_text(encoding="utf-8"))
if projection != expected_projection:
    die("worker identity projection changed")
print("worker-names=" + ",".join(names))
node = node_bin()
client = NEW / "fleet-mcp" / "node_modules" / "@modelcontextprotocol" / "sdk" / "dist" / "esm" / "client" / "index.js"
stdio = NEW / "fleet-mcp" / "node_modules" / "@modelcontextprotocol" / "sdk" / "dist" / "esm" / "client" / "stdio.js"
if not client.is_file() or not stdio.is_file():
    die("MCP SDK client files are absent")
script = r"""
const clientMod = await import(process.env.MCP_CLIENT_URL);
const stdioMod = await import(process.env.MCP_STDIO_URL);
const transport = new stdioMod.StdioClientTransport({
  command: process.env.MCP_NODE,
  args: [process.env.MCP_INDEX],
  cwd: process.env.MCP_CWD,
  env: { PATH: process.env.MCP_PATH, HOME: process.env.HOME || "/root", LANG: "C" },
});
const client = new clientMod.Client({ name: "c08cb1e-deploy-check", version: "0" });
await client.connect(transport);
const listed = await client.listTools();
const names = listed.tools.map((tool) => tool.name).sort();
process.stdout.write(names.join("\n") + "\n");
await client.close();
"""
completed = subprocess.run(
    [str(node), "--input-type=module", "-e", script],
    cwd="/",
    env={
        "MCP_CLIENT_URL": client.as_uri(),
        "MCP_STDIO_URL": stdio.as_uri(),
        "MCP_NODE": str(node),
        "MCP_INDEX": str(NEW / "fleet-mcp" / "index.js"),
        "MCP_CWD": str(NEW / "fleet-mcp"),
        "MCP_PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/root"),
    },
    capture_output=True,
    text=True,
)
if completed.returncode != 0:
    die("MCP tools/list failed")
tools = [line for line in completed.stdout.splitlines() if line]
required = {"worker_status", "ensure_worker", "onboard_worker", "delegate_worker", "retire_worker"}
if not required.issubset(tools):
    die("onboard_worker or retire_worker is not listed")
if "send_message" in tools:
    die("send_message is listed")
print("tools=" + ",".join(tools))
print("STEP 7 OK")
PY
BASH
```

### 8. Provisioner — confirm the witness is unchanged

On the Provisioner, run the same read as step 2. The unit, PID, restart
count, `HEAD`, porcelain checksum, tombstones, and journals must match
the witness from step 2.

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

### 9. Proxmox node — confirm the VM inventory is unchanged

On the Proxmox node, run the same read as step 3. Stop here when it
matches. The deploy is complete. Leave the new checkout on disk and
leave steps 10 through 13 unused.

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

### 10. Control — roll the gateway back to the stable checkout

Run this only to undo steps 5 and 6. On the Control host, restore
baseline `config.yaml` when this procedure changed it, remove
`fleet-retirement.conf` when it is the reviewed file, `daemon-reload`,
and restart only `hermes-gateway-control.service` if the process was
not already the stable checkout with those files already restored.
Journals are compared to the step 1 baseline before and after. The new
checkout directory stays on disk and is not the running root.

```bash
bash -euo pipefail <<'BASH'
echo "host-role=Control hostname=$(hostname -s)"
test -x /usr/bin/python3.12
exec /usr/bin/python3.12 - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

UNIT = "hermes-gateway-control.service"
SHA = "c08cb1ebd073ee7946f49005dd45071366eeb688"
STABLE_SHA = "dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a"
TREE = "2b8888b984634b714d62646ddd5b6f48d073d160"
STABLE_TREE = "3d5f940738c5d1c0061645d06e74d3f88b034ae5"
PROVISIONER_SHA = "b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb"
NEW = Path("/opt/hermes-fleet-control") / SHA


def evidence_root() -> Path:
    """Root-owned witness, or the invoking user's state dir for a user unit."""
    if os.geteuid() == 0:
        return Path("/var/lib/hermes-control-deploy") / SHA
    return Path.home() / ".local/state/hermes-control-deploy" / SHA


EVIDENCE = evidence_root()
AGENT_VENV = Path("/home/hermes/.hermes/hermes-agent/venv")
PY = Path("/usr/bin/python3.12")
DROPIN_NAME = "fleet-retirement.conf"
PRIOR_DROPIN = "fleet-delegation.conf"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PRIVATE|NSEC|CREDENTIAL|KEY)$|^(AUTHORIZATION)$",
    re.IGNORECASE,
)
PATH_KEYS = {
    "HERMES_FLEET_CONTROL_ROOT",
    "HERMES_HOME",
    "FLEET_CONTROL_ENV_FILE",
    "FLEET_CONTROL_PROFILES_ROOT",
    "FLEET_DELEGATION_JOURNAL_DIR",
    "FLEET_ONBOARD_JOURNAL_DIR",
    "FLEET_RETIRE_JOURNAL_DIR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
}
PRESENCE_KEYS = (
    "BUZZ_PRIVATE_KEY",
    "FLEET_PROVISIONER_CALLER_TOKEN",
    "BUZZ_FLEET_MEMBERSHIP_TOKEN",
    "LITELLM_MASTER_KEY",
    "PVE_TOKEN_SECRET",
    "FLEET_CONTROL_PYTHON",
)


def die(message: str) -> None:
    sys.stderr.write("STOP: " + message + "\n")
    raise SystemExit(1)


def run(argv: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        err = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        safe = ""
        if err and len(err[-1]) < 240 and "://" not in err[-1] and "@" not in err[-1]:
            safe = ": " + err[-1]
        die(f"command failed ({completed.returncode}): {argv[0]}{safe}")
    return completed.stdout.decode("utf-8", "replace")


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git_out(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args], env=git_env()).strip()


def require_python312() -> None:
    if not PY.is_file() or not os.access(PY, os.X_OK):
        die("/usr/bin/python3.12 is missing or not executable")
    real = Path(os.path.realpath(PY))
    agent = AGENT_VENV.resolve() if AGENT_VENV.exists() else AGENT_VENV
    if real == agent or str(real).startswith(str(agent) + os.sep):
        die("/usr/bin/python3.12 resolves inside the Hermes agent virtualenv")


def systemctl_scope() -> list[str]:
    def loaded(user: bool) -> bool:
        argv = ["systemctl"]
        if user:
            argv.append("--user")
        argv.extend(["show", "-p", "LoadState", "--value", UNIT])
        completed = subprocess.run(argv, capture_output=True, text=True)
        return completed.returncode == 0 and completed.stdout.strip() == "loaded"

    system_loaded = loaded(False)
    user_loaded = loaded(True)
    if system_loaded and user_loaded:
        die("both system and user hermes-gateway-control.service are loaded")
    if system_loaded:
        if os.geteuid() != 0:
            die("the system unit requires this command to run as root")
        return ["systemctl"]
    if user_loaded:
        return ["systemctl", "--user"]
    die("hermes-gateway-control.service is not loaded")


def show(ctl: list[str], *props: str) -> dict[str, str]:
    text = run([*ctl, "show", *[f"-p{prop}" for prop in props], "--value", UNIT])
    lines = text.splitlines()
    if len(lines) != len(props):
        # systemctl --value prints one line per property; empty values still occupy a line
        # only when at least one property is empty at the end. Re-read without relying on blanks.
        raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
        found: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            found[key] = value
        missing = [prop for prop in props if prop not in found]
        if missing:
            die("systemctl show omitted properties")
        return {prop: found[prop] for prop in props}
    return dict(zip(props, lines))


def show_safe(ctl: list[str]) -> dict[str, str]:
    props = (
        "LoadState",
        "ActiveState",
        "SubState",
        "MainPID",
        "NRestarts",
        "FragmentPath",
        "DropInPaths",
        "EnvironmentFiles",
        "User",
        "Group",
        "WorkingDirectory",
        "ExecMainStartTimestamp",
    )
    raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
    found: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in props:
            found[key] = value
    missing = [prop for prop in props if prop not in found]
    if missing:
        die("systemctl show omitted " + ",".join(missing))
    return {prop: found[prop] for prop in props}


def read_environ(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    env: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            env[key.decode("utf-8")] = value.decode("utf-8")
        except UnicodeDecodeError:
            die("gateway environ has a non-utf8 entry")
    return env


def descendants(pid: int) -> list[int]:
    found: list[int] = []

    def walk(parent: int) -> None:
        child_file = Path(f"/proc/{parent}/task/{parent}/children")
        try:
            text = child_file.read_text()
        except OSError:
            return
        for token in text.split():
            child = int(token)
            found.append(child)
            walk(child)

    walk(pid)
    return found


def checkout_dirs_of(pid: int) -> list[Path]:
    paths: list[Path] = []
    for proc in [pid, *descendants(pid)]:
        link = Path(f"/proc/{proc}/cwd")
        try:
            cwd = Path(os.path.realpath(link))
        except OSError:
            continue
        text = str(cwd)
        marker = "/opt/hermes-fleet-control/"
        if marker in text:
            root = Path(text.split(marker, 1)[0] + marker + text.split(marker, 1)[1].split("/", 1)[0])
            paths.append(root)
    return paths


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.lstat().st_mode))


def regular_files(directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        die(f"not a real directory: {directory}")
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        current = Path(dirpath)
        if current.is_symlink():
            die(f"symlink inside witness tree: {current}")
        dirnames[:] = sorted(name for name in dirnames if name not in {".git"})
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                die(f"symlink inside witness tree: {path}")
            if path.is_file():
                found.append(path)
    return found


def manifest_lines(paths: list[Path]) -> str:
    lines = []
    for path in sorted(paths, key=lambda item: str(item)):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            die(f"not a regular file: {path}")
        lines.append(f"{sha256_file(path)} {file_mode(path)} {path}")
    return "\n".join(lines) + ("\n" if lines else "")


def hold_manifest(path: Path, text: str, *, create: bool) -> None:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current != text:
            die(f"baseline differs and will not be replaced: {path.name}")
        return
    if not create:
        die(f"baseline is missing: {path.name}")
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def copy_once(source: Path, dest: Path) -> None:
    if source.is_symlink() or not source.is_file():
        die(f"refusing to back up a non-regular file: {source}")
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if dest.exists():
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            die(f"backup already exists and differs: {dest.name}")
        return
    dest.write_bytes(data)
    os.chmod(dest, 0o600)


def discover_stable() -> Path:
    root = Path("/opt/hermes-fleet-control")
    if not root.is_dir():
        die("/opt/hermes-fleet-control is absent")
    matches = sorted(path for path in root.glob("dcb3f950*") if path.is_dir() and not path.is_symlink())
    if len(matches) != 1:
        die("expected exactly one /opt/hermes-fleet-control/dcb3f950* checkout")
    stable = matches[0]
    if stable.resolve() == NEW.resolve():
        die("stable and new checkout paths are the same")
    if git_out(stable, "rev-parse", "HEAD") != STABLE_SHA:
        die("stable checkout HEAD is not dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a")
    if git_out(stable, "rev-parse", "HEAD^{tree}") != STABLE_TREE:
        die("stable checkout tree is not the dcb3f950 tree")
    return stable


def origin_description(repo: Path) -> str:
    url = git_out(repo, "remote", "get-url", "origin")
    if "://" not in url and ":" in url:
        return "origin=scp-like"
    if "@" in url.split("://", 1)[-1].split("/", 1)[0]:
        return "origin=url-with-userinfo"
    scheme, rest = url.split("://", 1)
    host = rest.split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", host):
        return "origin=present"
    return f"origin={scheme}://{host}"


def journal_dirs(env: dict[str, str]) -> dict[str, Path]:
    profile = env.get("FLEET_CONTROL_HERMES_PROFILE", "")
    if not NAME_RE.fullmatch(profile):
        die("FLEET_CONTROL_HERMES_PROFILE is absent or not a profile name")
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    if not root.startswith("/"):
        die("profiles root is not absolute")
    overrides = {
        "delegations": env.get("FLEET_DELEGATION_JOURNAL_DIR") or str(Path(root) / profile / "fleet-delegations"),
        "onboarding": env.get("FLEET_ONBOARD_JOURNAL_DIR") or str(Path(root) / profile / "fleet-onboarding"),
        "retirements": env.get("FLEET_RETIRE_JOURNAL_DIR") or str(Path(root) / profile / "fleet-retirements"),
    }
    paths = {name: Path(value) for name, value in overrides.items()}
    for path in paths.values():
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            die(f"journal directory is absent: {path}")
        mode = stat.S_IMODE(path.lstat().st_mode)
        if mode & 0o077:
            die(f"journal directory is not private: {path}")
    return paths


def private_dir_files(path: Path) -> list[Path]:
    files = regular_files(path)
    if not files:
        die(f"journal directory is empty: {path}")
    for file in files:
        if file.name.endswith(".lock"):
            fd = os.open(file, os.O_RDONLY)
            try:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                die(f"journal lock is held: {file.name}")
            finally:
                os.close(fd)
    return files


def parse_env_assignments(path: Path) -> list[tuple[str, str]]:
    if path.is_symlink() or not path.is_file():
        die(f"env file is not a regular file: {path}")
    rows: list[tuple[str, str]] = []
    for raw in path.read_bytes().splitlines():
        if raw.endswith(b"\\"):
            die("env file has a continuation line; refusing to parse it")
        line = raw.decode("utf-8", "replace").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            die("env file has a line without an assignment")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            die("env file has an unusual key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        rows.append((key, value))
    return rows


def classify_value(key: str, value: str) -> str:
    if value == "":
        return f"{key}=empty"
    if key in PATH_KEYS and value.startswith("/") and not re.search(r"\s", value):
        return f"{key}={value}"
    if key == "FLEET_PROVISIONER_URL":
        if value.startswith("https://") and "@" not in value and " " not in value:
            return "FLEET_PROVISIONER_URL=https-origin"
        return "FLEET_PROVISIONER_URL=present-not-printed"
    if SECRET_KEY_RE.search(key) or key in PRESENCE_KEYS:
        return f"{key}=present"
    return f"{key}=present"


def env_report(rows: list[tuple[str, str]]) -> list[str]:
    return [classify_value(key, value) for key, value in rows]


def require_assignment(rows: list[tuple[str, str]], key: str) -> str:
    values = [value for name, value in rows if name == key]
    if len(values) != 1 or values[0] == "":
        die(f"{key} is not present exactly once")
    return values[0]


def dropin_paths(shown: dict[str, str]) -> list[Path]:
    text = shown.get("DropInPaths", "").strip()
    if not text:
        die("the gateway unit has no drop-ins")
    return [Path(part) for part in text.split()]


def environment_files(shown: dict[str, str]) -> list[Path]:
    text = shown.get("EnvironmentFiles", "").strip()
    if text in {"", "[not set]", "n/a"}:
        return []
    paths = []
    for match in re.findall(r"-?(/[^()\s]+)", text):
        paths.append(Path(match))
    return paths


def prior_dropin(paths: list[Path]) -> Path:
    matches = [path for path in paths if path.name == PRIOR_DROPIN]
    if len(matches) != 1:
        die("fleet-delegation.conf is not exactly one loaded drop-in")
    path = matches[0]
    if path.is_symlink() or not path.is_file():
        die("fleet-delegation.conf is not a regular file")
    names = sorted(path.name for path in paths)
    if any(name > DROPIN_NAME for name in names):
        die("a drop-in sorts after fleet-retirement.conf")
    return path


def desired_dropin(prior: Path, stable: Path, new: Path) -> str:
    lines = [
        "# Checkout override for hermes-fleet-control " + SHA + ".",
        "# Loaded after fleet-delegation.conf. That file is not modified.",
        "[Service]",
        f"Environment=HERMES_FLEET_CONTROL_ROOT={new}",
    ]
    for raw in prior.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("Environment="):
            continue
        body = line[len("Environment=") :]
        if len(body) >= 2 and body[0] == body[-1] == '"':
            body = body[1:-1]
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        if key == "HERMES_FLEET_CONTROL_ROOT":
            if not value.startswith(str(stable)):
                die("fleet-delegation.conf roots the checkout somewhere else")
            continue
        if str(stable) in value:
            if SECRET_KEY_RE.search(key):
                die("a secret-like drop-in key contains the checkout path")
            lines.append(f"Environment={key}={value.replace(str(stable), str(new), 1)}")
    text = "\n".join(lines) + "\n"
    if "\n" in text.strip().split("HERMES_FLEET_CONTROL_ROOT=", 1)[-1].split("\n", 1)[0]:
        die("drop-in path is not a single line")
    return text


def yaml_loader():
    stable = discover_stable()
    candidate = stable / "runtime" / "venv" / "bin" / "python"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    die("stable checkout has no runtime/venv/bin/python to parse config.yaml")


def mcp_view(config_path: Path, parser: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink():
    raise SystemExit("config.yaml is a symlink")
text = path.read_text(encoding="utf-8")
import yaml
data = yaml.safe_load(text)
if not isinstance(data, dict):
    raise SystemExit("config.yaml is not a mapping")
servers = data.get("mcp_servers")
if not isinstance(servers, dict):
    raise SystemExit("mcp_servers is absent")
view = {}
for name, cfg in servers.items():
    if not isinstance(cfg, dict):
        raise SystemExit("mcp server entry is not a mapping")
    args = cfg.get("args")
    if args is None:
        args = []
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise SystemExit("mcp args are not strings")
    command = cfg.get("command")
    cwd = cfg.get("cwd")
    if command is not None and not isinstance(command, str):
        raise SystemExit("mcp command is not a string")
    if cwd is not None and not isinstance(cwd, str):
        raise SystemExit("mcp cwd is not a string")
    env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
    view[name] = {
        "command": command,
        "args": args,
        "cwd": cwd,
        "env_keys": sorted(str(key) for key in env),
    }
json.dump({"text_sha": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(), "servers": view}, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(config_path)], text=True)
    return json.loads(raw)


def config_path_from(env: dict[str, str]) -> Path:
    profile = env["FLEET_CONTROL_HERMES_PROFILE"]
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    path = Path(root) / profile / "config.yaml"
    if path.is_symlink() or not path.is_file():
        die("profile config.yaml is absent")
    return path


def rewrite_config(text: str, stable: Path, new: Path) -> tuple[str, str]:
    """Return (new_text, reason). reason is unchanged, interpolated, or rewritten."""
    stable_text = str(stable)
    new_text = str(new)
    if stable_text not in text and new_text not in text and "${HERMES_FLEET_CONTROL_ROOT}" in text:
        return text, "interpolated"
    if stable_text not in text and new_text in text:
        return text, "unchanged"
    if stable_text not in text:
        die("config.yaml does not reference the stable checkout or HERMES_FLEET_CONTROL_ROOT")
    return text.replace(stable_text, new_text), "rewritten"


def mcp_path_changed(before: dict, after: dict) -> bool:
    if before.keys() != after.keys():
        die("mcp server names would change")
    for name in before:
        for field in ("command", "args", "cwd", "env_keys"):
            if before[name][field] != after[name][field]:
                if field == "env_keys":
                    die("mcp env keys would change")
                old = before[name][field]
                new = after[name][field]
                if isinstance(old, list):
                    if not isinstance(new, list) or len(old) != len(new):
                        die("mcp args shape would change")
                    for left, right in zip(old, new):
                        if right != left.replace(str(discover_stable()), str(NEW)):
                            die("an mcp arg change is not the checkout prefix")
                elif isinstance(old, str):
                    if new != old.replace(str(discover_stable()), str(NEW)):
                        die("an mcp path change is not the checkout prefix")
                elif old is None and new is None:
                    continue
                else:
                    die("mcp field type would change")
    return True


def status_env(env_file: Path, gateway_env: dict[str, str]) -> dict[str, str]:
    child = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": gateway_env.get("HOME", "/root"),
        "LANG": "C",
        "FLEET_CONTROL_ENV_FILE": str(env_file),
    }
    for key in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE"):
        value = gateway_env.get(key, "")
        if value.startswith("/") and Path(value).exists() and not Path(value).is_symlink():
            child[key] = value
    return child


def run_status(checkout: Path, env_file: Path, gateway_env: dict[str, str], args: list[str]) -> dict:
    binary = checkout / "runtime" / "venv" / "bin" / "python"
    script = checkout / "fleet-status"
    if not binary.is_file() or not script.is_file():
        die("fleet-status runtime is absent in " + checkout.name)
    completed = subprocess.run(
        [str(binary), str(script), *args],
        cwd="/",
        env=status_env(env_file, gateway_env),
        capture_output=True,
    )
    if completed.returncode != 0:
        die("authenticated status read failed")
    if len(completed.stdout) > 1_000_000:
        die("status response is too large")
    try:
        body = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        die("status response is not json")
    if not isinstance(body, dict):
        die("status response is not an object")
    return body


def worker_names(body: dict) -> list[str]:
    if body.get("api_version") != "v1" or body.get("kind") != "WorkerList":
        die("status list is not a WorkerList")
    workers = body.get("workers")
    names: list[str] = []
    if isinstance(workers, list):
        for item in workers:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
            else:
                die("worker list entry has no name")
    elif isinstance(workers, dict):
        names.extend(str(key) for key in workers)
    else:
        die("workers field is not a list")
    for name in names:
        if not NAME_RE.fullmatch(name):
            die("worker list contains a name that is not safe to record")
    return sorted(set(names))


def project_worker(body: dict) -> dict:
    if body.get("api_version") != "v1" or body.get("kind") != "Worker":
        die("status read is not one worker")
    observed = body.get("observed") if isinstance(body.get("observed"), dict) else {}
    onboarding = body.get("onboarding") if isinstance(body.get("onboarding"), dict) else None
    tombstone = body.get("tombstone")
    tombstone_view = None
    if isinstance(tombstone, dict):
        tombstone_view = {
            "name": tombstone.get("name"),
            "vmid": tombstone.get("vmid"),
        }
    return {
        "name": body.get("name"),
        "declared": body.get("declared"),
        "retained": body.get("retained"),
        "tombstone": tombstone_view,
        "observed_state": observed.get("state"),
        "public_key_hex": observed.get("buzz_public_key_hex"),
        "vmid": observed.get("vmid"),
        "onboarding_id": None if onboarding is None else onboarding.get("id"),
        "onboarding_status": None if onboarding is None else onboarding.get("status"),
    }


def read_text(path: Path) -> str:
    if not path.is_file():
        die(f"missing evidence {path.name}")
    return path.read_text(encoding="utf-8")


def prepare_evidence() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.chmod(EVIDENCE, 0o700)
    if EVIDENCE.is_symlink():
        die("evidence directory is a symlink")


def lock_evidence() -> None:
    prepare_evidence()
    lock_path = EVIDENCE / "lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        die("another paste holds the evidence lock")
    # Hold the lock for the process lifetime.
    os.dup2(fd, 9)


def gateway_pid(shown: dict[str, str]) -> int:
    if shown["ActiveState"] != "active":
        die("hermes-gateway-control.service is not active")
    try:
        pid = int(shown["MainPID"])
    except ValueError:
        die("MainPID is not numeric")
    if pid <= 1 or not Path(f"/proc/{pid}").exists():
        die("MainPID is not a live process")
    return pid


def require_checkout_identity(path: Path, commit: str, tree: str) -> None:
    if git_out(path, "rev-parse", "HEAD") != commit:
        die(path.name + " HEAD is not " + commit)
    if git_out(path, "rev-parse", "HEAD^{tree}") != tree:
        die(path.name + " tree does not match")


def porcelain_allowed(repo: Path) -> None:
    text = run(["git", "-C", str(repo), "status", "--porcelain=v1", "-uall"], env=git_env())
    for line in text.splitlines():
        if len(line) < 4:
            die("unexpected git status line")
        path = line[3:]
        if " -> " in path:
            die("checkout has a rename")
        if not (
            path == "runtime"
            or path.startswith("runtime/")
            or path == "fleet-mcp/node_modules"
            or path.startswith("fleet-mcp/node_modules/")
        ):
            die("new checkout has an unexpected untracked or modified path")
        if not line.startswith("?? "):
            die("new checkout has a tracked change")


def yaml_leaves(parser: Path, path: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
import yaml
data = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
leaves = {}
def walk(obj, prefix):
    if isinstance(obj, dict):
        for key, value in obj.items():
            walk(value, f"{prefix}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            walk(value, f"{prefix}[{index}]")
    else:
        leaves[prefix] = obj
walk(data, "")
json.dump(leaves, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(path)], text=True)
    body = json.loads(raw)
    if not isinstance(body, dict):
        die("config.yaml leaves are not an object")
    return body


def assert_checkout_swap(old_leaves: dict, new_leaves: dict, stable: Path, new: Path) -> None:
    allowed = re.compile(r"^\.mcp_servers\.[^.]+\.(command|cwd|args\[\d+\])$")
    keys = set(old_leaves) | set(new_leaves)
    for key in sorted(keys):
        left = old_leaves.get(key)
        right = new_leaves.get(key)
        if left == right:
            continue
        if not allowed.fullmatch(key):
            die("config.yaml would change a field other than mcp command, args, or cwd")
        if not isinstance(left, str) or not isinstance(right, str):
            die("mcp path field is not a string")
        if right != left.replace(str(stable), str(new)):
            die("mcp path change is not the checkout prefix")


def node_bin() -> Path:
    found = shutil.which("node")
    if not found:
        die("node is not on PATH")
    path = Path(found)
    if not path.is_file() or not os.access(path, os.X_OK):
        die("node is not executable")
    version = run([str(path), "--version"]).strip()
    match = re.fullmatch(r"v(\d+)\..*", version)
    if not match or int(match.group(1)) < 20:
        die("node is older than 20")
    return path


def npm_bin() -> Path:
    found = shutil.which("npm")
    if not found:
        die("npm is not on PATH")
    path = Path(found)
    if not os.access(path, os.X_OK):
        die("npm is not executable")
    return path

print(f"host-role=Control hostname={os.uname().nodename}")
require_python312()
lock_evidence()
stable = discover_stable()
ctl = systemctl_scope()
shown = show_safe(ctl)
pid = gateway_pid(shown)
env = read_environ(pid)
dirs = journal_dirs(env)
journal_files: list[Path] = []
for directory in dirs.values():
    journal_files.extend(private_dir_files(directory))
hold_manifest(EVIDENCE / "journals.manifest", manifest_lines(journal_files), create=False)
paths = dropin_paths(shown)
prior = prior_dropin(paths)
if sha256_file(prior) != sha256_file(EVIDENCE / "fleet-delegation.conf"):
    die("fleet-delegation.conf changed; rollback stops")
config = config_path_from(env)
if config.is_symlink():
    die("config.yaml is a symlink")
baseline = (EVIDENCE / "config.yaml.baseline").read_text(encoding="utf-8")
live = config.read_text(encoding="utf-8")
proposed_path = EVIDENCE / "config.yaml.proposed"
proposed = proposed_path.read_text(encoding="utf-8") if proposed_path.exists() else baseline
root = Path(env.get("HERMES_FLEET_CONTROL_ROOT", ""))
retirement = prior.with_name(DROPIN_NAME)
dirty = root.resolve() != stable.resolve() or retirement.exists() or live != baseline
if live == baseline:
    pass
elif live == proposed:
    info = config.lstat()
    tmp = config.with_name(config.name + ".c08cb1e-tmp")
    if tmp.exists() or tmp.is_symlink():
        die("config.yaml temp path already exists")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IMODE(info.st_mode))
    try:
        os.write(fd, baseline.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(tmp, stat.S_IMODE(info.st_mode))
    os.chown(tmp, info.st_uid, info.st_gid)
    os.replace(tmp, config)
else:
    die("config.yaml matches neither the baseline nor the proposed deploy bytes")
if retirement.exists():
    if retirement.is_symlink() or retirement.read_text(encoding="utf-8") != (EVIDENCE / "fleet-retirement.conf.desired").read_text(encoding="utf-8"):
        die("fleet-retirement.conf is not the file this procedure wrote")
    copy_once(retirement, EVIDENCE / "fleet-retirement.conf.removed")
    retirement.unlink()
if not dirty:
    print("rollback=already-stable")
    print("STEP 10 OK")
    raise SystemExit(0)
before = int(show_safe(ctl)["NRestarts"])
old_pid = gateway_pid(show_safe(ctl))
if subprocess.run([*ctl, "daemon-reload"], capture_output=True).returncode != 0:
    die("daemon-reload failed")
if subprocess.run([*ctl, "restart", UNIT], capture_output=True).returncode != 0:
    die("rollback restart failed")
shown = show_safe(ctl)
new_pid = gateway_pid(shown)
if new_pid == old_pid:
    die("rollback restart left the same MainPID")
if int(shown["NRestarts"]) != before + 1:
    die("rollback NRestarts did not increase by exactly one")
env = read_environ(new_pid)
if Path(env.get("HERMES_FLEET_CONTROL_ROOT", "")).resolve() != stable.resolve():
    die("rolled-back gateway is not rooted at the stable checkout")
require_checkout_identity(stable, STABLE_SHA, STABLE_TREE)
if config_path_from(env).read_text(encoding="utf-8") != baseline:
    die("config.yaml is not the baseline after rollback")
if prior.with_name(DROPIN_NAME).exists():
    die("fleet-retirement.conf is still present")
if any(path.name == DROPIN_NAME for path in dropin_paths(shown)):
    die("fleet-retirement.conf is still loaded")
journal_files = []
for directory in journal_dirs(env).values():
    journal_files.extend(private_dir_files(directory))
hold_manifest(EVIDENCE / "journals.manifest", manifest_lines(journal_files), create=False)
print(f"rolled-back mainpid={new_pid}")
print("STEP 10 OK")
PY
BASH
```

### 11. Control — confirm the running gateway is dcb3f950 again

On the Control host, read the process, drop-ins, config, profile env,
fleet env, worker projection, and journal checksums. The running root
must be the stable checkout. The new drop-in must be gone.
`fleet-delegation.conf` must match its backup.

```bash
bash -euo pipefail <<'BASH'
echo "host-role=Control hostname=$(hostname -s)"
test -x /usr/bin/python3.12
exec /usr/bin/python3.12 - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

UNIT = "hermes-gateway-control.service"
SHA = "c08cb1ebd073ee7946f49005dd45071366eeb688"
STABLE_SHA = "dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a"
TREE = "2b8888b984634b714d62646ddd5b6f48d073d160"
STABLE_TREE = "3d5f940738c5d1c0061645d06e74d3f88b034ae5"
PROVISIONER_SHA = "b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb"
NEW = Path("/opt/hermes-fleet-control") / SHA


def evidence_root() -> Path:
    """Root-owned witness, or the invoking user's state dir for a user unit."""
    if os.geteuid() == 0:
        return Path("/var/lib/hermes-control-deploy") / SHA
    return Path.home() / ".local/state/hermes-control-deploy" / SHA


EVIDENCE = evidence_root()
AGENT_VENV = Path("/home/hermes/.hermes/hermes-agent/venv")
PY = Path("/usr/bin/python3.12")
DROPIN_NAME = "fleet-retirement.conf"
PRIOR_DROPIN = "fleet-delegation.conf"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PRIVATE|NSEC|CREDENTIAL|KEY)$|^(AUTHORIZATION)$",
    re.IGNORECASE,
)
PATH_KEYS = {
    "HERMES_FLEET_CONTROL_ROOT",
    "HERMES_HOME",
    "FLEET_CONTROL_ENV_FILE",
    "FLEET_CONTROL_PROFILES_ROOT",
    "FLEET_DELEGATION_JOURNAL_DIR",
    "FLEET_ONBOARD_JOURNAL_DIR",
    "FLEET_RETIRE_JOURNAL_DIR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
}
PRESENCE_KEYS = (
    "BUZZ_PRIVATE_KEY",
    "FLEET_PROVISIONER_CALLER_TOKEN",
    "BUZZ_FLEET_MEMBERSHIP_TOKEN",
    "LITELLM_MASTER_KEY",
    "PVE_TOKEN_SECRET",
    "FLEET_CONTROL_PYTHON",
)


def die(message: str) -> None:
    sys.stderr.write("STOP: " + message + "\n")
    raise SystemExit(1)


def run(argv: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        err = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        safe = ""
        if err and len(err[-1]) < 240 and "://" not in err[-1] and "@" not in err[-1]:
            safe = ": " + err[-1]
        die(f"command failed ({completed.returncode}): {argv[0]}{safe}")
    return completed.stdout.decode("utf-8", "replace")


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git_out(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args], env=git_env()).strip()


def require_python312() -> None:
    if not PY.is_file() or not os.access(PY, os.X_OK):
        die("/usr/bin/python3.12 is missing or not executable")
    real = Path(os.path.realpath(PY))
    agent = AGENT_VENV.resolve() if AGENT_VENV.exists() else AGENT_VENV
    if real == agent or str(real).startswith(str(agent) + os.sep):
        die("/usr/bin/python3.12 resolves inside the Hermes agent virtualenv")


def systemctl_scope() -> list[str]:
    def loaded(user: bool) -> bool:
        argv = ["systemctl"]
        if user:
            argv.append("--user")
        argv.extend(["show", "-p", "LoadState", "--value", UNIT])
        completed = subprocess.run(argv, capture_output=True, text=True)
        return completed.returncode == 0 and completed.stdout.strip() == "loaded"

    system_loaded = loaded(False)
    user_loaded = loaded(True)
    if system_loaded and user_loaded:
        die("both system and user hermes-gateway-control.service are loaded")
    if system_loaded:
        if os.geteuid() != 0:
            die("the system unit requires this command to run as root")
        return ["systemctl"]
    if user_loaded:
        return ["systemctl", "--user"]
    die("hermes-gateway-control.service is not loaded")


def show(ctl: list[str], *props: str) -> dict[str, str]:
    text = run([*ctl, "show", *[f"-p{prop}" for prop in props], "--value", UNIT])
    lines = text.splitlines()
    if len(lines) != len(props):
        # systemctl --value prints one line per property; empty values still occupy a line
        # only when at least one property is empty at the end. Re-read without relying on blanks.
        raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
        found: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            found[key] = value
        missing = [prop for prop in props if prop not in found]
        if missing:
            die("systemctl show omitted properties")
        return {prop: found[prop] for prop in props}
    return dict(zip(props, lines))


def show_safe(ctl: list[str]) -> dict[str, str]:
    props = (
        "LoadState",
        "ActiveState",
        "SubState",
        "MainPID",
        "NRestarts",
        "FragmentPath",
        "DropInPaths",
        "EnvironmentFiles",
        "User",
        "Group",
        "WorkingDirectory",
        "ExecMainStartTimestamp",
    )
    raw = run([*ctl, "show", *[f"-p{prop}" for prop in props], UNIT])
    found: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in props:
            found[key] = value
    missing = [prop for prop in props if prop not in found]
    if missing:
        die("systemctl show omitted " + ",".join(missing))
    return {prop: found[prop] for prop in props}


def read_environ(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    env: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            env[key.decode("utf-8")] = value.decode("utf-8")
        except UnicodeDecodeError:
            die("gateway environ has a non-utf8 entry")
    return env


def descendants(pid: int) -> list[int]:
    found: list[int] = []

    def walk(parent: int) -> None:
        child_file = Path(f"/proc/{parent}/task/{parent}/children")
        try:
            text = child_file.read_text()
        except OSError:
            return
        for token in text.split():
            child = int(token)
            found.append(child)
            walk(child)

    walk(pid)
    return found


def checkout_dirs_of(pid: int) -> list[Path]:
    paths: list[Path] = []
    for proc in [pid, *descendants(pid)]:
        link = Path(f"/proc/{proc}/cwd")
        try:
            cwd = Path(os.path.realpath(link))
        except OSError:
            continue
        text = str(cwd)
        marker = "/opt/hermes-fleet-control/"
        if marker in text:
            root = Path(text.split(marker, 1)[0] + marker + text.split(marker, 1)[1].split("/", 1)[0])
            paths.append(root)
    return paths


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.lstat().st_mode))


def regular_files(directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        die(f"not a real directory: {directory}")
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        current = Path(dirpath)
        if current.is_symlink():
            die(f"symlink inside witness tree: {current}")
        dirnames[:] = sorted(name for name in dirnames if name not in {".git"})
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                die(f"symlink inside witness tree: {path}")
            if path.is_file():
                found.append(path)
    return found


def manifest_lines(paths: list[Path]) -> str:
    lines = []
    for path in sorted(paths, key=lambda item: str(item)):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            die(f"not a regular file: {path}")
        lines.append(f"{sha256_file(path)} {file_mode(path)} {path}")
    return "\n".join(lines) + ("\n" if lines else "")


def hold_manifest(path: Path, text: str, *, create: bool) -> None:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current != text:
            die(f"baseline differs and will not be replaced: {path.name}")
        return
    if not create:
        die(f"baseline is missing: {path.name}")
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def copy_once(source: Path, dest: Path) -> None:
    if source.is_symlink() or not source.is_file():
        die(f"refusing to back up a non-regular file: {source}")
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if dest.exists():
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            die(f"backup already exists and differs: {dest.name}")
        return
    dest.write_bytes(data)
    os.chmod(dest, 0o600)


def discover_stable() -> Path:
    root = Path("/opt/hermes-fleet-control")
    if not root.is_dir():
        die("/opt/hermes-fleet-control is absent")
    matches = sorted(path for path in root.glob("dcb3f950*") if path.is_dir() and not path.is_symlink())
    if len(matches) != 1:
        die("expected exactly one /opt/hermes-fleet-control/dcb3f950* checkout")
    stable = matches[0]
    if stable.resolve() == NEW.resolve():
        die("stable and new checkout paths are the same")
    if git_out(stable, "rev-parse", "HEAD") != STABLE_SHA:
        die("stable checkout HEAD is not dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a")
    if git_out(stable, "rev-parse", "HEAD^{tree}") != STABLE_TREE:
        die("stable checkout tree is not the dcb3f950 tree")
    return stable


def origin_description(repo: Path) -> str:
    url = git_out(repo, "remote", "get-url", "origin")
    if "://" not in url and ":" in url:
        return "origin=scp-like"
    if "@" in url.split("://", 1)[-1].split("/", 1)[0]:
        return "origin=url-with-userinfo"
    scheme, rest = url.split("://", 1)
    host = rest.split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", host):
        return "origin=present"
    return f"origin={scheme}://{host}"


def journal_dirs(env: dict[str, str]) -> dict[str, Path]:
    profile = env.get("FLEET_CONTROL_HERMES_PROFILE", "")
    if not NAME_RE.fullmatch(profile):
        die("FLEET_CONTROL_HERMES_PROFILE is absent or not a profile name")
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    if not root.startswith("/"):
        die("profiles root is not absolute")
    overrides = {
        "delegations": env.get("FLEET_DELEGATION_JOURNAL_DIR") or str(Path(root) / profile / "fleet-delegations"),
        "onboarding": env.get("FLEET_ONBOARD_JOURNAL_DIR") or str(Path(root) / profile / "fleet-onboarding"),
        "retirements": env.get("FLEET_RETIRE_JOURNAL_DIR") or str(Path(root) / profile / "fleet-retirements"),
    }
    paths = {name: Path(value) for name, value in overrides.items()}
    for path in paths.values():
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            die(f"journal directory is absent: {path}")
        mode = stat.S_IMODE(path.lstat().st_mode)
        if mode & 0o077:
            die(f"journal directory is not private: {path}")
    return paths


def private_dir_files(path: Path) -> list[Path]:
    files = regular_files(path)
    if not files:
        die(f"journal directory is empty: {path}")
    for file in files:
        if file.name.endswith(".lock"):
            fd = os.open(file, os.O_RDONLY)
            try:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                die(f"journal lock is held: {file.name}")
            finally:
                os.close(fd)
    return files


def parse_env_assignments(path: Path) -> list[tuple[str, str]]:
    if path.is_symlink() or not path.is_file():
        die(f"env file is not a regular file: {path}")
    rows: list[tuple[str, str]] = []
    for raw in path.read_bytes().splitlines():
        if raw.endswith(b"\\"):
            die("env file has a continuation line; refusing to parse it")
        line = raw.decode("utf-8", "replace").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            die("env file has a line without an assignment")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            die("env file has an unusual key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        rows.append((key, value))
    return rows


def classify_value(key: str, value: str) -> str:
    if value == "":
        return f"{key}=empty"
    if key in PATH_KEYS and value.startswith("/") and not re.search(r"\s", value):
        return f"{key}={value}"
    if key == "FLEET_PROVISIONER_URL":
        if value.startswith("https://") and "@" not in value and " " not in value:
            return "FLEET_PROVISIONER_URL=https-origin"
        return "FLEET_PROVISIONER_URL=present-not-printed"
    if SECRET_KEY_RE.search(key) or key in PRESENCE_KEYS:
        return f"{key}=present"
    return f"{key}=present"


def env_report(rows: list[tuple[str, str]]) -> list[str]:
    return [classify_value(key, value) for key, value in rows]


def require_assignment(rows: list[tuple[str, str]], key: str) -> str:
    values = [value for name, value in rows if name == key]
    if len(values) != 1 or values[0] == "":
        die(f"{key} is not present exactly once")
    return values[0]


def dropin_paths(shown: dict[str, str]) -> list[Path]:
    text = shown.get("DropInPaths", "").strip()
    if not text:
        die("the gateway unit has no drop-ins")
    return [Path(part) for part in text.split()]


def environment_files(shown: dict[str, str]) -> list[Path]:
    text = shown.get("EnvironmentFiles", "").strip()
    if text in {"", "[not set]", "n/a"}:
        return []
    paths = []
    for match in re.findall(r"-?(/[^()\s]+)", text):
        paths.append(Path(match))
    return paths


def prior_dropin(paths: list[Path]) -> Path:
    matches = [path for path in paths if path.name == PRIOR_DROPIN]
    if len(matches) != 1:
        die("fleet-delegation.conf is not exactly one loaded drop-in")
    path = matches[0]
    if path.is_symlink() or not path.is_file():
        die("fleet-delegation.conf is not a regular file")
    names = sorted(path.name for path in paths)
    if any(name > DROPIN_NAME for name in names):
        die("a drop-in sorts after fleet-retirement.conf")
    return path


def desired_dropin(prior: Path, stable: Path, new: Path) -> str:
    lines = [
        "# Checkout override for hermes-fleet-control " + SHA + ".",
        "# Loaded after fleet-delegation.conf. That file is not modified.",
        "[Service]",
        f"Environment=HERMES_FLEET_CONTROL_ROOT={new}",
    ]
    for raw in prior.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("Environment="):
            continue
        body = line[len("Environment=") :]
        if len(body) >= 2 and body[0] == body[-1] == '"':
            body = body[1:-1]
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        if key == "HERMES_FLEET_CONTROL_ROOT":
            if not value.startswith(str(stable)):
                die("fleet-delegation.conf roots the checkout somewhere else")
            continue
        if str(stable) in value:
            if SECRET_KEY_RE.search(key):
                die("a secret-like drop-in key contains the checkout path")
            lines.append(f"Environment={key}={value.replace(str(stable), str(new), 1)}")
    text = "\n".join(lines) + "\n"
    if "\n" in text.strip().split("HERMES_FLEET_CONTROL_ROOT=", 1)[-1].split("\n", 1)[0]:
        die("drop-in path is not a single line")
    return text


def yaml_loader():
    stable = discover_stable()
    candidate = stable / "runtime" / "venv" / "bin" / "python"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    die("stable checkout has no runtime/venv/bin/python to parse config.yaml")


def mcp_view(config_path: Path, parser: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink():
    raise SystemExit("config.yaml is a symlink")
text = path.read_text(encoding="utf-8")
import yaml
data = yaml.safe_load(text)
if not isinstance(data, dict):
    raise SystemExit("config.yaml is not a mapping")
servers = data.get("mcp_servers")
if not isinstance(servers, dict):
    raise SystemExit("mcp_servers is absent")
view = {}
for name, cfg in servers.items():
    if not isinstance(cfg, dict):
        raise SystemExit("mcp server entry is not a mapping")
    args = cfg.get("args")
    if args is None:
        args = []
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise SystemExit("mcp args are not strings")
    command = cfg.get("command")
    cwd = cfg.get("cwd")
    if command is not None and not isinstance(command, str):
        raise SystemExit("mcp command is not a string")
    if cwd is not None and not isinstance(cwd, str):
        raise SystemExit("mcp cwd is not a string")
    env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
    view[name] = {
        "command": command,
        "args": args,
        "cwd": cwd,
        "env_keys": sorted(str(key) for key in env),
    }
json.dump({"text_sha": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(), "servers": view}, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(config_path)], text=True)
    return json.loads(raw)


def config_path_from(env: dict[str, str]) -> Path:
    profile = env["FLEET_CONTROL_HERMES_PROFILE"]
    root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    path = Path(root) / profile / "config.yaml"
    if path.is_symlink() or not path.is_file():
        die("profile config.yaml is absent")
    return path


def rewrite_config(text: str, stable: Path, new: Path) -> tuple[str, str]:
    """Return (new_text, reason). reason is unchanged, interpolated, or rewritten."""
    stable_text = str(stable)
    new_text = str(new)
    if stable_text not in text and new_text not in text and "${HERMES_FLEET_CONTROL_ROOT}" in text:
        return text, "interpolated"
    if stable_text not in text and new_text in text:
        return text, "unchanged"
    if stable_text not in text:
        die("config.yaml does not reference the stable checkout or HERMES_FLEET_CONTROL_ROOT")
    return text.replace(stable_text, new_text), "rewritten"


def mcp_path_changed(before: dict, after: dict) -> bool:
    if before.keys() != after.keys():
        die("mcp server names would change")
    for name in before:
        for field in ("command", "args", "cwd", "env_keys"):
            if before[name][field] != after[name][field]:
                if field == "env_keys":
                    die("mcp env keys would change")
                old = before[name][field]
                new = after[name][field]
                if isinstance(old, list):
                    if not isinstance(new, list) or len(old) != len(new):
                        die("mcp args shape would change")
                    for left, right in zip(old, new):
                        if right != left.replace(str(discover_stable()), str(NEW)):
                            die("an mcp arg change is not the checkout prefix")
                elif isinstance(old, str):
                    if new != old.replace(str(discover_stable()), str(NEW)):
                        die("an mcp path change is not the checkout prefix")
                elif old is None and new is None:
                    continue
                else:
                    die("mcp field type would change")
    return True


def status_env(env_file: Path, gateway_env: dict[str, str]) -> dict[str, str]:
    child = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": gateway_env.get("HOME", "/root"),
        "LANG": "C",
        "FLEET_CONTROL_ENV_FILE": str(env_file),
    }
    for key in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE"):
        value = gateway_env.get(key, "")
        if value.startswith("/") and Path(value).exists() and not Path(value).is_symlink():
            child[key] = value
    return child


def run_status(checkout: Path, env_file: Path, gateway_env: dict[str, str], args: list[str]) -> dict:
    binary = checkout / "runtime" / "venv" / "bin" / "python"
    script = checkout / "fleet-status"
    if not binary.is_file() or not script.is_file():
        die("fleet-status runtime is absent in " + checkout.name)
    completed = subprocess.run(
        [str(binary), str(script), *args],
        cwd="/",
        env=status_env(env_file, gateway_env),
        capture_output=True,
    )
    if completed.returncode != 0:
        die("authenticated status read failed")
    if len(completed.stdout) > 1_000_000:
        die("status response is too large")
    try:
        body = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        die("status response is not json")
    if not isinstance(body, dict):
        die("status response is not an object")
    return body


def worker_names(body: dict) -> list[str]:
    if body.get("api_version") != "v1" or body.get("kind") != "WorkerList":
        die("status list is not a WorkerList")
    workers = body.get("workers")
    names: list[str] = []
    if isinstance(workers, list):
        for item in workers:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
            else:
                die("worker list entry has no name")
    elif isinstance(workers, dict):
        names.extend(str(key) for key in workers)
    else:
        die("workers field is not a list")
    for name in names:
        if not NAME_RE.fullmatch(name):
            die("worker list contains a name that is not safe to record")
    return sorted(set(names))


def project_worker(body: dict) -> dict:
    if body.get("api_version") != "v1" or body.get("kind") != "Worker":
        die("status read is not one worker")
    observed = body.get("observed") if isinstance(body.get("observed"), dict) else {}
    onboarding = body.get("onboarding") if isinstance(body.get("onboarding"), dict) else None
    tombstone = body.get("tombstone")
    tombstone_view = None
    if isinstance(tombstone, dict):
        tombstone_view = {
            "name": tombstone.get("name"),
            "vmid": tombstone.get("vmid"),
        }
    return {
        "name": body.get("name"),
        "declared": body.get("declared"),
        "retained": body.get("retained"),
        "tombstone": tombstone_view,
        "observed_state": observed.get("state"),
        "public_key_hex": observed.get("buzz_public_key_hex"),
        "vmid": observed.get("vmid"),
        "onboarding_id": None if onboarding is None else onboarding.get("id"),
        "onboarding_status": None if onboarding is None else onboarding.get("status"),
    }


def read_text(path: Path) -> str:
    if not path.is_file():
        die(f"missing evidence {path.name}")
    return path.read_text(encoding="utf-8")


def prepare_evidence() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.chmod(EVIDENCE, 0o700)
    if EVIDENCE.is_symlink():
        die("evidence directory is a symlink")


def lock_evidence() -> None:
    prepare_evidence()
    lock_path = EVIDENCE / "lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        die("another paste holds the evidence lock")
    # Hold the lock for the process lifetime.
    os.dup2(fd, 9)


def gateway_pid(shown: dict[str, str]) -> int:
    if shown["ActiveState"] != "active":
        die("hermes-gateway-control.service is not active")
    try:
        pid = int(shown["MainPID"])
    except ValueError:
        die("MainPID is not numeric")
    if pid <= 1 or not Path(f"/proc/{pid}").exists():
        die("MainPID is not a live process")
    return pid


def require_checkout_identity(path: Path, commit: str, tree: str) -> None:
    if git_out(path, "rev-parse", "HEAD") != commit:
        die(path.name + " HEAD is not " + commit)
    if git_out(path, "rev-parse", "HEAD^{tree}") != tree:
        die(path.name + " tree does not match")


def porcelain_allowed(repo: Path) -> None:
    text = run(["git", "-C", str(repo), "status", "--porcelain=v1", "-uall"], env=git_env())
    for line in text.splitlines():
        if len(line) < 4:
            die("unexpected git status line")
        path = line[3:]
        if " -> " in path:
            die("checkout has a rename")
        if not (
            path == "runtime"
            or path.startswith("runtime/")
            or path == "fleet-mcp/node_modules"
            or path.startswith("fleet-mcp/node_modules/")
        ):
            die("new checkout has an unexpected untracked or modified path")
        if not line.startswith("?? "):
            die("new checkout has a tracked change")


def yaml_leaves(parser: Path, path: Path) -> dict:
    code = r"""
import json, sys
from pathlib import Path
import yaml
data = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
leaves = {}
def walk(obj, prefix):
    if isinstance(obj, dict):
        for key, value in obj.items():
            walk(value, f"{prefix}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            walk(value, f"{prefix}[{index}]")
    else:
        leaves[prefix] = obj
walk(data, "")
json.dump(leaves, sys.stdout)
"""
    raw = subprocess.check_output([str(parser), "-c", code, str(path)], text=True)
    body = json.loads(raw)
    if not isinstance(body, dict):
        die("config.yaml leaves are not an object")
    return body


def assert_checkout_swap(old_leaves: dict, new_leaves: dict, stable: Path, new: Path) -> None:
    allowed = re.compile(r"^\.mcp_servers\.[^.]+\.(command|cwd|args\[\d+\])$")
    keys = set(old_leaves) | set(new_leaves)
    for key in sorted(keys):
        left = old_leaves.get(key)
        right = new_leaves.get(key)
        if left == right:
            continue
        if not allowed.fullmatch(key):
            die("config.yaml would change a field other than mcp command, args, or cwd")
        if not isinstance(left, str) or not isinstance(right, str):
            die("mcp path field is not a string")
        if right != left.replace(str(stable), str(new)):
            die("mcp path change is not the checkout prefix")


def node_bin() -> Path:
    found = shutil.which("node")
    if not found:
        die("node is not on PATH")
    path = Path(found)
    if not path.is_file() or not os.access(path, os.X_OK):
        die("node is not executable")
    version = run([str(path), "--version"]).strip()
    match = re.fullmatch(r"v(\d+)\..*", version)
    if not match or int(match.group(1)) < 20:
        die("node is older than 20")
    return path


def npm_bin() -> Path:
    found = shutil.which("npm")
    if not found:
        die("npm is not on PATH")
    path = Path(found)
    if not os.access(path, os.X_OK):
        die("npm is not executable")
    return path

print(f"host-role=Control hostname={os.uname().nodename}")
require_python312()
lock_evidence()
stable = discover_stable()
ctl = systemctl_scope()
shown = show_safe(ctl)
pid = gateway_pid(shown)
env = read_environ(pid)
if Path(env.get("HERMES_FLEET_CONTROL_ROOT", "")).resolve() != stable.resolve():
    die("running gateway is not the stable checkout")
require_checkout_identity(stable, STABLE_SHA, STABLE_TREE)
dirs = journal_dirs(env)
journal_files: list[Path] = []
for directory in dirs.values():
    journal_files.extend(private_dir_files(directory))
hold_manifest(EVIDENCE / "journals.manifest", manifest_lines(journal_files), create=False)
if any(path.name == DROPIN_NAME for path in dropin_paths(shown)):
    die("fleet-retirement.conf is still loaded")
if prior_dropin(dropin_paths(shown)).with_name(DROPIN_NAME).exists():
    die("fleet-retirement.conf is still on disk")
if sha256_file(prior_dropin(dropin_paths(shown))) != sha256_file(EVIDENCE / "fleet-delegation.conf"):
    die("fleet-delegation.conf changed")
config = config_path_from(env)
if config.read_text(encoding="utf-8") != (EVIDENCE / "config.yaml.baseline").read_text(encoding="utf-8"):
    die("config.yaml is not the baseline")
profile = env["FLEET_CONTROL_HERMES_PROFILE"]
profiles_root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
profile_env = Path(profiles_root) / profile / ".env"
env_file = Path(env["FLEET_CONTROL_ENV_FILE"])
if sha256_file(profile_env) != sha256_file(EVIDENCE / "profile.env.baseline"):
    die("profile .env changed")
if sha256_file(env_file) != sha256_file(EVIDENCE / "fleet.env.baseline"):
    die("fleet env file changed")
names = worker_names(run_status(stable, env_file, env, []))
expected_names = [line for line in (EVIDENCE / "worker-names").read_text(encoding="utf-8").splitlines() if line]
if names != expected_names:
    die("worker name set changed")
projection = {name: project_worker(run_status(stable, env_file, env, [name])) for name in names}
if projection != json.loads((EVIDENCE / "worker-projection.json").read_text(encoding="utf-8")):
    die("worker identity projection changed")
child_roots = {path.resolve() for path in checkout_dirs_of(pid)}
if NEW.resolve() in child_roots:
    die("a gateway child is still using the new checkout")
print("running-root=" + str(stable))
print("worker-names=" + ",".join(names))
print("STEP 11 OK")
PY
BASH
```

### 12. Provisioner — confirm rollback did not touch it

On the Provisioner, run the same read as step 2 again.

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

### 13. Proxmox node — confirm rollback did not touch a guest

On the Proxmox node, run the same read as step 3 again.

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
