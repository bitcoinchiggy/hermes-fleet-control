#!/usr/bin/env python3
"""Reviewed helpers for the c08cb1e Control deploy.

The shell entry points in this directory call this file. It does not
contact another machine. Mutating commands write only the evidence
directory, the new checkout, the gateway drop-in, and config.yaml.
"""

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
TREE = "2b8888b984634b714d62646ddd5b6f48d073d160"
STABLE_SHA = "dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a"
STABLE_TREE = "3d5f940738c5d1c0061645d06e74d3f88b034ae5"
NEW = Path("/opt/hermes-fleet-control") / SHA
OPT = Path("/opt/hermes-fleet-control")
PROFILES_ROOT_DEFAULT = "/home/hermes/.hermes/profiles"
DELEGATION_JOURNAL_KEY = "FLEET_DELEGATION_JOURNAL_DIR"
ONBOARD_JOURNAL_KEY = "FLEET_ONBOARD_JOURNAL_DIR"
RETIRE_JOURNAL_KEY = "FLEET_RETIRE_JOURNAL_DIR"
PROFILE_KEY = "FLEET_CONTROL_HERMES_PROFILE"
PROFILES_ROOT_KEY = "FLEET_CONTROL_PROFILES_ROOT"
JOURNAL_SUFFIX = {
    "delegations": "fleet-delegations",
    "onboarding": "fleet-onboarding",
    "retirements": "fleet-retirements",
}
JOURNAL_OVERRIDE = {
    "delegations": DELEGATION_JOURNAL_KEY,
    "onboarding": ONBOARD_JOURNAL_KEY,
    "retirements": RETIRE_JOURNAL_KEY,
}
NRESTARTS_MEASURES = (
    "NRestarts counts automatic restarts caused by the unit Restart= policy "
    "after an unclean exit. A manual systemctl restart does not increment it. "
    "A successful manual restart can leave NRestarts at 0."
)
PUBLIC_MCP = frozenset({"node", "npm", "python3", "python3.12"})
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
SAFE_PATH_RE = re.compile(r"^/[A-Za-z0-9._+/-]+$")
CHECKOUT_RE = re.compile(r"^/opt/hermes-fleet-control/[A-Za-z0-9._/-]+$")
HOST_RE = re.compile(r"^[A-Za-z0-9.-]+(?::[0-9]+)?$")
SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PRIVATE|NSEC|CREDENTIAL|KEY)$|^(AUTHORIZATION)$",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"sk-[A-Za-z0-9_-]+|nsec1[a-z0-9]+|\bbearer\b",
    re.IGNORECASE,
)
CREDENTIAL_FLAG_RE = re.compile(
    r"^--?(?:token|password|secret|api-key|apikey|authorization|auth|credential|key)(?:=.*)?$",
    re.IGNORECASE,
)
SAFE_FLAG_RE = re.compile(r"^--?[A-Za-z][A-Za-z0-9-]*$")
SKIP_WALK = {".git", "node_modules", "venv", "proc", "sys", "runtime"}
RETIREMENT_HEADER = (
    "# Checkout override for hermes-fleet-control "
    + SHA
    + ".\n"
    + "# Loaded after fleet-delegation.conf. That file is not modified.\n"
    + "[Service]\n"
    + "Environment=HERMES_FLEET_CONTROL_ROOT="
    + str(NEW)
    + "\n"
)


class Stop(Exception):
    """A guarded command refused to continue."""


def die(message: str) -> None:
    sys.stderr.write("STOP: " + message + "\n")
    raise Stop(message)


def out(line: str) -> None:
    sys.stdout.write(line + "\n")


def origin_credential(url: str) -> str:
    """Return present, absent, or unknown. Never echo the URL."""
    if "://" in url:
        _scheme, rest = url.split("://", 1)
        hostport = rest.split("/", 1)[0]
        if "@" in hostport:
            return "present"
        return "absent"
    if re.match(r"^[A-Za-z0-9._-]+@[^:]+:", url):
        return "absent"
    return "unknown"


def origin_form(url: str) -> tuple[str, str]:
    """Return a credential-free form and the credential class."""
    kind = origin_credential(url)
    if "://" in url:
        scheme, rest = url.split("://", 1)
        hostport = rest.split("/", 1)[0]
        host = hostport.split("@")[-1]
        if HOST_RE.fullmatch(host) and re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]*", scheme):
            return f"{scheme}://{host}", kind
        return "url", kind
    if kind == "absent" and re.match(r"^[A-Za-z0-9._-]+@[^:]+:", url):
        return "scp-like", kind
    return "unknown", kind


def classify_mcp_text(value: object) -> str:
    """Classify one MCP field. Arbitrary literals are not public."""
    if value is None or value == "":
        return "absent"
    if not isinstance(value, str):
        return "redacted"
    if SECRET_VALUE_RE.search(value) or "://" in value or "@" in value:
        return "redacted"
    if "${HERMES_FLEET_CONTROL_ROOT}" in value:
        return "interpolated"
    if CHECKOUT_RE.fullmatch(value):
        return "absolute-checkout:" + value
    if value.startswith("/") or re.search(r"\s", value):
        return "redacted"
    if CREDENTIAL_FLAG_RE.match(value):
        return "redacted" if "=" in value else "flag:" + value
    if SAFE_FLAG_RE.fullmatch(value):
        return "flag:" + value
    if value in PUBLIC_MCP:
        return "public:" + value
    return "redacted"


def classify_mcp_args(value: object) -> str:
    """Classify argv. A credential flag redacts the following value."""
    if isinstance(value, list):
        if not value:
            return "absent"
        parts: list[str] = []
        index = 0
        while index < len(value):
            item = value[index]
            if isinstance(item, str) and CREDENTIAL_FLAG_RE.match(item) and "=" not in item:
                parts.append("flag:" + item)
                if index + 1 < len(value):
                    parts.append("redacted")
                    index += 2
                    continue
            else:
                parts.append(classify_mcp_text(item))
            index += 1
        return ",".join(parts)
    return classify_mcp_text(value)


def report_origin_decision(url: str) -> list[str]:
    """Lines for a copy-or-stop decision. The URL is not included."""
    kind = origin_credential(url)
    if kind == "present":
        return ["origin-embedded-token=present", "origin-copied=no"]
    if kind == "absent":
        return ["origin-embedded-token=absent", "origin-copied=yes"]
    return ["origin-embedded-token=unknown", "origin-copied=no"]


def bind_origin(url: str, add_remote) -> str:
    """Copy a credential-free origin. Stop before add_remote otherwise."""
    lines = report_origin_decision(url)
    for line in lines:
        out(line)
    if lines[-1] != "origin-copied=yes":
        die("stable origin has an embedded credential or an unknown form; not copied")
    add_remote(url)
    return "copied"


def restart_blockers(
    before_pid: int,
    after: dict[str, str],
    environ: dict[str, str],
    expected_root: str,
    dropins: list[str],
    *,
    expect_retirement: bool,
) -> list[str]:
    """Health and process identity. NRestarts is not a success signal."""
    blockers: list[str] = []
    if after.get("ActiveState") != "active":
        blockers.append("active")
    if after.get("SubState") != "running":
        blockers.append("substate")
    try:
        pid = int(after.get("MainPID", "0"))
    except ValueError:
        pid = 0
    if pid <= 1 or pid == before_pid:
        blockers.append("mainpid")
    if environ.get("HERMES_FLEET_CONTROL_ROOT") != expected_root:
        blockers.append("root")
    if str(environ.get("FLEET_CONTROL_PYTHON", "")).strip():
        blockers.append("python-override")
    if "fleet-delegation.conf" not in dropins:
        blockers.append("delegation-dropin")
    if expect_retirement and "fleet-retirement.conf" not in dropins:
        blockers.append("retirement-dropin")
    if not expect_retirement and "fleet-retirement.conf" in dropins:
        blockers.append("retirement-dropin-still-loaded")
    return blockers


def control_journal_dir(env: dict[str, str], kind: str) -> Path:
    """Same path the Control loaders use. Does not create the directory."""
    override_key = JOURNAL_OVERRIDE[kind]
    suffix = JOURNAL_SUFFIX[kind]
    configured = str(env.get(override_key) or "").strip()
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            die("journal override is not absolute")
        return path
    profile = str(env.get(PROFILE_KEY) or "").strip()
    if not NAME_RE.fullmatch(profile):
        die("control profile is unusable")
    root = str(env.get(PROFILES_ROOT_KEY) or PROFILES_ROOT_DEFAULT)
    return Path(root) / profile / suffix


def deployed_state_dir(env: dict[str, str], checkout: str) -> str:
    """Call the deployed state-dir loader. Do not construct its default path."""
    import importlib

    root = str(checkout)
    if root not in sys.path:
        sys.path.insert(0, root)
    module = importlib.import_module("fleet_" + "provisioner.worker_identity")
    return module.resolve_state_dir(env)


def _json_files(directory: Path) -> list[Path]:
    found: list[Path] = []
    for entry in sorted(directory.iterdir(), key=lambda item: item.name):
        if entry.is_symlink():
            die("state entry is a symlink")
        if entry.name.endswith(".json") and entry.is_file():
            found.append(entry)
    return found


def inventory_state(state_dir: Path) -> dict[str, object]:
    """Count onboarding/*.json and tombstones/*.json. Do not return bodies."""
    onboarding = state_dir / "onboarding"
    tombstones = state_dir / "tombstones"
    if onboarding.is_symlink() or not onboarding.is_dir():
        die("onboarding directory is missing")
    if tombstones.is_symlink() or not tombstones.is_dir():
        die("tombstones directory is missing")
    onboarding_files = _json_files(onboarding)
    tombstone_files = _json_files(tombstones)
    if not tombstone_files:
        die("tombstones directory has no json files")
    return {
        "state_dir": state_dir,
        "onboarding_dir": onboarding,
        "tombstones_dir": tombstones,
        "onboarding_files": onboarding_files,
        "tombstone_files": tombstone_files,
    }


def state_report_lines(inventory: dict[str, object]) -> list[str]:
    onboarding_files = inventory["onboarding_files"]
    tombstone_files = inventory["tombstone_files"]
    assert isinstance(onboarding_files, list)
    assert isinstance(tombstone_files, list)
    return [
        "state-dir=" + str(inventory["state_dir"]),
        "onboarding-dir=" + str(inventory["onboarding_dir"]),
        "tombstones-dir=" + str(inventory["tombstones_dir"]),
        "onboarding-count=" + str(len(onboarding_files)),
        "tombstone-count=" + str(len(tombstone_files)),
    ]


def manifest_line(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    mode = oct(stat.S_IMODE(path.lstat().st_mode))
    return f"{digest} {mode} {path}"


def retirement_dropin(delegation_text: str, stable: str, new: str) -> str:
    """Header plus non-secret Environment lines whose value contains stable."""
    lines = [RETIREMENT_HEADER.rstrip("\n")]
    for raw in delegation_text.splitlines():
        if not raw.startswith("Environment="):
            continue
        body = raw[len("Environment=") :]
        key, sep, value = body.partition("=")
        if sep != "=":
            die("drop-in environment line has no value")
        if key == "HERMES_FLEET_CONTROL_ROOT":
            continue
        if stable not in value:
            continue
        if SECRET_KEY_RE.search(key):
            die("secret-like key contains the stable path")
        replaced = value.replace(stable, new, 1)
        if stable in replaced or replaced == value:
            die("stable path was not a single prefix swap")
        lines.append(f"Environment={key}={replaced}")
    return "\n".join(lines) + "\n"


def _load_yaml(text: str) -> dict:
    import yaml

    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        die("config yaml is not a mapping")
    return data


def _mcp_strings(data: dict, server_name: str) -> dict[str, str]:
    servers = data.get("mcp_servers")
    if not isinstance(servers, dict) or not isinstance(servers.get(server_name), dict):
        die("fleet mcp entry is missing")
    server = servers[server_name]
    found: dict[str, str] = {}
    command = server.get("command")
    cwd = server.get("cwd")
    if isinstance(command, str):
        found["command"] = command
    if isinstance(cwd, str):
        found["cwd"] = cwd
    args = server.get("args")
    if isinstance(args, list):
        for index, item in enumerate(args):
            if isinstance(item, str):
                found[f"args[{index}]"] = item
    return found


def rewrite_config(text: str, stable: str, new: str, server_name: str) -> tuple[str, str]:
    """Return (text, status). Status is interpolated, unchanged, or rewritten."""
    if stable not in text and "${HERMES_FLEET_CONTROL_ROOT}" in text:
        return text, "interpolated"
    if new in text and stable not in text:
        return text, "unchanged"
    if stable not in text:
        die("config has neither the stable path nor the checkout variable")
    before = _mcp_strings(_load_yaml(text), server_name)
    swaps = sum(1 for value in before.values() if stable in value)
    if text.count(stable) != swaps:
        die("stable path appears outside the fleet mcp command, cwd, or args")
    updated = text.replace(stable, new)
    if stable in updated:
        die("stable path remains after replacement")
    after = _mcp_strings(_load_yaml(updated), server_name)
    if set(before) != set(after):
        die("mcp field set changed")
    for key, old in before.items():
        new_value = after[key]
        if old == new_value:
            continue
        if old.replace(stable, new, 1) != new_value or stable not in old:
            die("a changed string is not one stable-prefix swap")
    before_rest = _without_mcp(text, server_name)
    after_rest = _without_mcp(updated, server_name)
    if before_rest != after_rest:
        die("yaml change is not only the fleet mcp command, cwd, or args")
    return updated, "rewritten"


def _without_mcp(text: str, server_name: str) -> str:
    data = _load_yaml(text)
    servers = data.get("mcp_servers")
    if isinstance(servers, dict):
        servers = dict(servers)
        servers.pop(server_name, None)
        data = dict(data)
        data["mcp_servers"] = servers
    return json.dumps(data, sort_keys=True, default=str)


def atomic_replace(path: Path, payload: bytes, *, mode: int | None = None) -> None:
    """O_EXCL temp, fsync, original mode and owner, then replace."""
    tmp = path.with_name(path.name + ".c08cb1e-tmp")
    if tmp.exists():
        die("config temp file already exists")
    st = path.lstat() if path.exists() else None
    if st is not None and stat.S_ISLNK(st.st_mode):
        die("refusing to replace a symlink")
    use_mode = stat.S_IMODE(st.st_mode) if st is not None else (0o644 if mode is None else mode)
    fd = os.open(str(tmp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, use_mode)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(tmp, use_mode)
    if st is not None:
        os.chown(tmp, st.st_uid, st.st_gid)
    os.replace(tmp, path)


def host_ready_blockers(facts: dict[str, str]) -> list[str]:
    """Unknown and missing prerequisites are blockers, not passes."""
    blockers: list[str] = []

    def need(key: str, ok) -> None:
        value = facts.get(key)
        if value is None or value in {"unknown", "unparsed", "unreadable", "not-live"}:
            blockers.append(key)
        elif not ok(value):
            blockers.append(key)

    def checkout_or_interpolated(value: str) -> bool:
        return value == "interpolated" or value.startswith("absolute-checkout:")

    def args_classified(value: str) -> bool:
        if value == "absent":
            return True
        for part in value.split(","):
            if part == "redacted" or part == "interpolated" or part == "absent":
                continue
            if part.startswith("public:") or part.startswith("flag:") or part.startswith("absolute-checkout:"):
                continue
            return False
        return True

    need("hostname", lambda value: value not in {"", "unknown"})
    need("unit-scope", lambda value: value in {"system", "user"})
    scope = facts.get("unit-scope")
    if scope in {"system", "user"}:
        need(f"{scope}-active", lambda value: value == "active")
        need(f"{scope}-process", lambda value: value == "live")
        need(f"{scope}-FLEET_CONTROL_PYTHON", lambda value: value == "absent")
        need(f"{scope}-HERMES_FLEET_CONTROL_INTEGRATION", lambda value: value == "1")
        need(f"{scope}-mcp-command", checkout_or_interpolated)
        need(f"{scope}-mcp-cwd", checkout_or_interpolated)
        need(f"{scope}-mcp-args", args_classified)
        need(
            f"{scope}-skill-load",
            lambda value: value
            in {"home-skills", "external-dir", "checkout-only-not-on-skill-path"},
        )
    need("stable-dir-count", lambda value: value == "1")
    need("stable-head-is-dcb3f950", lambda value: value == "yes")
    need("origin-embedded-token", lambda value: value == "absent")
    need("guest-node-signals", lambda value: value == "absent")
    need("provisioner-on-host", lambda value: value == "no")
    return blockers


def preflight_exit(blockers: list[str]) -> int:
    """0 is host-ready. 4 is a completed diagnostic that is not ready."""
    return 0 if not blockers else 4


def _self_check() -> None:
    form, token = origin_form("https://user:example-token@example.test/org/repo.git")
    assert form == "https://example.test" and token == "present"
    form, token = origin_form("https://example.test/org/repo.git")
    assert form == "https://example.test" and token == "absent"
    form, token = origin_form("git@example.test:org/repo.git")
    assert form == "scp-like" and token == "absent"
    assert classify_mcp_text("${HERMES_FLEET_CONTROL_ROOT}/fleet-mcp") == "interpolated"
    assert classify_mcp_text(
        "/opt/hermes-fleet-control/dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a/fleet-mcp"
    ).startswith("absolute-checkout:")
    assert classify_mcp_text("node") == "public:node"
    assert classify_mcp_text("sk-test-value") == "redacted"
    assert classify_mcp_text("nsec1qqqqqqqqqqqqqq") == "redacted"
    assert classify_mcp_text("Bearer test-token") == "redacted"
    assert "sk-test-value" not in classify_mcp_args(["--token", "sk-test-value"])
    assert classify_mcp_args(["--token", "sk-test-value"]) == "flag:--token,redacted"
    assert classify_mcp_args(["--password", "hunter2"]) == "flag:--password,redacted"
    assert classify_mcp_args(["--token", "node"]) == "flag:--token,redacted"
    decision = "\n".join(report_origin_decision("https://user:sk-test-value@example.test/org/repo.git"))
    assert "origin-embedded-token=present" in decision
    assert "origin-copied=no" in decision
    assert "sk-test-value" not in decision
    healthy = restart_blockers(
        10,
        {"ActiveState": "active", "SubState": "running", "MainPID": "11", "NRestarts": "0"},
        {"HERMES_FLEET_CONTROL_ROOT": str(NEW)},
        str(NEW),
        ["fleet-delegation.conf", "fleet-retirement.conf"],
        expect_retirement=True,
    )
    assert healthy == []


def _run(argv: list[str], *, cwd: str | None = None) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "LANG": "C",
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_TERMINAL_PROMPT": "0",
            },
        )
    except OSError:
        return 127, ""
    return completed.returncode, completed.stdout.decode("utf-8", "replace")


def git_read(repo: Path, *args: str) -> str | None:
    code, text = _run(
        ["git", "-C", str(repo), "-c", "credential.helper=", "--no-optional-locks", *args]
    )
    if code != 0:
        return None
    return text.strip()


def systemctl_loaded(user: bool) -> str:
    argv = ["systemctl"]
    if user:
        argv.append("--user")
    argv.extend(["show", "-p", "LoadState", "--value", UNIT])
    code, text = _run(argv)
    if code == 127:
        return "systemctl-absent"
    if code != 0:
        return "not-loaded"
    return "loaded" if text.strip() == "loaded" else "not-loaded"


def systemctl_show(user: bool) -> dict[str, str] | None:
    argv = ["systemctl"]
    if user:
        argv.append("--user")
    props = (
        "LoadState",
        "ActiveState",
        "SubState",
        "MainPID",
        "NRestarts",
        "FragmentPath",
        "DropInPaths",
    )
    argv.extend(["show", *[f"-p{prop}" for prop in props], UNIT])
    code, text = _run(argv)
    if code != 0:
        return None
    found: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in props:
            found[key] = value
    if any(prop not in found for prop in props):
        return None
    return found


def read_environ(pid: int) -> dict[str, str] | None:
    path = Path(f"/proc/{pid}/environ")
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    env: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            env[key.decode("utf-8")] = value.decode("utf-8")
        except UnicodeDecodeError:
            continue
    return env


def dropin_names(shown: dict[str, str]) -> list[str]:
    text = shown.get("DropInPaths", "").strip()
    if not text or text in {"[not set]", "n/a"}:
        return []
    return [Path(part).name for part in text.split()]


def stable_dirs() -> list[Path]:
    if not OPT.is_dir():
        return []
    return sorted(path for path in OPT.glob("dcb3f950*") if path.is_dir() and not path.is_symlink())


def safe_path(value: str) -> str:
    if SAFE_PATH_RE.fullmatch(value):
        return value
    return "redacted"


def presence(env: dict[str, str], key: str) -> str:
    if str(env.get(key, "")).strip() == "":
        return "absent"
    return "set"


def yaml_view(config: Path) -> dict | None:
    code = r"""
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink() or not path.is_file():
    raise SystemExit(2)
try:
    import yaml
except Exception:
    raise SystemExit(3)
try:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(4)
if not isinstance(data, dict):
    raise SystemExit(4)
servers = data.get("mcp_servers")
view = {}
if isinstance(servers, dict):
    for name, cfg in servers.items():
        if not isinstance(name, str) or not isinstance(cfg, dict):
            continue
        view[name] = {
            "command": cfg.get("command"),
            "args": cfg.get("args") if isinstance(cfg.get("args"), list) else [],
            "cwd": cfg.get("cwd"),
        }
skills = data.get("skills") if isinstance(data.get("skills"), dict) else {}
external = skills.get("external_dirs") if isinstance(skills.get("external_dirs"), list) else []
create_dir = skills.get("create_dir") if isinstance(skills.get("create_dir"), str) else ""
json.dump({"servers": view, "external_dirs": [item for item in external if isinstance(item, str)], "create_dir": create_dir}, sys.stdout)
"""
    candidates = [directory / "runtime" / "venv" / "bin" / "python" for directory in stable_dirs()]
    candidates.append(Path(sys.executable))
    for parser in candidates:
        if not parser.is_file() or not os.access(parser, os.X_OK):
            continue
        try:
            completed = subprocess.run(
                [str(parser), "-c", code, str(config)],
                capture_output=True,
                env={"PATH": "/usr/bin:/bin", "LANG": "C"},
            )
        except OSError:
            continue
        if completed.returncode == 0:
            try:
                return json.loads(completed.stdout.decode("utf-8"))
            except json.JSONDecodeError:
                return None
        if completed.returncode == 3:
            continue
        return None
    return None


def skill_hits(root: Path) -> list[Path]:
    if not root.is_dir() or root.is_symlink():
        return []
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        try:
            depth = len(current.relative_to(root).parts)
        except ValueError:
            dirnames.clear()
            continue
        if depth > 5:
            dirnames.clear()
            continue
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_WALK and not name.startswith("."))
        if "SKILL.md" in filenames and current.name == "fleet-delegation":
            path = current / "SKILL.md"
            if path.is_file() and not path.is_symlink():
                found.append(path)
        if len(found) > 20:
            break
    return found


def file_sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def provisioner_units() -> list[str]:
    code, text = _run(["systemctl", "list-units", "--type=service", "--all", "--plain", "--no-legend"])
    if code != 0:
        return []
    names = []
    for line in text.splitlines():
        if not line.strip():
            continue
        name = line.split()[0]
        if name.startswith("hermes-gateway") or "hermes-fleet-control" in name:
            continue
        if "provisioner" in name or name in {"hermes-fleet.service", "fleet-provisioner.service"}:
            names.append(name)
    return names


def cmd_preflight() -> int:
    _self_check()
    facts: dict[str, str] = {}

    def fact(key: str, value: str) -> None:
        facts[key] = value
        out(f"{key}={value}")

    out("preflight=c08cb1e-control")
    out("read-only=yes")
    out("other-hosts=not-contacted")
    out("nrestarts-measures=" + NRESTARTS_MEASURES)
    code, short = _run(["hostname", "-s"])
    fact("hostname", short.strip() if code == 0 and short.strip() else "unknown")
    code, fqdn = _run(["hostname", "-f"])
    fqdn_text = fqdn.strip()
    if code == 0 and fqdn_text and re.fullmatch(r"[A-Za-z0-9.-]+", fqdn_text):
        out("hostname-fqdn=" + fqdn_text)
    else:
        out("hostname-fqdn=unavailable")
    system_state = systemctl_loaded(False)
    user_state = systemctl_loaded(True)
    out(f"system-unit={system_state}")
    out(f"user-unit={user_state}")
    if system_state == "loaded" and user_state == "loaded":
        fact("unit-scope", "both")
    elif system_state == "loaded":
        fact("unit-scope", "system")
    elif user_state == "loaded":
        fact("unit-scope", "user")
    else:
        fact("unit-scope", "neither")
    guest_node = Path("/etc/pve").is_dir() and shutil.which("qm") is not None
    fact("guest-node-signals", "present" if guest_node else "absent")
    if facts["unit-scope"] in {"system", "user"}:
        _report_gateway(facts["unit-scope"], facts["unit-scope"] == "user", facts)
    matches = stable_dirs()
    fact("stable-dir-count", str(len(matches)))
    if len(matches) == 1:
        stable = matches[0]
        out("stable-dir=" + str(stable))
        head = git_read(stable, "rev-parse", "HEAD")
        tree = git_read(stable, "rev-parse", "HEAD^{tree}")
        out("stable-head=" + (head if head else "unreadable"))
        out("stable-tree=" + (tree if tree else "unreadable"))
        fact("stable-head-is-dcb3f950", "yes" if head == STABLE_SHA else "no")
        origin = git_read(stable, "remote", "get-url", "origin")
        if origin is None:
            out("origin-form=unreadable")
            fact("origin-embedded-token", "unknown")
        else:
            form, token = origin_form(origin)
            out("origin-form=" + form)
            fact("origin-embedded-token", token)
    else:
        for path in matches:
            out("stable-dir=" + str(path))
        fact("stable-head-is-dcb3f950", "unknown")
        fact("origin-embedded-token", "unknown")
    out("new-checkout-exists=" + ("yes" if NEW.exists() else "no"))
    _report_provisioner(facts)
    roles = []
    if system_state == "loaded" or user_state == "loaded":
        roles.append("control")
    if guest_node:
        roles.append("guest-node")
    if facts.get("provisioner-on-host") == "yes":
        roles.append("provisioner")
    out("roles-on-this-host=" + (",".join(roles) if roles else "none"))
    blockers = host_ready_blockers(facts)
    out("diagnostic=completed")
    out("host-ready=" + ("yes" if not blockers else "no"))
    out("host-ready-blockers=" + (",".join(blockers) if blockers else "none"))
    return preflight_exit(blockers)


def _report_gateway(scope: str, user: bool, facts: dict[str, str]) -> None:
    shown = systemctl_show(user)
    if shown is None:
        out(f"{scope}-show=unreadable")
        facts[f"{scope}-active"] = "unreadable"
        facts[f"{scope}-process"] = "unreadable"
        return
    facts[f"{scope}-active"] = shown["ActiveState"]
    out(f"{scope}-active={shown['ActiveState']}")
    out(f"{scope}-substate={shown['SubState']}")
    out(f"{scope}-nrestarts={shown['NRestarts']}")
    fragment = shown["FragmentPath"]
    out(f"{scope}-fragment=" + (safe_path(fragment) if fragment.startswith("/") else "redacted"))
    names = dropin_names(shown)
    out(f"{scope}-dropins=" + (",".join(names) if names else "none"))
    try:
        pid = int(shown["MainPID"])
    except ValueError:
        pid = 0
    if shown["ActiveState"] != "active" or pid <= 1 or not Path(f"/proc/{pid}").exists():
        facts[f"{scope}-process"] = "not-live"
        out(f"{scope}-process=not-live")
        return
    env = read_environ(pid)
    if env is None:
        facts[f"{scope}-process"] = "unreadable"
        out(f"{scope}-environ=unreadable")
        return
    facts[f"{scope}-process"] = "live"
    out(f"{scope}-process=live")
    out(f"{scope}-pid={pid}")
    python_presence = presence(env, "FLEET_CONTROL_PYTHON")
    facts[f"{scope}-FLEET_CONTROL_PYTHON"] = python_presence
    out(f"{scope}-FLEET_CONTROL_PYTHON={python_presence}")
    integration = "1" if env.get("HERMES_FLEET_CONTROL_INTEGRATION") == "1" else presence(
        env, "HERMES_FLEET_CONTROL_INTEGRATION"
    )
    facts[f"{scope}-HERMES_FLEET_CONTROL_INTEGRATION"] = integration
    out(f"{scope}-HERMES_FLEET_CONTROL_INTEGRATION={integration}")
    root = env.get("HERMES_FLEET_CONTROL_ROOT", "")
    out(f"{scope}-HERMES_FLEET_CONTROL_ROOT=" + (safe_path(root) if root.startswith("/") else "absent-or-redacted"))
    home = env.get("HERMES_HOME", "")
    server_name = env.get("HERMES_FLEET_MCP_SERVER", "")
    profiles_root = env.get(PROFILES_ROOT_KEY) or PROFILES_ROOT_DEFAULT
    profile = env.get(PROFILE_KEY, "")
    if NAME_RE.fullmatch(profile) and profiles_root.startswith("/") and SAFE_PATH_RE.fullmatch(profiles_root):
        _report_mcp(scope, env, Path(profiles_root) / profile / "config.yaml", root, home, facts)
    else:
        facts[f"{scope}-mcp-command"] = "unknown"
        facts[f"{scope}-mcp-cwd"] = "unknown"
        facts[f"{scope}-mcp-args"] = "unknown"
        facts[f"{scope}-skill-load"] = "unknown"
        out(f"{scope}-mcp-config=unknown")
        out(f"{scope}-skill-load=unknown")


def _report_mcp(
    scope: str,
    env: dict[str, str],
    config: Path,
    root: str,
    home: str,
    facts: dict[str, str],
) -> None:
    view = None
    if config.is_symlink() or not config.is_file():
        facts[f"{scope}-mcp-command"] = "unknown"
        facts[f"{scope}-mcp-cwd"] = "unknown"
        facts[f"{scope}-mcp-args"] = "unknown"
        out(f"{scope}-mcp-config=unknown")
    else:
        view = yaml_view(config)
        if view is None:
            facts[f"{scope}-mcp-command"] = "unparsed"
            facts[f"{scope}-mcp-cwd"] = "unparsed"
            facts[f"{scope}-mcp-args"] = "unparsed"
            out(f"{scope}-mcp-config=unparsed")
        else:
            server_name = env.get("HERMES_FLEET_MCP_SERVER", "")
            servers = view.get("servers") or {}
            server = servers.get(server_name) if isinstance(servers, dict) else None
            if not isinstance(server, dict):
                facts[f"{scope}-mcp-command"] = "unknown"
                facts[f"{scope}-mcp-cwd"] = "unknown"
                facts[f"{scope}-mcp-args"] = "unknown"
                out(f"{scope}-mcp-entry=absent")
            else:
                command = classify_mcp_text(server.get("command"))
                cwd = classify_mcp_text(server.get("cwd"))
                args = classify_mcp_args(server.get("args"))
                facts[f"{scope}-mcp-command"] = command
                facts[f"{scope}-mcp-cwd"] = cwd
                facts[f"{scope}-mcp-args"] = args
                out(f"{scope}-mcp-command={command}")
                out(f"{scope}-mcp-args={args}")
                out(f"{scope}-mcp-cwd={cwd}")
    checkout_skill = []
    if root.startswith("/") and SAFE_PATH_RE.fullmatch(root):
        candidate = Path(root) / "skills" / "fleet-delegation" / "SKILL.md"
        if candidate.is_file() and not candidate.is_symlink():
            checkout_skill.append(candidate)
    home_hits = skill_hits(Path(home) / "skills") if home.startswith("/") and SAFE_PATH_RE.fullmatch(home) else []
    external_hit = False
    if view and root.startswith("/"):
        checkout_skills = Path(root) / "skills"
        for item in view.get("external_dirs") or []:
            if isinstance(item, str) and SAFE_PATH_RE.fullmatch(item):
                try:
                    if Path(item).resolve() == checkout_skills.resolve():
                        external_hit = True
                except OSError:
                    continue
    if home_hits:
        preference = "home-skills"
    elif external_hit:
        preference = "external-dir"
    elif checkout_skill:
        preference = "checkout-only-not-on-skill-path"
    else:
        preference = "not-found"
    facts[f"{scope}-skill-load"] = preference
    out(f"{scope}-skill-load={preference}")
    out(f"{scope}-skill-load-basis=fleet-tip-loader-not-process-maps")


def _report_provisioner(facts: dict[str, str]) -> None:
    names = provisioner_units()
    if not names:
        facts["provisioner-on-host"] = "no"
        out("provisioner-unit=not-on-this-host")
        out("onboarding-dir=not-on-this-host")
        out("tombstones-dir=not-on-this-host")
        return
    facts["provisioner-on-host"] = "yes"
    active = []
    for name in names:
        code, text = _run(["systemctl", "show", "-p", "ActiveState", "--value", name])
        state = text.strip() if code == 0 else "unknown"
        out(f"provisioner-unit={name} active={state}")
        if state == "active":
            active.append(name)
    if len(active) != 1:
        out("onboarding-dir=unknown")
        out("tombstones-dir=unknown")
        return
    code, text = _run(["systemctl", "show", "-p", "MainPID", "--value", active[0]])
    try:
        pid = int(text.strip()) if code == 0 else 0
    except ValueError:
        pid = 0
    env = read_environ(pid) if pid > 1 else None
    if env is None:
        out("onboarding-dir=unknown")
        out("tombstones-dir=unknown")
        return
    try:
        cwd = os.path.realpath(f"/proc/{pid}/cwd")
        top = git_read(Path(cwd), "rev-parse", "--show-toplevel") or cwd
        state = deployed_state_dir(env, top)
        inventory = inventory_state(Path(state))
    except Stop:
        out("onboarding-dir=unknown")
        out("tombstones-dir=unknown")
        return
    for line in state_report_lines(inventory):
        out(line)


def cmd_provisioner_witness() -> int:
    """Read-only except the witness directory. State bodies are not printed."""
    if os.geteuid() != 0:
        die("run this command as root on the Provisioner")
    if Path("/etc/pve").is_dir() and shutil.which("qm"):
        die("this host looks like the guest node")
    code, text = _run(["systemctl", "show", "-p", "LoadState", "--value", UNIT])
    if code == 0 and text.strip() == "loaded":
        die("hermes-gateway-control.service is loaded; this is not the Provisioner command")
    names = [
        name
        for name in provisioner_units()
        if _run(["systemctl", "show", "-p", "ActiveState", "--value", name])[1].strip() == "active"
    ]
    if len(names) != 1:
        die("expected exactly one active provisioner unit")
    unit = names[0]
    shown = _run(
        ["systemctl", "show", "-p", "MainPID", "-p", "NRestarts", "-p", "ActiveState", "-p", "SubState", unit]
    )[1]
    props = {}
    for line in shown.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            props[key] = value
    pid = int(props.get("MainPID", "0"))
    if props.get("ActiveState") != "active" or props.get("SubState") != "running" or pid <= 1:
        die("provisioner is not active and running")
    env = read_environ(pid)
    if env is None:
        die("provisioner environ is unreadable")
    if str(env.get("FLEET_PROVISIONER_GIT_REF", "")).strip():
        die("FLEET_PROVISIONER_GIT_REF is set")
    cwd = os.path.realpath(f"/proc/{pid}/cwd")
    top = git_read(Path(cwd), "rev-parse", "--show-toplevel")
    if top is None:
        die("provisioner checkout is unreadable")
    head = git_read(Path(top), "rev-parse", "HEAD")
    if head != "b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb":
        die("provisioner checkout HEAD is not the pinned revision")
    state = deployed_state_dir(env, top)
    inventory = inventory_state(Path(state))
    files = list(inventory["onboarding_files"]) + list(inventory["tombstone_files"])
    manifest = "".join(manifest_line(path) + "\n" for path in sorted(files, key=str))
    evidence = Path("/var/lib/hermes-control-deploy/c08cb1e-provisioner-witness")
    evidence.mkdir(parents=True, exist_ok=True)
    os.chmod(evidence, 0o700)
    identity = f"unit={unit}\npid={pid}\nhead={head}\n"
    manifest_path = evidence / "witness.manifest"
    identity_path = evidence / "identity"
    if not manifest_path.exists():
        manifest_path.write_text(manifest, encoding="utf-8")
        identity_path.write_text(identity, encoding="utf-8")
        os.chmod(manifest_path, 0o600)
        os.chmod(identity_path, 0o600)
        status = "created"
    else:
        if manifest_path.read_text(encoding="utf-8") != manifest or identity_path.read_text(encoding="utf-8") != identity:
            die("provisioner witness changed")
        status = "matched"
    out(f"unit={unit} pid={pid} head={head}")
    out("nrestarts=" + props.get("NRestarts", "unknown"))
    out("nrestarts-measures=" + NRESTARTS_MEASURES)
    for line in state_report_lines(inventory):
        out(line)
    out("baseline=" + status)
    out("PROVISIONER OK")
    return 0


def evidence_root() -> Path:
    if os.geteuid() == 0:
        return Path("/var/lib/hermes-control-deploy") / SHA
    return Path.home() / ".local" / "state" / "hermes-control-deploy" / SHA


def journal_manifest(env: dict[str, str]) -> str:
    """Hash journal files. Does not print or return their bodies."""
    import fcntl

    lines: list[str] = []
    for kind in ("delegations", "onboarding", "retirements"):
        directory = control_journal_dir(env, kind)
        if directory.is_symlink() or not directory.is_dir():
            die(kind + " journal dir is missing")
        if stat.S_IMODE(directory.stat().st_mode) & 0o077:
            die(kind + " journal dir is not private")
        entries = [path for path in directory.iterdir() if not path.is_symlink() and path.is_file()]
        files = [path for path in entries if not path.name.endswith(".lock")]
        if not files:
            die(kind + " journal dir is empty")
        for path in entries:
            if not path.name.endswith(".lock"):
                continue
            fd = os.open(str(path), os.O_RDWR)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                die(kind + " journal lock is taken")
            finally:
                os.close(fd)
        lines.extend(manifest_line(path) for path in sorted(files, key=lambda item: item.name))
    return "\n".join(lines) + "\n"


def project_workers(body: dict) -> list[dict[str, object]]:
    """Keep the compared worker fields. Drop every other value."""
    workers = body.get("workers")
    if body.get("kind") == "Worker":
        workers = [body]
    if not isinstance(workers, list):
        die("worker status is not a list")
    projected = []
    for doc in workers:
        if not isinstance(doc, dict):
            die("worker status entry is not an object")
        tomb = doc.get("tombstone") if isinstance(doc.get("tombstone"), dict) else None
        onboarding = doc.get("onboarding") if isinstance(doc.get("onboarding"), dict) else None
        observed = doc.get("observed") if isinstance(doc.get("observed"), dict) else {}
        projected.append(
            {
                "name": doc.get("name"),
                "declared": doc.get("declared"),
                "retained": doc.get("retained"),
                "tombstone_name": None if tomb is None else tomb.get("name"),
                "tombstone_vmid": None if tomb is None else tomb.get("vmid"),
                "observed_state": observed.get("state"),
                "public_key_hex": observed.get("buzz_public_key_hex"),
                "vmid": observed.get("vmid"),
                "onboarding_id": None if onboarding is None else onboarding.get("id"),
                "onboarding_status": None if onboarding is None else onboarding.get("status"),
            }
        )
    return sorted(projected, key=lambda item: str(item["name"]))


def require_tools(listed: set[str]) -> None:
    required = {"worker_status", "ensure_worker", "onboard_worker", "delegate_worker", "retire_worker"}
    missing = required - listed
    if missing:
        die("mcp tools missing")
    if "send_message" in listed:
        die("mcp send_message is present")


def apply_configure(
    delegation_text: str,
    config_text: str,
    stable: str,
    new: str,
    server_name: str,
) -> tuple[str, str, str]:
    """Return (drop-in, config bytes status, config text)."""
    dropin = retirement_dropin(delegation_text, stable, new)
    updated, status = rewrite_config(config_text, stable, new, server_name)
    return dropin, status, updated


def cmd_install() -> int:
    """Create the new checkout. Never copy a credential-bearing origin."""
    matches = stable_dirs()
    if len(matches) != 1:
        die("stable checkout is not exactly one directory")
    stable = matches[0]
    origin = git_read(stable, "remote", "get-url", "origin")
    if origin is None:
        die("stable origin is unreadable")
    if NEW.exists() and not (NEW / ".git").is_dir():
        die("new path exists and is not a git directory")
    OPT.mkdir(parents=True, exist_ok=True)
    if not (NEW / ".git").exists():
        code, _text = _run(["git", "init", "--quiet", str(NEW)])
        if code != 0:
            die("git init failed")
    existing = git_read(NEW, "remote", "get-url", "origin")
    if existing is None:
        def add_remote(url: str) -> None:
            code, _text = _run(["git", "-C", str(NEW), "remote", "add", "origin", url])
            if code != 0:
                die("git remote add failed")

        bind_origin(origin, add_remote)
    else:
        for line in report_origin_decision(existing):
            out(line)
        if origin_credential(existing) != "absent":
            die("new checkout origin has an embedded credential or an unknown form")
    code, _text = _run(
        ["git", "-C", str(NEW), "-c", "credential.helper=", "fetch", "--quiet", "--no-tags", "origin", SHA]
    )
    if code != 0:
        die("git fetch failed")
    code, _text = _run(["git", "-C", str(NEW), "checkout", "--quiet", "--detach", SHA])
    if code != 0:
        die("git checkout failed")
    head = git_read(NEW, "rev-parse", "HEAD")
    tree = git_read(NEW, "rev-parse", "HEAD^{tree}")
    if head != SHA or tree != TREE:
        die("new checkout does not match the deploy pins")
    _ensure_runtime()
    out("STEP 4 OK")
    return 0


def _ensure_runtime() -> None:
    interpreter = "/usr/bin/python3.12"
    venv_py = NEW / "runtime" / "venv" / "bin" / "python"
    code, _text = _run([str(venv_py), "-c", "import cryptography, yaml"], cwd="/")
    if code != 0:
        code, text = _run(
            [interpreter, str(NEW / "install-control-runtime"), "--python", interpreter],
            cwd="/",
        )
        if code != 0 or text.strip() != str(venv_py):
            die("runtime install failed")
    mcp = NEW / "fleet-mcp"
    code, _text = _run(["npm", "ls", "--omit=dev", "--depth=0"], cwd=str(mcp))
    if code != 0:
        code, _text = _run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=str(mcp))
        if code != 0:
            die("npm ci failed")
        code, _text = _run(["npm", "ls", "--omit=dev", "--depth=0"], cwd=str(mcp))
        if code != 0:
            die("npm ls failed")
    code, _text = _run(["node", "--check", str(mcp / "index.js")])
    if code != 0:
        die("node check failed")


def delegation_path(shown: dict[str, str]) -> Path:
    for part in shown.get("DropInPaths", "").split():
        if Path(part).name == "fleet-delegation.conf":
            return Path(part)
    die("fleet-delegation.conf is not loaded")


def selected_scope() -> tuple[str, bool]:
    system_state = systemctl_loaded(False)
    user_state = systemctl_loaded(True)
    if system_state == "loaded" and user_state == "loaded":
        die("both unit scopes are loaded")
    if system_state == "loaded":
        return "system", False
    if user_state == "loaded":
        return "user", True
    die("neither unit scope is loaded")


def _live_gateway(user: bool) -> tuple[dict[str, str], dict[str, str], int]:
    shown = systemctl_show(user)
    if shown is None:
        die("gateway show failed")
    try:
        pid = int(shown["MainPID"])
    except ValueError:
        pid = 0
    if shown["ActiveState"] != "active" or shown["SubState"] != "running" or pid <= 1:
        die("gateway is not active and running")
    env = read_environ(pid)
    if env is None:
        die("gateway environ is unreadable")
    return shown, env, pid


def _private_write(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    os.chmod(path, 0o600)


def _save_baseline(evidence: Path, files: dict[str, bytes]) -> str:
    manifest = evidence / "journals.manifest"
    if manifest.exists():
        for name, data in files.items():
            current = evidence / name
            if not current.is_file() or current.read_bytes() != data:
                die("baseline changed")
        return "matched"
    if evidence.exists() and any(path.is_file() for path in evidence.iterdir()):
        die("partial baseline")
    evidence.mkdir(parents=True, exist_ok=True)
    os.chmod(evidence, 0o700)
    for name, data in files.items():
        _private_write(evidence / name, data)
    return "created"


def _env_key_names(text: str) -> str:
    names = []
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        names.append(line.split("=", 1)[0])
    return ",".join(names)


def cmd_baseline() -> int:
    """Write the evidence baseline once. Does not restart or create the checkout."""
    _scope, user = selected_scope()
    shown, env, pid = _live_gateway(user)
    if str(env.get("FLEET_CONTROL_PYTHON", "")).strip():
        die("FLEET_CONTROL_PYTHON is set")
    if env.get("HERMES_FLEET_CONTROL_INTEGRATION") != "1":
        die("HERMES_FLEET_CONTROL_INTEGRATION is not 1")
    matches = stable_dirs()
    if len(matches) != 1:
        die("stable checkout is not exactly one directory")
    stable = matches[0]
    root = env.get("HERMES_FLEET_CONTROL_ROOT", "")
    if root != str(stable):
        die("running root is not the stable checkout")
    manifest = journal_manifest(env)
    names = dropin_names(shown)
    delegation = delegation_path(shown)
    if not delegation.is_file():
        die("fleet-delegation.conf is not loaded")
    if any(name > "fleet-retirement.conf" for name in names):
        die("a drop-in sorts after fleet-retirement.conf")
    profile = env.get(PROFILE_KEY, "")
    profiles = env.get(PROFILES_ROOT_KEY) or PROFILES_ROOT_DEFAULT
    config = Path(profiles) / profile / "config.yaml"
    profile_env = Path(profiles) / profile / ".env"
    fleet_env = Path(str(env.get("FLEET_CONTROL_ENV_FILE") or ""))
    fragment = Path(shown["FragmentPath"])
    for path in (config, profile_env, fleet_env, fragment):
        if path.is_symlink() or not path.is_file():
            die("baseline input is missing")
    files = {
        "journals.manifest": manifest.encode(),
        "fleet-delegation.conf": delegation.read_bytes(),
        "config.yaml": config.read_bytes(),
        "config.mode": str(stat.S_IMODE(config.stat().st_mode)).encode(),
        "fleet.env": fleet_env.read_bytes(),
        "profile.env": profile_env.read_bytes(),
        "unit.fragment": fragment.read_bytes(),
        "mainpid": str(pid).encode(),
        "stable_dir": str(stable).encode(),
        "scope": (_scope + "\n").encode(),
    }
    status = _save_baseline(evidence_root(), files)
    out(f"scope={_scope}")
    out(f"ActiveState={shown['ActiveState']}")
    out(f"SubState={shown['SubState']}")
    out(f"MainPID={pid}")
    out("NRestarts=" + shown["NRestarts"])
    out("nrestarts-measures=" + NRESTARTS_MEASURES)
    out("dropins=" + ",".join(names))
    out("fleet-env-keys=" + _env_key_names(fleet_env.read_text(encoding="utf-8", errors="replace")))
    out("FLEET_CONTROL_PYTHON=absent")
    out("journal-manifest=sha256:" + hashlib.sha256(manifest.encode()).hexdigest())
    out("stable=" + str(stable))
    out("running-root=" + root)
    out("baseline=" + status)
    out("STEP 1 OK")
    return 0


def _require_manifest(env: dict[str, str]) -> None:
    recorded = (evidence_root() / "journals.manifest").read_text(encoding="utf-8")
    if journal_manifest(env) != recorded:
        die("journal manifest changed")


def cmd_configure() -> int:
    evidence = evidence_root()
    if not (evidence / "journals.manifest").is_file():
        die("baseline is missing")
    _scope, user = selected_scope()
    shown, env, _pid = _live_gateway(user)
    _require_manifest(env)
    stable = (evidence / "stable_dir").read_text(encoding="utf-8").strip()
    delegation = delegation_path(shown)
    if delegation.read_bytes() != (evidence / "fleet-delegation.conf").read_bytes():
        die("fleet-delegation.conf changed")
    server = env.get("HERMES_FLEET_MCP_SERVER", "")
    profile = env.get(PROFILE_KEY, "")
    profiles = env.get(PROFILES_ROOT_KEY) or PROFILES_ROOT_DEFAULT
    config = Path(profiles) / profile / "config.yaml"
    dropin, status, updated = apply_configure(
        delegation.read_text(encoding="utf-8"),
        config.read_text(encoding="utf-8"),
        stable,
        str(NEW),
        server,
    )
    dest = delegation.with_name("fleet-retirement.conf")
    if dest.exists():
        if dest.read_text(encoding="utf-8") != dropin:
            die("fleet-retirement.conf bytes differ")
    else:
        atomic_replace(dest, dropin.encode(), mode=0o644)
    if status == "rewritten":
        atomic_replace(config, updated.encode())
    elif config.read_text(encoding="utf-8") != updated:
        die("config.yaml bytes differ")
    _private_write(evidence / "fleet-retirement.conf.desired", dropin.encode())
    _private_write(evidence / "config.yaml.deployed", updated.encode())
    _private_write(evidence / "config.status", status.encode())
    out("config=" + status)
    out("config.changed=" + ("yes" if status == "rewritten" else "no"))
    out("STEP 5 OK")
    return 0


def _restart(user: bool, before_pid: int, expected_root: str, expect_retirement: bool) -> None:
    argv_prefix = ["systemctl", "--user"] if user else ["systemctl"]
    if _run([*argv_prefix, "daemon-reload"])[0] != 0:
        die("daemon-reload failed")
    if _run([*argv_prefix, "restart", UNIT])[0] != 0:
        die("restart failed")
    shown, env, pid = _live_gateway(user)
    blockers = restart_blockers(
        before_pid,
        shown,
        env,
        expected_root,
        dropin_names(shown),
        expect_retirement=expect_retirement,
    )
    out("NRestarts=" + shown.get("NRestarts", "unknown"))
    out("nrestarts-measures=" + NRESTARTS_MEASURES)
    if blockers:
        die("restart health failed (" + ",".join(blockers) + ")")
    if pid == before_pid:
        die("MainPID did not change")
    _require_manifest(env)


def cmd_restart() -> int:
    evidence = evidence_root()
    _scope, user = selected_scope()
    shown, env, pid = _live_gateway(user)
    _require_manifest(env)
    desired = evidence / "fleet-retirement.conf.desired"
    if not desired.is_file():
        die("desired drop-in is missing")
    root = env.get("HERMES_FLEET_CONTROL_ROOT", "")
    loaded = dropin_names(shown)
    if root == str(NEW) and "fleet-retirement.conf" in loaded:
        out("restart=skipped")
        out("STEP 6 OK")
        return 0
    stable = (evidence / "stable_dir").read_text(encoding="utf-8").strip()
    if root != stable:
        die("running root is neither stable nor the new checkout")
    _restart(user, pid, str(NEW), True)
    out("restart=done")
    out("STEP 6 OK")
    return 0


def cmd_verify() -> int:
    _scope, user = selected_scope()
    _shown, env, _pid = _live_gateway(user)
    if env.get("HERMES_FLEET_CONTROL_ROOT") != str(NEW):
        die("running root is not the new checkout")
    _require_manifest(env)
    evidence = evidence_root()
    stable = (evidence / "stable_dir").read_text(encoding="utf-8").strip()
    status = (evidence / "config.status").read_text(encoding="utf-8").strip()
    profile = env.get(PROFILE_KEY, "")
    profiles = env.get(PROFILES_ROOT_KEY) or PROFILES_ROOT_DEFAULT
    config = (Path(profiles) / profile / "config.yaml").read_text(encoding="utf-8")
    if status != "interpolated" and stable in config:
        die("config still names the stable checkout")
    out("STEP 7 OK")
    return 0


def cmd_rollback() -> int:
    evidence = evidence_root()
    _scope, user = selected_scope()
    shown, env, pid = _live_gateway(user)
    _require_manifest(env)
    delegation = delegation_path(shown)
    if (evidence / "fleet-delegation.conf").read_bytes() != delegation.read_bytes():
        die("fleet-delegation.conf changed")
    profile = env.get(PROFILE_KEY, "")
    profiles = env.get(PROFILES_ROOT_KEY) or PROFILES_ROOT_DEFAULT
    config = Path(profiles) / profile / "config.yaml"
    baseline = (evidence / "config.yaml").read_bytes()
    deployed = (evidence / "config.yaml.deployed").read_bytes() if (evidence / "config.yaml.deployed").is_file() else None
    live = config.read_bytes()
    if live == deployed and deployed is not None:
        atomic_replace(config, baseline)
        os.chmod(config, int((evidence / "config.mode").read_text(encoding="utf-8")))
    elif live != baseline:
        die("config.yaml is neither the baseline nor the deployed bytes")
    dropin = delegation.with_name("fleet-retirement.conf")
    desired = (evidence / "fleet-retirement.conf.desired").read_bytes() if (evidence / "fleet-retirement.conf.desired").is_file() else None
    if dropin.exists():
        if desired is None or dropin.read_bytes() != desired:
            die("fleet-retirement.conf bytes differ")
        removed = dropin.with_name("fleet-retirement.conf.removed")
        _private_write(removed, dropin.read_bytes())
        dropin.unlink()
    stable = (evidence / "stable_dir").read_text(encoding="utf-8").strip()
    root = env.get("HERMES_FLEET_CONTROL_ROOT", "")
    if root == stable and not dropin.exists() and config.read_bytes() == baseline:
        out("rollback=already-stable")
        out("STEP 10 OK")
        return 0
    _restart(user, pid, stable, False)
    out("rollback=done")
    out("STEP 10 OK")
    return 0


def cmd_confirm() -> int:
    evidence = evidence_root()
    _scope, user = selected_scope()
    shown, env, pid = _live_gateway(user)
    stable = (evidence / "stable_dir").read_text(encoding="utf-8").strip()
    if env.get("HERMES_FLEET_CONTROL_ROOT") != stable:
        die("running root is not the stable checkout")
    head = git_read(Path(stable), "rev-parse", "HEAD")
    tree = git_read(Path(stable), "rev-parse", "HEAD^{tree}")
    if head != STABLE_SHA or tree != STABLE_TREE:
        die("stable checkout does not match the pins")
    if "fleet-retirement.conf" in dropin_names(shown):
        die("retirement drop-in is still loaded")
    if any(Path(part).name == "fleet-retirement.conf" for part in shown.get("DropInPaths", "").split()):
        die("retirement drop-in is still loaded")
    if delegation_path(shown).with_name("fleet-retirement.conf").exists():
        die("retirement drop-in is still on disk")
    _require_manifest(env)
    if _cwd_under(pid, NEW):
        die("a gateway process cwd is the new checkout")
    out("STEP 11 OK")
    return 0


def _cwd_under(pid: int, root: Path) -> bool:
    """True when pid or a descendant has a cwd inside root. Unreadable cwd stops."""
    wanted = str(root)
    seen = {pid}
    pending = [pid]
    while pending:
        current = pending.pop()
        cwd = Path(f"/proc/{current}/cwd")
        try:
            target = os.path.realpath(cwd)
        except OSError:
            die("process cwd is unreadable")
        if target == wanted or target.startswith(wanted + os.sep):
            return True
        children = Path(f"/proc/{current}/task/{current}/children")
        try:
            text = children.read_text(encoding="utf-8")
        except OSError:
            die("process children are unreadable")
        for item in text.split():
            try:
                child = int(item)
            except ValueError:
                continue
            if child not in seen:
                seen.add(child)
                pending.append(child)
    return False


def main(argv: list[str]) -> int:
    commands = {
        "preflight": cmd_preflight,
        "baseline": cmd_baseline,
        "provisioner-witness": cmd_provisioner_witness,
        "install": cmd_install,
        "configure": cmd_configure,
        "restart": cmd_restart,
        "verify": cmd_verify,
        "rollback": cmd_rollback,
        "confirm": cmd_confirm,
    }
    if len(argv) != 2 or argv[1] not in commands:
        sys.stderr.write("STOP: usage: c08cb1e_material.py " + "|".join(commands) + "\n")
        return 2
    try:
        return commands[argv[1]]()
    except Stop:
        return 1
    except Exception as exc:
        sys.stderr.write("STOP: command failed (" + type(exc).__name__ + ")\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
