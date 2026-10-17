#!/usr/bin/python3.12
"""Reviewed helpers for the c08cb1e Control deploy.

The shell entry points in this directory call this file. It does not
contact another machine. Preflight only reads. baseline, install,
configure, restart, and rollback write the evidence directory, the new
checkout, the gateway drop-in, or config.yaml. provisioner-witness
creates /var/lib/hermes-control-deploy/c08cb1e-provisioner-witness.
The guest-node shell script is a separate host mutation.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
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
ALLOWED_ABSOLUTE = frozenset({
    "/usr/bin/node",
    "/usr/bin/npm",
    "/usr/bin/python3",
    "/usr/bin/python3.12",
})
ALLOWED_FLAGS = frozenset({"--version", "--stdio"})
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
ENV_NAME_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)$")
SAFE_PATH_RE = re.compile(r"^/[A-Za-z0-9._+/-]+$")
CHECKOUT_RE = re.compile(r"^/opt/hermes-fleet-control/[A-Za-z0-9._/-]+$")
RELATIVE_SCRIPT_RE = re.compile(r"^[A-Za-z0-9._-]+\.(?:js|mjs|cjs)$")
HOST_RE = re.compile(r"^[A-Za-z0-9.-]+(?::[0-9]+)?$")
FIXED_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"
AGENT_VENV = Path("/home/hermes/.hermes/hermes-agent/venv")
RESTART_SETTLE_SECONDS = 10
LOCK_WAIT_SECONDS = 20
FLEET_ROOT_VAR = "${HERMES_FLEET_CONTROL_ROOT}"
REQUIRED_ENV_KEYS = (
    "FLEET_PROVISIONER_URL",
    "FLEET_PROVISIONER_CALLER_TOKEN",
)
SHOW_PROPS = (
    "LoadState",
    "ActiveState",
    "SubState",
    "MainPID",
    "NRestarts",
    "FragmentPath",
    "DropInPaths",
    "NeedDaemonReload",
    "EnvironmentFiles",
    "ExecStart",
    "WorkingDirectory",
    "Restart",
    "TriggeredBy",
    "ControlGroup",
)
# systemctl stop suppresses Restart=, including always and on-success.
# An empty or unrecognized value stays fail-closed.
SAFE_STOP_RESTART = frozenset(
    {"no", "on-failure", "on-abnormal", "on-watchdog", "on-abort", "always", "on-success"}
)
EXEC_ENV_KEYS = frozenset(
    {
        "NODE_OPTIONS",
        "NODE_PATH",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
        "PYTHONEXECUTABLE",
        "PYTHONUSERBASE",
        "PYTHONSAFEPATH",
        "PYTHONDEVMODE",
        "FLEET_CONTROL_PYTHON",
        "PATH",
    }
)
_POLICY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
_UNIT_NAME_RE = re.compile(r"^[A-Za-z0-9:@._-]+$")
SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PRIVATE|NSEC|CREDENTIAL|KEY)$|^(AUTHORIZATION)$",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"sk-[A-Za-z0-9_-]+|nsec1[a-z0-9]+|\bbearer\b",
    re.IGNORECASE,
)
CREDENTIAL_FLAG_RE = re.compile(
    r"^--?(?:"
    r"token|password|secret|api-key|apikey|authorization|auth|credential|key|"
    r"pass|passwd|bearer|"
    r"(?:access|client|auth)[-_]?(?:token|secret|key)"
    r")(?:=.*)?$",
    re.IGNORECASE,
)
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


def warn(message: str) -> None:
    sys.stdout.write("WARNING: " + message + "\n")


def _check(condition: bool) -> None:
    """Fail closed. Unlike assert, this still runs under python -O."""
    if not condition:
        die("self-check failed")


def out(line: str) -> None:
    sys.stdout.write(line + "\n")


def origin_credential(url: str) -> str:
    """Return present, absent, or unknown. Never echo the URL."""
    if "?" in url or "#" in url or ";" in url:
        return "unknown"
    if "://" in url:
        scheme, rest = url.split("://", 1)
        hostport = rest.split("/", 1)[0]
        if "@" in hostport:
            userinfo = hostport.rsplit("@", 1)[0]
            if scheme.lower() == "ssh" and ":" not in userinfo:
                return "absent"
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
    if SECRET_VALUE_RE.search(value) or "://" in value or "@" in value or "?" in value or "#" in value:
        return "redacted"
    if "${HERMES_FLEET_CONTROL_ROOT}" in value:
        return "interpolated"
    if CHECKOUT_RE.fullmatch(value):
        return "absolute-checkout:" + value
    if value.startswith("/") or value.startswith("-") or re.search(r"\s", value):
        return "redacted"
    if value in PUBLIC_MCP:
        return "public:" + value
    return "redacted"


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def resolve_fixed_tool(name: str) -> str | None:
    """Resolve a tool on the pinned PATH. Do not search the inherited PATH."""
    return shutil.which(name, path=FIXED_PATH)


def relative_script_fact(command: object, cwd: object, arg: object, root: str) -> str | None:
    """Basename fact for one relative MCP script, or None when it is not safe.

    command must be the literal node and resolve on the pinned PATH to an
    executable regular file outside the checkout. cwd must be exactly
    <root>/fleet-mcp, must not be a symlink, and its real path must stay
    inside the checkout. The argument is a single basename ending in .js,
    .mjs, or .cjs. realpath(cwd/arg) must stay inside both realpath(cwd)
    and the checkout, and must be a regular file that is not a symlink.
    """
    if command != "node" or not isinstance(cwd, str) or not isinstance(arg, str) or not root:
        return None
    if not RELATIVE_SCRIPT_RE.fullmatch(arg) or "/" in arg or ".." in arg:
        return None
    if cwd != str(Path(root) / "fleet-mcp"):
        return None
    cwd_path = Path(cwd)
    if cwd_path.is_symlink():
        return None
    try:
        root_real = Path(root).resolve(strict=True)
        cwd_real = cwd_path.resolve(strict=True)
    except OSError:
        return None
    if cwd_real == root_real or not _is_inside(cwd_real, root_real):
        return None
    node = resolve_fixed_tool("node")
    if node is None:
        return None
    node_path = Path(node)
    try:
        node_real = node_path.resolve(strict=True)
    except OSError:
        return None
    if not node_real.is_file() or not os.access(node_real, os.X_OK):
        return None
    if _is_inside(node_real, root_real):
        return None
    script = cwd_path / arg
    if script.is_symlink() or not script.is_file():
        return None
    try:
        script_real = script.resolve(strict=True)
    except OSError:
        return None
    if script_real.is_symlink() or not script_real.is_file():
        return None
    if not _is_inside(script_real, cwd_real) or not _is_inside(script_real, root_real):
        return None
    return "relative-script:" + arg


def classify_mcp_args(
    value: object,
    *,
    command: object = "",
    cwd: object = "",
    root: str = "",
) -> str:
    """Classify argv. Only --version and --stdio are printed as flags."""
    if isinstance(value, list):
        if not value:
            return "absent"
        parts: list[str] = []
        index = 0
        while index < len(value):
            item = value[index]
            flag = isinstance(item, str) and item.startswith("-") and "=" not in item
            if flag:
                allowed = item in ALLOWED_FLAGS and CREDENTIAL_FLAG_RE.match(item) is None
                parts.append("flag:" + item if allowed else "redacted")
                if index + 1 < len(value):
                    nxt = value[index + 1]
                    if not (isinstance(nxt, str) and nxt.startswith("-") and "=" not in nxt):
                        if allowed:
                            relative = relative_script_fact(command, cwd, nxt, root)
                            parts.append(relative if relative is not None else classify_mcp_text(nxt))
                        else:
                            parts.append("redacted")
                        index += 2
                        continue
            else:
                relative = relative_script_fact(command, cwd, item, root)
                parts.append(relative if relative is not None else classify_mcp_text(item))
            index += 1
        return ",".join(parts)
    relative = relative_script_fact(command, cwd, value, root)
    return relative if relative is not None else classify_mcp_text(value)


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

    sys.dont_write_bytecode = True
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
    if not isinstance(onboarding_files, list) or not isinstance(tombstone_files, list):
        die("state inventory is incomplete")
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
    env = server.get("env")
    if isinstance(env, dict):
        for key, value in env.items():
            if isinstance(key, str) and isinstance(value, str):
                found["env." + key] = value
    return found


def rewrite_config(text: str, stable: str, new: str, server_name: str) -> tuple[str, str]:
    """Return (text, status). Status is interpolated, unchanged, or rewritten."""
    if stable not in text and "${HERMES_FLEET_CONTROL_ROOT}" in text:
        fields = _mcp_strings(_load_yaml(text), server_name)
        if not any("${HERMES_FLEET_CONTROL_ROOT}" in value for value in fields.values()):
            die("checkout variable is not on the fleet mcp entry")
        return text, "interpolated"
    if new in text and stable not in text:
        return text, "unchanged"
    if stable not in text:
        die("config has neither the stable path nor the checkout variable")
    before = _mcp_strings(_load_yaml(text), server_name)
    swaps = sum(1 for value in before.values() if stable in value)
    if text.count(stable) != swaps:
        die("stable path appears outside the fleet mcp command, cwd, args, or env")
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
        die("yaml change is not only the fleet mcp command, cwd, args, or env")
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


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            die("short write")
        view = view[written:]


def atomic_replace(path: Path, payload: bytes, *, mode: int | None = None) -> None:
    """O_EXCL temp, full write, fsync, owner then mode, replace, fsync the directory."""
    tmp = path.with_name(path.name + ".c08cb1e-tmp")
    if tmp.is_symlink() or tmp.exists():
        die("config temp file already exists")
    if path.is_symlink():
        die("refusing to replace a symlink")
    try:
        st = path.lstat()
    except FileNotFoundError:
        st = None
    if st is not None and stat.S_ISLNK(st.st_mode):
        die("refusing to replace a symlink")
    use_mode = stat.S_IMODE(st.st_mode) if st is not None else (0o644 if mode is None else mode)
    fd = os.open(str(tmp), os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        _write_all(fd, payload)
        os.fsync(fd)
    except Exception:
        os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.close(fd)
    try:
        if st is not None:
            os.chown(tmp, st.st_uid, st.st_gid)
        os.chmod(tmp, use_mode)
        os.replace(tmp, path)
        dirfd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except Exception:
        try:
            if tmp.exists() and not tmp.is_symlink():
                os.unlink(tmp)
        except OSError:
            pass
        raise


def mcp_args_configuration_ok(value: str) -> bool:
    """True only for argument shapes the diagnostic can validate.

    `redacted` is safe to print. It does not show that the hidden text is
    the right configuration, so it is not a host-ready argument.
    """
    if value == "absent":
        return True
    if not value:
        return False
    for part in value.split(","):
        if part in {"interpolated", "absent"}:
            continue
        if part.startswith("absolute-checkout:"):
            if CHECKOUT_RE.fullmatch(part.removeprefix("absolute-checkout:")):
                continue
            return False
        if part.startswith("public:"):
            if part.removeprefix("public:") in PUBLIC_MCP:
                continue
            return False
        if part.startswith("relative-script:"):
            name = part.removeprefix("relative-script:")
            if RELATIVE_SCRIPT_RE.fullmatch(name) and "/" not in name and ".." not in name:
                continue
            return False
        if part.startswith("flag:"):
            if part.removeprefix("flag:") in ALLOWED_FLAGS:
                continue
            return False
        return False
    return True


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
        need(f"{scope}-mcp-args", mcp_args_configuration_ok)
        need(
            f"{scope}-skill-load",
            lambda value: value
            in {"home-skills", "external-dir", "checkout-only-not-on-skill-path"},
        )
        need(f"{scope}-running-root-is-stable", lambda value: value == "yes")
        need(f"{scope}-delegation-loaded", lambda value: value == "yes")
        need(f"{scope}-dropin-order", lambda value: value == "ok")
        need(f"{scope}-retirement-absent", lambda value: value == "yes")
        need(f"{scope}-fleet-env-file", lambda value: value == "regular")
        need(f"{scope}-journals", lambda value: value == "private-nonempty")
        need(f"{scope}-need-daemon-reload", lambda value: value == "no")
        need(f"{scope}-effective-unit", lambda value: value == "ok")
        if scope == "system":
            need(f"{scope}-delegation-location", lambda value: value == "system-config")
            need(f"{scope}-euid-root", lambda value: value == "yes")
        else:
            need(f"{scope}-delegation-location", lambda value: value == "user-config")
    need("stable-dir-count", lambda value: value == "1")
    need("stable-head-is-dcb3f950", lambda value: value == "yes")
    need("stable-tree-is-pinned", lambda value: value == "yes")
    need("origin-embedded-token", lambda value: value == "absent")
    need("guest-node-signals", lambda value: value == "absent")
    need("provisioner-on-host", lambda value: value == "no")
    need("pyyaml", lambda value: value == "present")
    need("node", lambda value: value == "ok")
    need("npm", lambda value: value == "present")
    need("git", lambda value: value == "present")
    need("python312", lambda value: value == "outside-venv")
    return blockers


def preflight_exit(blockers: list[str]) -> int:
    """0 is host-ready. 4 is a completed diagnostic that is not ready."""
    return 0 if not blockers else 4


def _self_check() -> None:
    form, token = origin_form("https://user:example-token@example.test/org/repo.git")
    _check(form == "https://example.test" and token == "present")
    form, token = origin_form("https://example.test/org/repo.git")
    _check(form == "https://example.test" and token == "absent")
    form, token = origin_form("git@example.test:org/repo.git")
    _check(form == "scp-like" and token == "absent")
    _check(origin_credential("ssh://git@example.test/org/repo.git") == "absent")
    _check(origin_credential("https://example.test/r.git?access_token=query-secret") == "unknown")
    _check(origin_credential("https://example.test/r.git;tok=semicolon-secret") == "unknown")
    _check(classify_mcp_text("${HERMES_FLEET_CONTROL_ROOT}/fleet-mcp") == "interpolated")
    _check(
        classify_mcp_text(
            "/opt/hermes-fleet-control/dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a/fleet-mcp"
        ).startswith("absolute-checkout:")
    )
    _check(classify_mcp_text("node") == "public:node")
    _check(classify_mcp_text("sk-test-value") == "redacted")
    _check(classify_mcp_text("nsec1qqqqqqqqqqqqqq") == "redacted")
    _check(classify_mcp_text("Bearer test-token") == "redacted")
    hidden = classify_mcp_args(["--token", "sk-test-value"])
    _check("sk-test-value" not in hidden and hidden == "redacted,redacted")
    _check(classify_mcp_args(["--version", "node"]) == "flag:--version,public:node")
    hidden_public = classify_mcp_args(["--password", "python3"])
    _check(hidden_public == "redacted,redacted" and "python3" not in hidden_public)
    _check(classify_mcp_text("-pHunter2secret") == "redacted")
    _check(CREDENTIAL_FLAG_RE.match("--access-token") is not None)
    _check(CREDENTIAL_FLAG_RE.match("--client_secret") is not None)
    _check(CREDENTIAL_FLAG_RE.match("--passwd") is not None)
    _check(CREDENTIAL_FLAG_RE.match("--bearer") is not None)
    _check(CREDENTIAL_FLAG_RE.match("--version") is None)
    plain = "\n".join(env_key_report("OK_NAME=1\nMIIabc+/xyz,qqq=hidden\n"))
    _check("fleet-env-name-count=1" in plain and "fleet-env-unparsed-lines=1" in plain)
    _check("OK_NAME" not in plain and "MIIabc" not in plain)
    pem = "\n".join(
        env_key_report(
            'SSL_KEY="-----BEGIN PRIVATE KEY-----\n'
            "q83vEiZZtopSecretTail==\n"
            '-----END PRIVATE KEY-----"\n'
            "GOOD=1\n"
        )
    )
    _check("fleet-env-name-count=2" in pem)
    _check("q83vEiZZtopSecretTail" not in pem and "SSL_KEY" not in pem and "GOOD" not in pem)
    quoted = "\n".join(env_key_report('A="line1\nSECRETWORD=abc"\nOK_NAME=1\n'))
    _check("fleet-env-name-count=2" in quoted and "SECRETWORD" not in quoted)
    _check(mcp_args_configuration_ok("absent"))
    _check(mcp_args_configuration_ok("public:node,flag:--version,interpolated"))
    _check(not mcp_args_configuration_ok("public:node,redacted"))
    _check(not mcp_args_configuration_ok("flag:--token"))
    decision = "\n".join(report_origin_decision("https://user:sk-test-value@example.test/org/repo.git"))
    _check("origin-embedded-token=present" in decision)
    _check("origin-copied=no" in decision)
    _check("sk-test-value" not in decision)
    query = "\n".join(report_origin_decision("https://example.test/r.git?access_token=query-secret"))
    _check("origin-embedded-token=unknown" in query and "query-secret" not in query)
    healthy = restart_blockers(
        10,
        {"ActiveState": "active", "SubState": "running", "MainPID": "11", "NRestarts": "0"},
        {"HERMES_FLEET_CONTROL_ROOT": str(NEW)},
        str(NEW),
        ["fleet-delegation.conf", "fleet-retirement.conf"],
        expect_retirement=True,
    )
    _check(healthy == [])


def _run(argv: list[str], *, cwd: str | None = None) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            env={
                "PATH": FIXED_PATH,
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
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "safe.directory=" + str(repo),
            "-c",
            "credential.helper=",
            "--no-optional-locks",
            *args,
        ]
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
    argv.extend(["show", *[f"-p{prop}" for prop in SHOW_PROPS], UNIT])
    code, text = _run(argv)
    if code != 0:
        return None
    found: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in SHOW_PROPS:
            found[key] = value
    if any(prop not in found for prop in SHOW_PROPS):
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
    """Parse config.yaml in this process. Do not spawn a checkout interpreter."""
    sys.dont_write_bytecode = True
    if config.is_symlink() or not config.is_file():
        return None
    try:
        import yaml
    except ImportError:
        return None
    try:
        data = yaml.safe_load(config.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    servers = data.get("mcp_servers")
    view: dict[str, object] = {}
    if isinstance(servers, dict):
        parsed: dict[str, dict[str, object]] = {}
        for name, cfg in servers.items():
            if not isinstance(name, str) or not isinstance(cfg, dict):
                continue
            parsed[name] = {
                "command": cfg.get("command"),
                "args": cfg.get("args") if isinstance(cfg.get("args"), list) else [],
                "cwd": cfg.get("cwd"),
            }
        view["servers"] = parsed
    skills = data.get("skills") if isinstance(data.get("skills"), dict) else {}
    external = skills.get("external_dirs") if isinstance(skills.get("external_dirs"), list) else []
    create_dir = skills.get("create_dir") if isinstance(skills.get("create_dir"), str) else ""
    view["external_dirs"] = [item for item in external if isinstance(item, str)]
    view["create_dir"] = create_dir
    return view


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


def python312_status() -> str:
    """outside-venv, inside-venv, or missing. Does not print a path."""
    py = Path("/usr/bin/python3.12")
    if not py.exists() and not py.is_symlink():
        return "missing"
    try:
        resolved = py.resolve(strict=True)
    except OSError:
        return "missing"
    try:
        if _is_inside(resolved, AGENT_VENV):
            return "inside-venv"
    except OSError:
        return "missing"
    if not os.access(resolved, os.X_OK):
        return "missing"
    return "outside-venv"


def node_status() -> str:
    node = resolve_fixed_tool("node")
    if node is None:
        return "absent"
    code, text = _run([node, "-p", "process.versions.node.split('.')[0]"])
    if code != 0 or not text.strip().isdigit():
        return "unknown"
    return "ok" if int(text.strip()) >= 20 else "old"


def tool_status(name: str) -> str:
    return "present" if resolve_fixed_tool(name) else "absent"


def pyyaml_status() -> str:
    sys.dont_write_bytecode = True
    try:
        import yaml  # noqa: F401
    except ImportError:
        return "absent"
    return "present"


def _report_tools(facts: dict[str, str]) -> None:
    def fact(key: str, value: str) -> None:
        facts[key] = value
        out(f"{key}={value}")

    fact("python312", python312_status())
    fact("pyyaml", pyyaml_status())
    fact("node", node_status())
    fact("npm", tool_status("npm"))
    fact("git", tool_status("git"))


def dropin_order_ok(names: list[str]) -> bool:
    return not any(name > "fleet-retirement.conf" for name in names)


def _strictly_under(path: Path, root: Path) -> bool:
    """True when path is a non-symlink file inside root after resolve."""
    if path.is_symlink():
        return False
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
        resolved.relative_to(root_resolved)
    except (OSError, ValueError):
        return False
    return resolved != root_resolved


def delegation_location(path: Path, user: bool) -> str:
    if user:
        root = Path.home() / ".config" / "systemd" / "user"
        return "user-config" if _strictly_under(path, root) else "rejected"
    root = Path("/etc/systemd/system")
    return "system-config" if _strictly_under(path, root) else "rejected"


def _quote_left_open(text: str, pending: str | None) -> str | None:
    """Return the quote still open after text, or None when it closes."""
    index = 0
    quote = pending
    if quote is None:
        stripped = text.lstrip()
        if not stripped or stripped[0] not in {'"', "'"}:
            return None
        quote = stripped[0]
        index = text.find(quote) + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == quote:
            return None
        index += 1
    return quote


def env_assigns_root_or_stable(text: str, stable: str) -> bool:
    """True when a validated name sets the checkout root or a value contains stable.

    Quoted continuations stay inside the value. This does not return file text.
    """
    pending: str | None = None
    for line in text.splitlines():
        if pending is not None:
            if stable and stable in line:
                return True
            pending = _quote_left_open(line, pending)
            continue
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        raw_name, value = line.split("=", 1)
        match = ENV_NAME_RE.fullmatch(raw_name)
        if match is not None and match.group(1) == "HERMES_FLEET_CONTROL_ROOT":
            return True
        if match is not None and stable and stable in value:
            return True
        pending = _quote_left_open(value, None)
    return False


def environment_file_entries(shown: dict[str, str]) -> list[tuple[str, bool]]:
    """Paths from EnvironmentFiles. A leading - marks a systemd optional file."""
    found: list[tuple[str, bool]] = []
    for token in shown.get("EnvironmentFiles", "").split():
        if token.startswith("(") and token.endswith(")"):
            continue
        optional = token.startswith("-")
        path = token[1:] if optional else token
        if not path.startswith("/"):
            continue
        found.append((path, optional))
    return found


def effective_unit_ok(shown: dict[str, str], stable: str) -> bool:
    """False when ExecStart, WorkingDirectory, or an EnvironmentFile pins the checkout.

    A missing optional EnvironmentFile is tolerated. A missing required file,
    a symlink, a path that contains the stable checkout, or a file that sets
    the checkout root is not.
    """
    for prop in ("ExecStart", "WorkingDirectory"):
        value = shown.get(prop, "")
        if stable and stable in value:
            return False
        if "HERMES_FLEET_CONTROL_ROOT=" in value:
            return False
    for file_name, optional in environment_file_entries(shown):
        if stable and stable in file_name:
            return False
        path = Path(file_name)
        if path.is_symlink():
            return False
        if not path.is_file():
            if optional:
                continue
            return False
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        if env_assigns_root_or_stable(text, stable):
            return False
    return True


def _unknown_step1(scope: str, facts: dict[str, str]) -> None:
    for key in (
        "running-root-is-stable",
        "delegation-loaded",
        "dropin-order",
        "retirement-absent",
        "fleet-env-file",
        "journals",
        "need-daemon-reload",
        "effective-unit",
        "delegation-location",
        "euid-root",
    ):
        facts[f"{scope}-{key}"] = "unknown"
        out(f"{scope}-{key}=unknown")


def _report_step1_readiness(scope: str, user: bool, facts: dict[str, str]) -> None:
    shown = systemctl_show(user)
    if shown is None or facts.get(f"{scope}-process") != "live":
        _unknown_step1(scope, facts)
        return
    try:
        pid = int(shown.get("MainPID", "0"))
    except ValueError:
        pid = 0
    env = read_environ(pid) if pid > 1 else None
    if env is None:
        _unknown_step1(scope, facts)
        return
    root = env.get("HERMES_FLEET_CONTROL_ROOT", "")
    matches = stable_dirs()
    stable = str(matches[0]) if len(matches) == 1 else ""
    names = dropin_names(shown)
    facts[f"{scope}-running-root-is-stable"] = "yes" if stable and root == stable else "no"
    facts[f"{scope}-delegation-loaded"] = "yes" if "fleet-delegation.conf" in names else "no"
    facts[f"{scope}-dropin-order"] = "ok" if dropin_order_ok(names) else "blocked"
    retirement_loaded = "fleet-retirement.conf" in names
    try:
        delegation = delegation_path(shown)
        retirement_file = delegation.with_name("fleet-retirement.conf").exists()
        facts[f"{scope}-delegation-location"] = delegation_location(delegation, user)
    except Stop:
        retirement_file = False
        facts[f"{scope}-delegation-location"] = "rejected"
    facts[f"{scope}-retirement-absent"] = "no" if retirement_loaded or retirement_file else "yes"
    fleet_env = Path(str(env.get("FLEET_CONTROL_ENV_FILE") or ""))
    if fleet_env.is_symlink() or not str(env.get("FLEET_CONTROL_ENV_FILE") or "").strip():
        facts[f"{scope}-fleet-env-file"] = "missing"
    elif fleet_env.is_file():
        facts[f"{scope}-fleet-env-file"] = "regular"
    else:
        facts[f"{scope}-fleet-env-file"] = "missing"
    try:
        journal_manifest(env)
        facts[f"{scope}-journals"] = "private-nonempty"
    except Stop:
        facts[f"{scope}-journals"] = "blocked"
    facts[f"{scope}-need-daemon-reload"] = "no" if shown.get("NeedDaemonReload") == "no" else "yes"
    facts[f"{scope}-effective-unit"] = "ok" if stable and effective_unit_ok(shown, stable) else "blocked"
    facts[f"{scope}-euid-root"] = "yes" if os.geteuid() == 0 else "no"
    for key in (
        "running-root-is-stable",
        "delegation-loaded",
        "dropin-order",
        "retirement-absent",
        "fleet-env-file",
        "journals",
        "need-daemon-reload",
        "effective-unit",
        "delegation-location",
        "euid-root",
    ):
        out(f"{scope}-{key}=" + facts[f"{scope}-{key}"])


def cmd_preflight() -> int:
    _self_check()
    facts: dict[str, str] = {}

    def fact(key: str, value: str) -> None:
        facts[key] = value
        out(f"{key}={value}")

    out("preflight=c08cb1e-control")
    out("read-only=yes")
    out("mcp-args-note=redacted-is-not-configuration-validation")
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
    guest_node = Path("/etc/pve").is_dir() and shutil.which("qm", path=FIXED_PATH) is not None
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
        fact("stable-tree-is-pinned", "yes" if tree == STABLE_TREE else "no")
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
        fact("stable-tree-is-pinned", "unknown")
        fact("origin-embedded-token", "unknown")
    out("new-checkout-exists=" + ("yes" if NEW.exists() else "no"))
    _report_provisioner(facts)
    _report_tools(facts)
    if facts["unit-scope"] in {"system", "user"}:
        _report_step1_readiness(facts["unit-scope"], facts["unit-scope"] == "user", facts)
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


def _exec_env_override(key: str) -> bool:
    """True for an env key that changes which code or binary runs.

    Names are exact and case-sensitive, plus any ``LD_`` prefix.
    ``FLEET_CONTROL_PYTHON`` and ``PATH`` are included because they
    select the interpreter or the command binary. The value is not read.
    """
    return key in EXEC_ENV_KEYS or key.startswith("LD_")


def _restart_policy_label(value: str) -> str:
    if value == "":
        return "empty"
    if _POLICY_RE.fullmatch(value):
        return value
    return "unreadable"


def _triggered_by_label(value: str) -> str:
    text = value.strip()
    if not text:
        return "none"
    names = text.split()
    if all(_UNIT_NAME_RE.fullmatch(name) for name in names):
        return ",".join(names)
    return "unreadable"


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
    out(f"{scope}-restart-policy=" + _restart_policy_label(shown.get("Restart", "")))
    out(f"{scope}-triggered-by=" + _triggered_by_label(shown.get("TriggeredBy", "")))
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
                args = classify_mcp_args(
                    server.get("args"),
                    command=server.get("command"),
                    cwd=server.get("cwd"),
                    root=root,
                )
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
    for name in names:
        code, text = _run(["systemctl", "show", "-p", "ActiveState", "--value", name])
        state = text.strip() if code == 0 else "unknown"
        out(f"provisioner-unit={name} active={state}")
    out("onboarding-dir=deferred-to-witness")
    out("tombstones-dir=deferred-to-witness")


def cmd_provisioner_witness() -> int:
    """Host mutation. Creates the witness directory (mode 0700) and, on
    the first run, witness.manifest and identity (mode 0600). Later runs
    still chmod the directory and compare those files. State bodies are
    not printed.
    """
    if os.geteuid() != 0:
        die("run this command as root on the Provisioner")
    if Path("/etc/pve").is_dir() and shutil.which("qm", path=FIXED_PATH):
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
        _private_write(manifest_path, manifest.encode())
        _private_write(identity_path, identity.encode())
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


def probe_lock(path: Path, kind: str) -> None:
    """Shared non-blocking probe. Do not follow a symlink or take an exclusive lock."""
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        die(kind + " journal lock is not a regular file")
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
    except BlockingIOError:
        die(kind + " journal lock is taken")
    finally:
        os.close(fd)


def journal_manifest(env: dict[str, str]) -> str:
    """Hash journal files. Does not print or return their bodies."""
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
            probe_lock(path, kind)
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


def require_python312() -> None:
    if python312_status() != "outside-venv":
        die("python3.12 is missing or inside the agent virtualenv")


def require_pins(repo: Path, head_pin: str, tree_pin: str) -> None:
    head = git_read(repo, "rev-parse", "HEAD")
    tree = git_read(repo, "rev-parse", "HEAD^{tree}")
    if head != head_pin or tree != tree_pin:
        die("checkout does not match the pins")


def git_exec(repo: Path, *args: str) -> tuple[int, str]:
    """Git with safe.directory set. Does not echo stdout."""
    return _run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "safe.directory=" + str(repo),
            "-c",
            "credential.helper=",
            "--no-optional-locks",
            *args,
        ]
    )


def assert_checkout_clean(repo: Path) -> None:
    """Allow only untracked runtime/ and fleet-mcp/node_modules/."""
    code, text = git_exec(repo, "status", "--porcelain=v1", "-uall")
    if code != 0:
        die("git status failed")
    for line in text.splitlines():
        if len(line) < 4 or line.startswith('"') or " -> " in line:
            die("git status line is unusable")
        path = line[3:]
        untracked = line.startswith("?? ")
        allowed = path.startswith("runtime/") or path.startswith("fleet-mcp/node_modules/")
        if not (untracked and allowed):
            die("checkout is not clean")


def recorded_scope(evidence: Path) -> tuple[str, bool]:
    file = evidence / "scope"
    if not file.is_file() or file.is_symlink():
        die("baseline scope is missing")
    text = file.read_text(encoding="utf-8").strip()
    if text == "system":
        return "system", False
    if text == "user":
        return "user", True
    die("baseline scope is unusable")


def stored_path(evidence: Path, name: str) -> Path:
    file = evidence / name
    if not file.is_file() or file.is_symlink():
        die("baseline is missing " + name)
    text = file.read_text(encoding="utf-8").strip()
    if not text.startswith("/") or SAFE_PATH_RE.fullmatch(text) is None:
        die(name + " is not a usable path")
    return Path(text)


def require_bytes(path: Path, expected: bytes, label: str, *, private: bool = False) -> None:
    if path.is_symlink() or not path.is_file():
        die(label + " is missing")
    if private and stat.S_IMODE(path.stat().st_mode) & 0o077:
        die(label + " is not private")
    if path.read_bytes() != expected:
        die(label + " changed")


def require_side_files(evidence: Path) -> None:
    """Profile env, fleet env, and the unit fragment still match step 1."""
    for label, copy, private in (
        ("profile.env.path", "profile.env", True),
        ("fleet.env.path", "fleet.env", False),
        ("unit.fragment.path", "unit.fragment", False),
    ):
        require_bytes(stored_path(evidence, label), (evidence / copy).read_bytes(), label, private=private)


def _require_owned_dir(path: Path, label: str) -> None:
    """Reject a symlink, a non-directory, a foreign owner, or group/world write.

    Uses lstat so a symlink is not followed. A mode of 0755 is accepted.
    Group-write and world-write bits are not.
    """
    try:
        info = os.lstat(path)
    except OSError:
        die(label + " is not lockable")
    if stat.S_ISLNK(info.st_mode):
        die(label + " is a symlink")
    if not stat.S_ISDIR(info.st_mode):
        die(label + " is not a directory")
    if info.st_uid != os.geteuid():
        die(label + " owner is not the deploying user")
    if stat.S_IMODE(info.st_mode) & 0o022:
        die(label + " is group or world writable")


def _lock_parent(create: bool) -> int:
    """Exclusive flock on the evidence parent. Wait is bounded.

    baseline may create the parent. Other commands stop when it is absent.
    The same lock covers baseline, configure, restart, verify, rollback,
    and confirm. The parent must be a directory this user owns, not a
    symlink, and not group or world writable. An existing unsafe parent
    is refused rather than chmod'd.
    """
    parent = evidence_root().parent
    missing = False
    try:
        os.lstat(parent)
    except FileNotFoundError:
        missing = True
    except OSError:
        die("evidence parent is not lockable")
    if missing:
        if not create:
            die("baseline is missing")
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            die("evidence parent is not lockable")
        os.chmod(parent, 0o700)
    _require_owned_dir(parent, "evidence parent")
    try:
        fd = os.open(str(parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        die("evidence parent is not lockable")
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            pass
        except OSError:
            os.close(fd)
            die("evidence parent is not lockable")
        if time.monotonic() >= deadline:
            os.close(fd)
            die("another deploy command holds the evidence lock; retry after it finishes")
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


def _require_evidence_dir() -> None:
    """When the evidence directory exists, it must be a private directory we own.

    Absence is left for the command. A symlink is refused before any write.
    """
    evidence = evidence_root()
    try:
        os.lstat(evidence)
    except FileNotFoundError:
        return
    except OSError:
        die("evidence directory is not lockable")
    _require_owned_dir(evidence, "evidence directory")


def _run_locked(body, *, create: bool = False) -> int:
    _require_evidence_dir()
    lock = _lock_parent(create)
    try:
        _require_evidence_dir()
        return body()
    finally:
        os.close(lock)


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def rehash_recorded(recorded: str) -> str:
    """Re-hash the files named in a manifest. Does not need a live process."""
    if not recorded.endswith("\n"):
        die("journal manifest is unusable")
    lines: list[str] = []
    for line in recorded.splitlines():
        parts = line.split(" ", 2)
        if len(parts) != 3:
            die("journal manifest is unusable")
        path = Path(parts[2])
        if path.is_symlink() or not path.is_file():
            die("journal file is missing")
        lines.append(manifest_line(path))
    return "\n".join(lines) + "\n"


def journal_difference(env: dict[str, str] | None, recorded: str) -> str:
    """none, none-recorded-files-only, changed, or unreadable.

    A live environment is re-listed. Without one, only paths already named
    in the manifest are rehashed, so a new journal file is not detected.
    Swallows the integrity stop so rollback can warn.
    """
    sink = sys.stderr
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
    try:
        try:
            current = journal_manifest(env) if env is not None else rehash_recorded(recorded)
        except (Stop, OSError):
            return "unreadable"
    finally:
        sys.stderr.close()
        sys.stderr = sink
    if current != recorded:
        return "changed"
    if env is None:
        return "none-recorded-files-only"
    return "none"


def warn_journals(kind: str, *, action: str = "rollback") -> None:
    if kind == "none-recorded-files-only":
        warn(
            "recorded journal files were rehashed only; new journal files were not "
            "scanned and journals will not be modified"
        )
    elif kind != "none":
        warn("journal manifest changed; " + action + " will not modify journals")
    out("journal-warning=" + kind)


def gateway_before_pid(shown: dict[str, str]) -> int:
    """MainPID of an active running unit, otherwise 0."""
    if shown.get("ActiveState") != "active" or shown.get("SubState") != "running":
        return 0
    try:
        pid = int(shown.get("MainPID", "0"))
    except ValueError:
        return 0
    if pid <= 1:
        return 0
    return pid


def restart_held(first: dict[str, str], second: dict[str, str], first_pid: int) -> list[str]:
    """The process is still the one observed just after restart."""
    blockers: list[str] = []
    if second.get("ActiveState") != "active" or second.get("SubState") != "running":
        blockers.append("settled-state")
    try:
        pid = int(second.get("MainPID", "0"))
    except ValueError:
        pid = 0
    if pid != first_pid or pid <= 1:
        blockers.append("settled-pid")
    if second.get("NRestarts") != first.get("NRestarts"):
        blockers.append("settled-nrestarts")
    return blockers


def _daemon_reload(user: bool) -> None:
    argv = ["systemctl", "--user", "daemon-reload"] if user else ["systemctl", "daemon-reload"]
    if _run(argv)[0] != 0:
        die("daemon-reload failed")


def _same_scope(evidence: Path) -> tuple[str, bool]:
    recorded, user = recorded_scope(evidence)
    scope, selected_user = selected_scope()
    if scope != recorded or selected_user != user:
        die("unit scope changed")
    return recorded, user


def cmd_install() -> int:
    """Create the new checkout. Never copy a credential-bearing origin."""
    matches = stable_dirs()
    if len(matches) != 1:
        die("stable checkout is not exactly one directory")
    stable = matches[0]
    require_python312()
    require_pins(stable, STABLE_SHA, STABLE_TREE)
    origin = git_read(stable, "remote", "get-url", "origin")
    if origin is None:
        die("stable origin is unreadable")
    if NEW.exists() and not (NEW / ".git").is_dir():
        die("new path exists and is not a git directory")
    OPT.mkdir(parents=True, exist_ok=True)
    if not (NEW / ".git").exists():
        code, _text = _run(["git", "-c", "safe.directory=" + str(NEW), "init", "--quiet", str(NEW)])
        if code != 0:
            die("git init failed")
    existing = git_read(NEW, "remote", "get-url", "origin")
    if existing is None:
        def add_remote(url: str) -> None:
            code, _text = git_exec(NEW, "remote", "add", "origin", url)
            if code != 0:
                die("git remote add failed")

        bind_origin(origin, add_remote)
    else:
        for line in report_origin_decision(existing):
            out(line)
        if origin_credential(existing) != "absent":
            die("new checkout origin has an embedded credential or an unknown form")
    code, _text = git_exec(NEW, "fetch", "--quiet", "--no-tags", "origin", SHA)
    if code != 0:
        die("git fetch failed")
    code, _text = git_exec(NEW, "checkout", "--quiet", "--detach", SHA)
    if code != 0:
        die("git checkout failed")
    require_pins(NEW, SHA, TREE)
    _ensure_runtime()
    assert_checkout_clean(NEW)
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
    """Create a 0600 file without a world-readable window. Refuse a symlink."""
    if path.is_symlink():
        die("refusing to write through a symlink")
    if path.exists():
        if path.read_bytes() != data:
            die("evidence file changed")
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            os.chmod(path, 0o600)
        return
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        _write_all(fd, data)
        os.fsync(fd)
    except Exception:
        os.close(fd)
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    os.close(fd)


def _baseline_names_present(evidence: Path, names: set[str]) -> bool:
    manifest = evidence / "journals.manifest"
    try:
        if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size == 0:
            return False
    except OSError:
        return False
    for name in names:
        path = evidence / name
        if path.is_symlink() or not path.is_file():
            return False
    return True


def _unexpected_child(directory: Path, names: set[str]) -> bool:
    for child in directory.iterdir():
        if child.name not in names:
            return True
    return False


def _save_baseline(evidence: Path, files: dict[str, bytes]) -> str:
    """Stage every evidence file, then rename the directory into place.

    A directory is complete only when it is not a symlink and every required
    file, including a non-empty journals.manifest, is a regular file. A
    partial directory of known names is discarded and rewritten. An unexpected
    name is left in place and stops the command. Journals live outside this
    directory and are not deleted.
    """
    if "journals.manifest" not in files or not files["journals.manifest"]:
        die("baseline is missing journals.manifest")
    if evidence.is_symlink():
        die("baseline is not a directory")
    names = set(files)
    if evidence.exists():
        if not evidence.is_dir():
            die("baseline is not a directory")
        if _unexpected_child(evidence, names):
            die("unexpected baseline file")
        if _baseline_names_present(evidence, names):
            for name, data in files.items():
                if (evidence / name).read_bytes() != data:
                    die("baseline changed")
            return "matched"
        shutil.rmtree(evidence)
    parent = evidence.parent
    if parent.is_symlink() or not parent.is_dir():
        die("evidence directory is not lockable")
    staging = parent / (evidence.name + ".staging")
    if staging.exists():
        if staging.is_symlink() or not staging.is_dir() or _unexpected_child(staging, names):
            die("baseline staging is unusable")
        shutil.rmtree(staging)
    try:
        staging.mkdir(mode=0o700)
        os.chmod(staging, 0o700)
        ordered = [name for name in files if name != "journals.manifest"]
        ordered.append("journals.manifest")
        for name in ordered:
            _private_write(staging / name, files[name])
        _fsync_dir(staging)
        os.rename(staging, evidence)
        os.chmod(evidence, 0o700)
        _fsync_dir(parent)
    except Exception:
        if staging.is_dir() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise
    return "created"


def env_key_report(text: str) -> list[str]:
    """Safe fleet-env lines. Names and values from the file are not included.

    The count and sha256 cover validated assignment names only. A quoted
    value that does not close on its line makes every following line
    unparsed until the closing quote. Required keys are reported as
    present or absent.
    """
    names: list[str] = []
    unparsed = 0
    pending: str | None = None
    for line in text.splitlines():
        if pending is not None:
            unparsed += 1
            pending = _quote_left_open(line, pending)
            continue
        if not line or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            unparsed += 1
            continue
        raw_name, value = line.split("=", 1)
        match = ENV_NAME_RE.fullmatch(raw_name)
        if match is None:
            unparsed += 1
        else:
            names.append(match.group(1))
        pending = _quote_left_open(value, None)
    payload = "".join(name + "\n" for name in sorted(set(names)))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    found = set(names)
    lines = [
        "fleet-env-name-count=" + str(len(names)),
        "fleet-env-names-sha256=" + digest,
        "fleet-env-unparsed-lines=" + str(unparsed),
    ]
    for key in REQUIRED_ENV_KEYS:
        lines.append(key + "=" + ("present" if key in found else "absent"))
    return lines


def cmd_baseline() -> int:
    """Write the evidence baseline once. Does not restart or create the checkout."""
    return _run_locked(_cmd_baseline_locked, create=True)


def _cmd_baseline_locked() -> int:
    """Write the evidence baseline once. Does not restart or create the checkout.

    Valid only before fleet-retirement.conf exists. A later re-run stops
    rather than recording a baseline that already includes that drop-in.
    """
    require_python312()
    _scope, user = selected_scope()
    if _scope == "system" and os.geteuid() != 0:
        die("system unit baseline must run as root")
    shown, env, pid = _live_gateway(user)
    if str(env.get("FLEET_CONTROL_PYTHON", "")).strip():
        die("FLEET_CONTROL_PYTHON is set")
    if env.get("HERMES_FLEET_CONTROL_INTEGRATION") != "1":
        die("HERMES_FLEET_CONTROL_INTEGRATION is not 1")
    if shown.get("NeedDaemonReload") != "no":
        die("daemon reload is pending")
    matches = stable_dirs()
    if len(matches) != 1:
        die("stable checkout is not exactly one directory")
    stable = matches[0]
    require_pins(stable, STABLE_SHA, STABLE_TREE)
    root = env.get("HERMES_FLEET_CONTROL_ROOT", "")
    if root != str(stable):
        die("running root is not the stable checkout")
    names = dropin_names(shown)
    delegation = delegation_path(shown)
    if delegation.is_symlink() or not delegation.is_file():
        die("fleet-delegation.conf is not loaded")
    if delegation_location(delegation, user) == "rejected":
        die("delegation drop-in is outside the config directory")
    if not dropin_order_ok(names):
        die("a drop-in sorts after fleet-retirement.conf")
    retirement = delegation.with_name("fleet-retirement.conf")
    if "fleet-retirement.conf" in names or retirement.is_symlink() or retirement.exists():
        die("fleet-retirement.conf is already present")
    if not effective_unit_ok(shown, str(stable)):
        die("effective unit references the stable checkout or sets the root")
    manifest = journal_manifest(env)
    profile = env.get(PROFILE_KEY, "")
    profiles = env.get(PROFILES_ROOT_KEY) or PROFILES_ROOT_DEFAULT
    config = Path(profiles) / profile / "config.yaml"
    profile_env = Path(profiles) / profile / ".env"
    fleet_env = Path(str(env.get("FLEET_CONTROL_ENV_FILE") or ""))
    fragment = Path(shown["FragmentPath"])
    for path in (config, profile_env, fleet_env, fragment, delegation):
        if path.is_symlink() or not path.is_file():
            die("baseline input is missing")
    if stat.S_IMODE(profile_env.stat().st_mode) & 0o077:
        die("profile.env.path is not private")
    for label, path in (
        ("config.path", config),
        ("profile.env.path", profile_env),
        ("fleet.env.path", fleet_env),
        ("unit.fragment.path", fragment),
        ("delegation.path", delegation),
    ):
        if SAFE_PATH_RE.fullmatch(str(path)) is None:
            die(label + " is not a usable path")
    env_lines = env_key_report(fleet_env.read_text(encoding="utf-8", errors="replace"))
    server_name = env.get("HERMES_FLEET_MCP_SERVER", "").strip()
    config_bytes = config.read_bytes()
    try:
        config_text = config_bytes.decode("utf-8")
    except UnicodeDecodeError:
        die("baseline fleet mcp is not stable-compatible")
    verdict = fleet_mcp_compatibility(config_text, str(stable), server_name)
    if verdict != "compatible":
        out("config-mcp=not-stable-compatible")
        out("config-mcp-detail=" + verdict)
        die("baseline fleet mcp is not stable-compatible")
    files = {
        "journals.manifest": manifest.encode(),
        "fleet-delegation.conf": delegation.read_bytes(),
        "config.yaml": config_bytes,
        "mcp-server.name": (server_name + "\n").encode(),
        "config.mcp-identity": (_mcp_identity_line(server_name, config_bytes) + "\n").encode(),
        "config.mode": str(stat.S_IMODE(config.stat().st_mode)).encode(),
        "fleet.env": fleet_env.read_bytes(),
        "profile.env": profile_env.read_bytes(),
        "unit.fragment": fragment.read_bytes(),
        "mainpid": str(pid).encode(),
        "stable_dir": (str(stable) + "\n").encode(),
        "scope": (_scope + "\n").encode(),
        "config.path": (str(config) + "\n").encode(),
        "profile.env.path": (str(profile_env) + "\n").encode(),
        "fleet.env.path": (str(fleet_env) + "\n").encode(),
        "unit.fragment.path": (str(fragment) + "\n").encode(),
        "delegation.path": (str(delegation) + "\n").encode(),
    }
    status = _save_baseline(evidence_root(), files)
    out(f"scope={_scope}")
    out(f"ActiveState={shown['ActiveState']}")
    out(f"SubState={shown['SubState']}")
    out(f"MainPID={pid}")
    out("restart-policy=" + _restart_policy_label(shown.get("Restart", "")))
    out("triggered-by=" + _triggered_by_label(shown.get("TriggeredBy", "")))
    out("NRestarts=" + shown["NRestarts"])
    out("nrestarts-measures=" + NRESTARTS_MEASURES)
    out("dropins=" + ",".join(names))
    for line in env_lines:
        out(line)
    out("FLEET_CONTROL_PYTHON=absent")
    out("journal-manifest=sha256:" + hashlib.sha256(manifest.encode()).hexdigest())
    out("stable=" + str(stable))
    out("running-root=" + root)
    out("baseline=" + status)
    out("STEP 1 OK")
    return 0


def _require_manifest(env: dict[str, str]) -> None:
    recorded_path = evidence_root() / "journals.manifest"
    if not recorded_path.is_file() or recorded_path.is_symlink():
        die("baseline is missing")
    recorded = recorded_path.read_text(encoding="utf-8")
    if journal_manifest(env) != recorded:
        die("journal manifest changed")


def _configure_locked(evidence: Path) -> int:
    _recorded, user = _same_scope(evidence)
    shown, env, _pid = _live_gateway(user)
    if str(env.get("FLEET_CONTROL_PYTHON", "")).strip():
        die("FLEET_CONTROL_PYTHON is set")
    if shown.get("NeedDaemonReload") != "no":
        die("daemon reload is pending")
    _require_manifest(env)
    require_side_files(evidence)
    stable = (evidence / "stable_dir").read_text(encoding="utf-8").strip()
    if env.get("HERMES_FLEET_CONTROL_ROOT") != stable:
        die("running root is not the stable checkout")
    if not dropin_order_ok(dropin_names(shown)):
        die("a drop-in sorts after fleet-retirement.conf")
    delegation = delegation_path(shown)
    if delegation != stored_path(evidence, "delegation.path"):
        die("fleet-delegation.conf path changed")
    if delegation.is_symlink() or not delegation.is_file():
        die("fleet-delegation.conf is not loaded")
    if delegation_location(delegation, user) == "rejected":
        die("delegation drop-in is outside the config directory")
    if delegation.read_bytes() != (evidence / "fleet-delegation.conf").read_bytes():
        die("fleet-delegation.conf changed")
    if not effective_unit_ok(shown, stable):
        die("effective unit references the stable checkout or sets the root")
    config = stored_path(evidence, "config.path")
    if config.is_symlink() or not config.is_file():
        die("config.yaml is missing")
    server_name = _recorded_server_name(evidence)
    if server_name is None:
        die("fleet mcp server name is missing")
    if env.get("HERMES_FLEET_MCP_SERVER", "").strip() != server_name:
        die("fleet mcp server name changed")
    try:
        baseline_bytes = (evidence / "config.yaml").read_bytes()
        baseline_text = baseline_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        die("baseline fleet mcp identity does not match")
    if not _baseline_identity_matches(evidence, baseline_bytes):
        die("baseline fleet mcp identity does not match")
    baseline_verdict = fleet_mcp_compatibility(baseline_text, stable, server_name)
    if baseline_verdict != "compatible":
        out("config-mcp=not-stable-compatible")
        out("config-mcp-detail=" + baseline_verdict)
        die("baseline fleet mcp is not stable-compatible")
    dropin, status, updated = apply_configure(
        delegation.read_text(encoding="utf-8"),
        config.read_text(encoding="utf-8"),
        stable,
        str(NEW),
        server_name,
    )
    dest = delegation.with_name("fleet-retirement.conf")
    if dest.is_symlink():
        die("fleet-retirement.conf is a symlink")
    if dest.exists() and dest.read_text(encoding="utf-8") != dropin:
        die("fleet-retirement.conf bytes differ")
    baseline_text = (evidence / "config.yaml").read_text(encoding="utf-8")
    live_text = config.read_text(encoding="utf-8")
    if status == "rewritten":
        if live_text not in {baseline_text, updated}:
            die("config.yaml is neither the baseline nor the rewritten bytes")
    elif live_text != updated:
        die("config.yaml bytes differ")
    _private_write(evidence / "fleet-retirement.conf.desired", dropin.encode())
    _private_write(evidence / "config.yaml.deployed", updated.encode())
    _private_write(evidence / "config.status", status.encode())
    if not dest.exists():
        atomic_replace(dest, dropin.encode(), mode=0o644)
    if status == "rewritten" and config.read_text(encoding="utf-8") != updated:
        atomic_replace(config, updated.encode())
    out("config=" + status)
    out("config.changed=" + ("yes" if status == "rewritten" else "no"))
    out("STEP 5 OK")
    return 0


def cmd_configure() -> int:
    """Write the rollback record, then edit the drop-in and config.yaml."""
    return _run_locked(_cmd_configure_locked)


def _cmd_configure_locked() -> int:
    evidence = evidence_root()
    if not (evidence / "journals.manifest").is_file():
        die("baseline is missing")
    return _configure_locked(evidence)


def _restart(
    user: bool,
    before_pid: int,
    expected_root: str,
    expect_retirement: bool,
    *,
    check_journals: bool = True,
) -> None:
    _daemon_reload(user)
    argv_prefix = ["systemctl", "--user"] if user else ["systemctl"]
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
    time.sleep(RESTART_SETTLE_SECONDS)
    settled = systemctl_show(user)
    if settled is None:
        die("gateway show failed")
    held = restart_held(shown, settled, pid)
    if held:
        die("restart did not stay up (" + ",".join(held) + ")")
    settled_env = read_environ(pid)
    if settled_env is None or settled_env.get("HERMES_FLEET_CONTROL_ROOT") != expected_root:
        die("running root changed during settle")
    if settled.get("NeedDaemonReload") != "no":
        die("daemon reload still needed")
    if check_journals:
        _require_manifest(settled_env)


def cmd_restart() -> int:
    return _run_locked(_cmd_restart_locked)


def _cmd_restart_locked() -> int:
    evidence = evidence_root()
    _recorded, user = _same_scope(evidence)
    shown, env, pid = _live_gateway(user)
    _require_manifest(env)
    require_side_files(evidence)
    stable = (evidence / "stable_dir").read_text(encoding="utf-8").strip()
    if not effective_unit_ok(shown, stable):
        die("effective unit references the stable checkout or sets the root")
    desired = evidence / "fleet-retirement.conf.desired"
    if not desired.is_file():
        die("desired drop-in is missing")
    root = env.get("HERMES_FLEET_CONTROL_ROOT", "")
    loaded = dropin_names(shown)
    if root == str(NEW) and "fleet-retirement.conf" in loaded:
        out("restart=skipped")
        out("STEP 6 OK")
        return 0
    if root != stable:
        die("running root is neither stable nor the new checkout")
    _restart(user, pid, str(NEW), True)
    out("restart=done")
    out("STEP 6 OK")
    return 0


def cmd_verify() -> int:
    return _run_locked(_cmd_verify_locked)


def _cmd_verify_locked() -> int:
    evidence = evidence_root()
    _recorded, user = _same_scope(evidence)
    shown, env, _pid = _live_gateway(user)
    if shown.get("NeedDaemonReload") != "no":
        die("daemon reload is pending")
    if env.get("HERMES_FLEET_CONTROL_ROOT") != str(NEW):
        die("running root is not the new checkout")
    _require_manifest(env)
    require_side_files(evidence)
    require_pins(NEW, SHA, TREE)
    assert_checkout_clean(NEW)
    stable = (evidence / "stable_dir").read_text(encoding="utf-8").strip()
    if not effective_unit_ok(shown, stable):
        die("effective unit references the stable checkout or sets the root")
    status_file = evidence / "config.status"
    deployed_file = evidence / "config.yaml.deployed"
    if not status_file.is_file() or not deployed_file.is_file():
        die("deployed config record is missing")
    status = status_file.read_text(encoding="utf-8").strip()
    config = stored_path(evidence, "config.path")
    if config.is_symlink() or not config.is_file():
        die("config.yaml is missing")
    text = config.read_text(encoding="utf-8")
    if status != "interpolated" and stable in text:
        die("config still names the stable checkout")
    if config.read_bytes() != deployed_file.read_bytes():
        die("config.yaml is not the deployed bytes")
    out("STEP 7 OK")
    return 0


def _side_labels(evidence: Path) -> list[str]:
    """Labels whose live bytes differ. Does not write those files."""
    labels: list[str] = []
    for label, copy, private in (
        ("profile.env.path", "profile.env", True),
        ("fleet.env.path", "fleet.env", False),
        ("unit.fragment.path", "unit.fragment", False),
    ):
        path = stored_path(evidence, label)
        expected = (evidence / copy).read_bytes()
        drifted = path.is_symlink() or not path.is_file() or path.read_bytes() != expected
        if not drifted and private and stat.S_IMODE(path.stat().st_mode) & 0o077:
            drifted = True
        if drifted:
            labels.append(label)
    return labels


def warn_side_files(labels: list[str], *, action: str) -> None:
    if labels:
        warn("side file differs from baseline; " + action + " will not modify it")
    out("side-file-drift=" + (",".join(labels) if labels else "none"))


def _delegation_changed(evidence: Path, delegation: Path) -> bool:
    recorded = evidence / "fleet-delegation.conf"
    if delegation.is_symlink() or not delegation.is_file() or recorded.is_symlink() or not recorded.is_file():
        return True
    return delegation.read_bytes() != recorded.read_bytes()


def _reverse_fleet_paths(live: bytes, stable_dir: str, server_name: str) -> bytes | None:
    """Swap the new checkout back to stable inside the named fleet MCP entry.

    Returns None when that swap is not safe. Does not print file text.
    The entry is the recorded server name. Another server is not rewritten
    because it mentions a checkout path.
    """
    try:
        text = live.decode("utf-8")
    except UnicodeDecodeError:
        return None
    new = str(NEW)
    if new not in text:
        return None
    sink = sys.stderr
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
    try:
        try:
            updated, _status = rewrite_config(text, new, stable_dir, server_name)
        except Exception:
            return None
    finally:
        sys.stderr.close()
        sys.stderr = sink
    if new in updated:
        return None
    return updated.encode("utf-8")


def _normalize_abs(value: str) -> str:
    """Collapse slashes and '.' / '..' without touching the filesystem.

    Leading '//' is collapsed too. Symlinks are not resolved, so a path
    that does not exist is judged by its spelling.
    """
    return os.path.normpath(re.sub(r"/+", "/", value))


def _stable_anchor(stable_dir: str) -> str | None:
    if not stable_dir.startswith("/"):
        return None
    anchor = _normalize_abs(stable_dir)
    if ".." in anchor.split("/"):
        return None
    if not anchor.startswith("/opt/hermes-fleet-control/"):
        return None
    if anchor == str(NEW) or anchor.startswith(str(NEW) + "/"):
        return None
    return anchor


def _path_tokens(value: str) -> list[str]:
    return [match.group(0) for match in re.finditer(r"/[A-Za-z0-9._/-]*", value)]


def _checkout_kind(value: str, stable_dir: str) -> str | None:
    """stable, new, or other when a token names a fleet checkout. None otherwise."""
    kind = "stable" if FLEET_ROOT_VAR in value else None
    for token in _path_tokens(value):
        normalized = _normalize_abs(token)
        if normalized == str(NEW) or normalized.startswith(str(NEW) + "/"):
            return "new"
        if normalized == "/opt/hermes-fleet-control" or normalized.startswith("/opt/hermes-fleet-control/"):
            if normalized == stable_dir or normalized.startswith(stable_dir + "/"):
                kind = "stable"
                continue
            return "other"
    return kind


def _text_checkout_problem(text: str, stable_dir: str) -> str | None:
    """foreign-checkout or non-canonical-new. Stable paths and the variable are allowed.

    A token is canonical when its spelling already starts with the new
    checkout. A different spelling that normalizes to that checkout,
    including '/opt/./', a repeated slash, or a leading '//', is
    non-canonical-new. The substring check is not used for that case:
    '//opt/...' contains the canonical path as a suffix.
    """
    canonical = False
    noncanonical = False
    other = False
    for token in _path_tokens(text):
        normalized = _normalize_abs(token)
        if normalized == stable_dir or normalized.startswith(stable_dir + "/"):
            continue
        new_hit = normalized == str(NEW) or normalized.startswith(str(NEW) + "/")
        if new_hit:
            if token == str(NEW) or token.startswith(str(NEW) + "/"):
                canonical = True
            else:
                noncanonical = True
            continue
        if normalized == "/opt/hermes-fleet-control" or normalized.startswith("/opt/hermes-fleet-control/"):
            other = True
    if canonical or other:
        return "foreign-checkout"
    if noncanonical:
        return "non-canonical-new"
    if str(NEW) in text:
        return "foreign-checkout"
    return None


def _variable_anchored(value: str) -> bool:
    if value == FLEET_ROOT_VAR:
        return True
    prefix = FLEET_ROOT_VAR + "/"
    if not value.startswith(prefix):
        return False
    parts = [part for part in value[len(prefix) :].split("/") if part != "."]
    if not parts or any(part in {"", ".."} for part in parts):
        return False
    return True


def _anchored(value: str, stable_dir: str) -> bool:
    """True when value is the stable checkout, the checkout variable, or a child of either."""
    if not value:
        return False
    if FLEET_ROOT_VAR in value:
        return _variable_anchored(value) and _checkout_kind(value, stable_dir) == "stable"
    if not value.startswith("/"):
        return False
    normalized = _normalize_abs(value)
    return normalized == stable_dir or normalized.startswith(stable_dir + "/")


def _command_ok(command: str, stable_dir: str) -> bool:
    if command in PUBLIC_MCP or _anchored(command, stable_dir):
        return True
    if command.startswith("/"):
        return _normalize_abs(command) in ALLOWED_ABSOLUTE
    return False


def _arg_ok(arg: str, stable_dir: str) -> bool:
    """Allow only the documented fleet MCP argument shapes.

    Anchored checkout paths, the interpreter allowlist, ``node`` / ``npm`` /
    ``python3`` / ``python3.12``, ``--version``, ``--stdio``, and a relative
    script basename. Flags such as ``-e``, ``--eval``, ``-p``, ``--print``,
    ``--require``, ``-r``, ``-c``, and ``-m`` are not in that set.
    """
    if not arg:
        return False
    if arg.startswith("-"):
        return arg in ALLOWED_FLAGS
    if _anchored(arg, stable_dir):
        return True
    if arg.startswith("/"):
        return _normalize_abs(arg) in ALLOWED_ABSOLUTE
    if arg in PUBLIC_MCP:
        return True
    return RELATIVE_SCRIPT_RE.fullmatch(arg) is not None and "/" not in arg and ".." not in arg


def _validate_fleet_server(server: dict, stable_dir: str) -> str:
    """Strict shape for the one fleet entry. Unrelated servers are not passed here."""
    command = server.get("command")
    cwd = server.get("cwd")
    if not isinstance(command, str) or not isinstance(cwd, str):
        return "fleet-entry-malformed"
    if not _anchored(cwd, stable_dir):
        return "cwd-not-anchored"
    if not _command_ok(command, stable_dir):
        return "command-not-allowed"
    args = server.get("args", [])
    if args is None:
        args = []
    if not isinstance(args, list):
        return "fleet-entry-malformed"
    for item in args:
        if not isinstance(item, str):
            return "fleet-entry-malformed"
        if not _arg_ok(item, stable_dir):
            return "arg-not-allowed"
    env = server.get("env")
    if env is None:
        return "compatible"
    if not isinstance(env, dict):
        return "fleet-entry-malformed"
    for key, value in env.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return "fleet-entry-malformed"
        if key == "HERMES_FLEET_CONTROL_ROOT":
            return "env-overrides-root"
        if _exec_env_override(key):
            return "env-exec-override"
        kind = _checkout_kind(value, stable_dir)
        if kind is None:
            continue
        if kind == "stable" and _anchored(value, stable_dir):
            continue
        return "env-names-checkout"
    return "compatible"


def fleet_mcp_compatibility(text: str, stable_dir: str, server_name: str) -> str:
    """Shared stable-MCP verdict for baseline, rollback, and confirm.

    Returns 'compatible' or a short token. The token is not file text and
    not a secret. The fleet entry is the server named by server_name.
    Another server is not selected because it mentions the stable checkout.
    Unrelated servers may mention stable paths. The named entry is strict.
    A non-string field on that entry is malformed. An execution-changing
    env key is env-exec-override and its value is not printed. The whole text is still
    rejected when it names the new checkout or another checkout. Paths are
    normalized without resolving symlinks.
    """
    anchor = _stable_anchor(stable_dir)
    if anchor is None:
        return "stable-dir-unusable"
    if NAME_RE.fullmatch(server_name or "") is None:
        return "fleet-server-name-missing"
    problem = _text_checkout_problem(text, anchor)
    if problem is not None:
        return problem
    try:
        import yaml
    except ImportError:
        return "yaml-unavailable"
    try:
        data = yaml.safe_load(text)
    except Exception:
        return "yaml-unparsed"
    if not isinstance(data, dict):
        return "yaml-unparsed"
    servers = data.get("mcp_servers")
    if not isinstance(servers, dict):
        return "fleet-entry-missing"
    if server_name not in servers:
        return "fleet-entry-missing"
    server = servers[server_name]
    if not isinstance(server, dict):
        return "fleet-entry-malformed"
    return _validate_fleet_server(server, anchor)


def _recorded_server_name(evidence: Path) -> str | None:
    path = evidence / "mcp-server.name"
    try:
        info = os.lstat(path)
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if NAME_RE.fullmatch(text) is None:
        return None
    return text


def _mcp_identity_line(server_name: str, config_bytes: bytes) -> str:
    """Identity bound to the recorded server name and the config bytes.

    An older line of ``compatible`` plus only the sha256 does not match.
    """
    return "compatible " + server_name + " " + hashlib.sha256(config_bytes).hexdigest()


def _baseline_identity_matches(evidence: Path, config_bytes: bytes) -> bool:
    """True when config bytes are the baseline step 1 marked compatible."""
    path = evidence / "config.mcp-identity"
    server_name = _recorded_server_name(evidence)
    if server_name is None:
        return False
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return False
    try:
        recorded = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return False
    return recorded == _mcp_identity_line(server_name, config_bytes)


def _config_plan(evidence: Path, config: Path, stable_dir: str) -> tuple[str, bytes | None, str]:
    """unchanged, restored, reversed, preserved, or incomplete. Does not write.

    The third value is a non-secret detail. preserved means the live file
    is not the baseline but fleet_mcp_compatibility says it already targets
    the stable checkout. The bytes to write are returned only for restored
    and reversed.
    """
    baseline_file = evidence / "config.yaml"
    if baseline_file.is_symlink() or not baseline_file.is_file():
        return "incomplete", None, "baseline-missing"
    baseline = baseline_file.read_bytes()
    deployed_file = evidence / "config.yaml.deployed"
    deployed = deployed_file.read_bytes() if deployed_file.is_file() and not deployed_file.is_symlink() else None
    try:
        info = os.lstat(config)
    except OSError:
        return "incomplete", None, "config-unreadable"
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return "incomplete", None, "config-unreadable"
    try:
        live = config.read_bytes()
    except OSError:
        return "incomplete", None, "config-unreadable"
    server_name = _recorded_server_name(evidence)
    if server_name is None:
        return "incomplete", None, "fleet-server-name-missing"
    verified = _baseline_identity_matches(evidence, baseline)
    if live == baseline and str(NEW).encode() not in live and verified:
        return "unchanged", None, "byte-match"
    if deployed is not None and live == deployed and str(NEW).encode() not in baseline and verified:
        return "restored", baseline, "byte-match"
    reversed_bytes = _reverse_fleet_paths(live, stable_dir, server_name)
    if reversed_bytes is not None and str(NEW).encode() not in reversed_bytes:
        try:
            reversed_text = reversed_bytes.decode("utf-8")
        except UnicodeDecodeError:
            reversed_text = ""
        if reversed_text and fleet_mcp_compatibility(reversed_text, stable_dir, server_name) == "compatible":
            return "reversed", reversed_bytes, "compatible"
    try:
        text = live.decode("utf-8")
    except UnicodeDecodeError:
        return "incomplete", None, "not-utf8"
    verdict = fleet_mcp_compatibility(text, stable_dir, server_name)
    if verdict == "compatible":
        return "preserved", None, "compatible"
    return "incomplete", None, verdict


def _dropin_plan(evidence: Path, delegation: Path) -> str:
    """absent, removable, or unverified. Does not unlink or print."""
    dropin = delegation.with_name("fleet-retirement.conf")
    try:
        info = os.lstat(dropin)
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unverified"
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return "unverified"
    desired_file = evidence / "fleet-retirement.conf.desired"
    try:
        desired_info = os.lstat(desired_file)
    except OSError:
        return "unverified"
    if stat.S_ISLNK(desired_info.st_mode) or not stat.S_ISREG(desired_info.st_mode):
        return "unverified"
    try:
        if dropin.read_bytes() != desired_file.read_bytes():
            return "unverified"
    except OSError:
        return "unverified"
    return "removable"


def _apply_config(evidence: Path, config: Path, status: str, payload: bytes | None) -> None:
    if status == "restored":
        if payload is None:
            die("config restore has no payload")
        atomic_replace(config, payload)
        os.chmod(config, int((evidence / "config.mode").read_text(encoding="utf-8").strip()))
        return
    if status == "reversed":
        if payload is None:
            die("config reverse has no payload")
        atomic_replace(config, payload)
        return
    if status == "preserved":
        warn("config.yaml is not the baseline; the fleet MCP entry already targets the stable checkout")


def _apply_dropin_removal(evidence: Path, delegation: Path) -> None:
    """Copy a verified regular drop-in into evidence, then unlink it. Do not follow a symlink."""
    dropin = delegation.with_name("fleet-retirement.conf")
    try:
        info = os.lstat(dropin)
    except OSError:
        die("retirement drop-in changed")
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        die("retirement drop-in changed")
    fd = os.open(str(dropin), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining > 0:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
    finally:
        os.close(fd)
    desired = _desired_dropin_bytes(evidence)
    if desired is None or data != desired:
        die("retirement drop-in changed")
    _private_write(evidence / "fleet-retirement.conf.removed", data)
    os.unlink(dropin)


def _config_names_new(config: Path) -> bool:
    if config.is_symlink() or not config.is_file():
        return True
    try:
        text = config.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True
    return str(NEW) in text


def _config_names_label(config: Path) -> str:
    """yes, no, or unknown. Does not print file text."""
    try:
        info = os.lstat(config)
    except OSError:
        return "unknown"
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return "unknown"
    try:
        text = config.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "unknown"
    return "yes" if str(NEW) in text else "no"


def _running_root(before: int, env: dict[str, str] | None, stable: str) -> str:
    """new, stable, none, or unknown. none means no running gateway process."""
    if before <= 1 or env is None:
        return "none"
    return _classify_root(env.get("HERMES_FLEET_CONTROL_ROOT", ""), stable)


def _classify_root(root: str, stable: str) -> str:
    """new, stable, or unknown. Does not print the path."""
    if root == str(NEW):
        return "new"
    if root == stable:
        return "stable"
    return "unknown"


def _live_root_label(shown: dict[str, str], stable: str) -> str:
    """Root of a unit that did not stay stopped. Does not stop or start it.

    none means there is no main process. unknown means a main process
    exists but its root cannot be classified. The path is not printed.
    """
    try:
        pid = int(shown.get("MainPID", "0"))
    except ValueError:
        pid = 0
    if pid <= 1:
        return "none"
    env = read_environ(pid)
    if env is None:
        return "unknown"
    return _classify_root(env.get("HERMES_FLEET_CONTROL_ROOT", ""), stable)


def _next_start_root(dropin: Path, desired: bytes | None) -> str:
    """Checkout the next start would use, from the retirement drop-in only.

    Absent means the retirement override is not installed, so the next
    start uses the stable unit. A regular file that matches the desired
    bytes and sets the root to the new checkout means new. Anything else
    is unknown. The file body is not printed.
    """
    try:
        info = os.lstat(dropin)
    except FileNotFoundError:
        return "stable"
    except OSError:
        return "unknown"
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or desired is None:
        return "unknown"
    try:
        live = dropin.read_bytes()
    except OSError:
        return "unknown"
    if live != desired:
        return "unknown"
    needle = "Environment=HERMES_FLEET_CONTROL_ROOT=" + str(NEW)
    roots = [
        line.split("=", 2)[-1]
        for line in live.decode("utf-8", errors="replace").splitlines()
        if line.startswith("Environment=HERMES_FLEET_CONTROL_ROOT=")
    ]
    if roots == [str(NEW)] and needle.encode() in live:
        return "new"
    return "unknown"


def _desired_dropin_bytes(evidence: Path) -> bytes | None:
    desired = evidence / "fleet-retirement.conf.desired"
    try:
        info = os.lstat(desired)
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return None
    try:
        return desired.read_bytes()
    except OSError:
        return None


def _confirm_dropin_unloaded(user: bool) -> dict[str, str]:
    _daemon_reload(user)
    shown = systemctl_show(user)
    if shown is None:
        die("gateway show failed")
    if any(Path(part).name == "fleet-retirement.conf" for part in shown.get("DropInPaths", "").split()):
        die("retirement drop-in is still loaded")
    if shown.get("NeedDaemonReload") != "no":
        die("daemon reload still needed")
    return shown


def _gateway_already_stable(shown: dict[str, str], stable: str, config_status: str, dropin_plan: str) -> bool:
    """True when this run changed nothing and the stable gateway is already healthy."""
    if dropin_plan != "absent" or config_status not in {"unchanged", "preserved"}:
        return False
    if shown.get("ActiveState") != "active" or shown.get("SubState") != "running":
        return False
    if shown.get("NeedDaemonReload") != "no":
        return False
    if "fleet-delegation.conf" not in dropin_names(shown):
        return False
    if any(Path(part).name == "fleet-retirement.conf" for part in shown.get("DropInPaths", "").split()):
        return False
    try:
        pid = int(shown.get("MainPID", "0"))
    except ValueError:
        return False
    if pid <= 1:
        return False
    env = read_environ(pid)
    if env is None or env.get("HERMES_FLEET_CONTROL_ROOT") != stable:
        return False
    if str(env.get("FLEET_CONTROL_PYTHON", "")).strip():
        return False
    return True


def _rollback_refuse(
    *,
    running: str,
    next_start: str,
    names_new: str,
    dropin_status: str,
    config_status: str,
    reason: str,
    detail: str,
    completed: str = "none",
    incomplete: str = "dropin,config,restart",
    repeat_status: bool = True,
) -> None:
    """Stop before a successful rollback. Does not print config text or secret values."""
    out("running-root=" + running)
    out("next-start-root=" + next_start)
    out("config-names-new=" + names_new)
    out("rollback-completed=" + completed)
    out("rollback-incomplete=" + incomplete)
    if repeat_status:
        out("dropin-rollback=" + dropin_status)
        out("config-rollback=" + config_status)
    out("rollback-reason=" + reason)
    out("rollback-detail=" + detail)
    warn("do not restart the gateway until rollback completes")
    out("rollback=incomplete")
    die("rollback incomplete; operator intervention required")


def _unit_active_state(user: bool, unit: str) -> str | None:
    if not re.fullmatch(r"[A-Za-z0-9:@._-]+", unit):
        return None
    argv = ["systemctl"]
    if user:
        argv.append("--user")
    argv.extend(["show", "-pActiveState", unit])
    code, text = _run(argv)
    if code != 0:
        return None
    for line in text.splitlines():
        if line.startswith("ActiveState="):
            return line.split("=", 1)[1]
    return None


def _activation_problem(
    user: bool,
    shown: dict[str, str],
    *,
    require_stop_policy: bool = True,
) -> str | None:
    """Refuse an unknown Restart= or a trigger that could start the unit.

    systemctl stop suppresses Restart=, including always and on-success,
    so those policies are accepted. An empty or unrecognized Restart= is
    refused before the stop. An already-stopped unit is not refused for
    Restart= alone. A socket, path, or timer is always checked.
    """
    if require_stop_policy:
        policy = shown.get("Restart", "")
        if policy not in SAFE_STOP_RESTART:
            return "restart-policy-unknown"
    for unit in shown.get("TriggeredBy", "").split():
        if not unit.endswith((".socket", ".path", ".timer")):
            continue
        state = _unit_active_state(user, unit)
        if state is None:
            return "activation-unreadable"
        if state not in {"inactive", "failed"}:
            return "activation-unit-active"
    return None


def _unit_cgroup_pids(control_group: str) -> list[int] | None:
    """PIDs in the unit cgroup. [] means the cgroup is gone. None is unreadable."""
    text = control_group.strip()
    if text in {"", "/"}:
        return []
    if not text.startswith("/") or ".." in text.split("/"):
        return None
    relative = text.lstrip("/")
    for root in (Path("/sys/fs/cgroup"), Path("/sys/fs/cgroup/systemd")):
        path = root / relative / "cgroup.procs"
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError:
            return None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            return None
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        pids: list[int] = []
        for line in raw.split():
            if not line.isdigit():
                return None
            pids.append(int(line))
        return pids
    return []


def _stopped_state(shown: dict[str, str]) -> bool:
    if shown.get("ActiveState") not in {"inactive", "failed"}:
        return False
    if shown.get("SubState") not in {"dead", "failed"}:
        return False
    try:
        pid = int(shown.get("MainPID", "0"))
    except ValueError:
        return False
    return pid == 0


def _cgroup_clear(shown: dict[str, str]) -> bool:
    return _unit_cgroup_pids(shown.get("ControlGroup", "")) == []


def _stop_held(shown: dict[str, str] | None) -> bool:
    return shown is not None and _stopped_state(shown) and _cgroup_clear(shown)


def _ensure_stopped(user: bool, shown: dict[str, str]) -> tuple[dict[str, str] | None, str, bool]:
    """Stop the unit and require a verified stop. Does not start it.

    The detail is empty when the unit is verified stopped. The bool is
    true when this call ran systemctl stop. A refusal detail means the
    caller must not write files and must not start.
    """
    already = _stop_held(shown)
    problem = _activation_problem(user, shown, require_stop_policy=not already)
    if problem is not None:
        return None, problem, False
    if already:
        return shown, "", False
    argv = ["systemctl", "--user", "stop", UNIT] if user else ["systemctl", "stop", UNIT]
    if _run(argv)[0] != 0:
        return None, "stop-failed", True
    after = systemctl_show(user)
    if not _stop_held(after):
        return None, "stop-unverified", True
    return after, "", True


def _start_stopped(
    user: bool,
    before_pid: int,
    expected_root: str,
    expect_retirement: bool,
) -> None:
    """Start a unit that this command has already verified stopped. Does not reload."""
    argv_prefix = ["systemctl", "--user"] if user else ["systemctl"]
    if _run([*argv_prefix, "start", UNIT])[0] != 0:
        die("start failed")
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
        die("start health failed (" + ",".join(blockers) + ")")
    time.sleep(RESTART_SETTLE_SECONDS)
    settled = systemctl_show(user)
    if settled is None:
        die("gateway show failed")
    held = restart_held(shown, settled, pid)
    if held:
        die("start did not stay up (" + ",".join(held) + ")")
    settled_env = read_environ(pid)
    if settled_env is None or settled_env.get("HERMES_FLEET_CONTROL_ROOT") != expected_root:
        die("running root changed during settle")
    if settled.get("NeedDaemonReload") != "no":
        die("daemon reload still needed")


def cmd_rollback() -> int:
    """Undo the drop-in and config.yaml. Journals are only read."""
    return _run_locked(_cmd_rollback_locked)


def _cmd_rollback_locked() -> int:
    """Undo the drop-in and config.yaml. Journals are only read.

    Scope and the stable directory come from the evidence directory.
    An inactive or failed unit is accepted. MainPID 0 is the before
    value. Journal, side-file, and delegation differences are warnings.
    This command does not write or delete journal files, and it does
    not overwrite a drifted side file or delegation file.

    The retirement drop-in and config.yaml are classified before either
    is written. An unverified drop-in or a config that is not
    stable-compatible leaves both files untouched, does not stop the
    unit, and does not start it. A plan that must replace a running
    gateway stops it and verifies the stop before the first write.
    The writes are unlink, then config.yaml, then daemon-reload, then
    start. Restart=always and Restart=on-success are accepted because
    systemctl stop suppresses them. The stop is verified, checked
    again before the config write when this command stopped the unit,
    and checked again on the post-reload show before start. A failure
    after the stop leaves the unit stopped and does not start it.
    rollback=done is printed only after that start passes its health
    checks. An already-healthy stable gateway is not stopped.
    """
    evidence = evidence_root()
    _recorded, user = recorded_scope(evidence)
    stable_file = evidence / "stable_dir"
    manifest_file = evidence / "journals.manifest"
    if stable_file.is_symlink() or not stable_file.is_file() or manifest_file.is_symlink() or not manifest_file.is_file():
        die("baseline is missing")
    stable = stable_file.read_text(encoding="utf-8").strip()
    shown = systemctl_show(user)
    if shown is None:
        die("gateway show failed")
    before = gateway_before_pid(shown)
    env = read_environ(before) if before > 1 else None
    if before > 1 and env is None:
        die("gateway environ is unreadable")
    recorded = manifest_file.read_text(encoding="utf-8")
    warn_journals(journal_difference(env, recorded))
    warn_side_files(_side_labels(evidence), action="rollback")
    delegation = stored_path(evidence, "delegation.path")
    if _delegation_changed(evidence, delegation):
        warn("delegation file differs from baseline; rollback will not modify it")
        out("delegation-drift=changed")
    else:
        out("delegation-drift=none")
    dropin = delegation.with_name("fleet-retirement.conf")
    dropin_plan = _dropin_plan(evidence, delegation)
    config = stored_path(evidence, "config.path")
    config_status, payload, detail = _config_plan(evidence, config, stable)
    running = _running_root(before, env, stable)
    next_start = _next_start_root(dropin, _desired_dropin_bytes(evidence))
    names_new = _config_names_label(config)
    if dropin_plan == "unverified" or config_status == "incomplete":
        if dropin_plan == "unverified":
            printed_dropin = "unverified"
            printed_config = "skipped"
            reason = "retirement drop-in is unverified"
            printed_detail = "dropin-unverified"
            incomplete = "dropin,config,restart"
        elif dropin_plan == "removable":
            printed_dropin = "kept"
            printed_config = "incomplete"
            reason = "fleet mcp config is not stable-compatible"
            printed_detail = detail
            incomplete = "dropin,config,restart"
        else:
            printed_dropin = "absent"
            printed_config = "incomplete"
            reason = "fleet mcp config is not stable-compatible"
            printed_detail = detail
            incomplete = "config,restart"
        _rollback_refuse(
            running=running,
            next_start=next_start,
            names_new=names_new,
            dropin_status=printed_dropin,
            config_status=printed_config,
            reason=reason,
            detail=printed_detail,
            incomplete=incomplete,
        )
    if config_status in {"restored", "reversed"} and (payload is None or str(NEW).encode() in payload):
        _rollback_refuse(
            running=running,
            next_start=next_start,
            names_new=names_new,
            dropin_status="kept" if dropin_plan == "removable" else "absent",
            config_status="incomplete",
            reason="fleet mcp config is not stable-compatible",
            detail="foreign-checkout",
            incomplete="dropin,config,restart" if dropin_plan == "removable" else "config,restart",
        )
    if _gateway_already_stable(shown, stable, config_status, dropin_plan):
        reloaded = _confirm_dropin_unloaded(user)
        if not _gateway_already_stable(reloaded, stable, config_status, dropin_plan):
            die("gateway left the stable state during reload")
        out("dropin-rollback=absent")
        out("config-rollback=" + config_status)
        out("rollback=already-stable")
        out("STEP 10 OK")
        return 0
    stopped, stop_detail, issued_stop = _ensure_stopped(user, shown)
    if stopped is None:
        attempted = stop_detail in {"stop-failed", "stop-unverified"}
        _rollback_refuse(
            running=running,
            next_start=next_start,
            names_new=names_new,
            dropin_status="kept" if dropin_plan == "removable" else "absent",
            config_status="skipped",
            reason="gateway did not stay stopped" if attempted else "gateway stop not attempted",
            detail=stop_detail,
            incomplete="dropin,config,restart" if dropin_plan == "removable" else "config,restart",
        )
    if dropin_plan == "removable":
        _apply_dropin_removal(evidence, delegation)
    if issued_stop:
        again = systemctl_show(user)
        if not _stop_held(again):
            completed = "dropin" if dropin_plan == "removable" else "none"
            remaining = ["restart"]
            if config_status in {"restored", "reversed"}:
                remaining.insert(0, "config")
            _rollback_refuse(
                running=running,
                next_start=_next_start_root(dropin, _desired_dropin_bytes(evidence)),
                names_new=names_new,
                dropin_status="removed" if dropin_plan == "removable" else "absent",
                config_status="skipped",
                reason="gateway did not stay stopped",
                detail="stop-unverified",
                completed=completed,
                incomplete=",".join(remaining),
            )
    if dropin_plan == "removable":
        out("dropin-rollback=removed")
    else:
        out("dropin-rollback=absent")
    _apply_config(evidence, config, config_status, payload)
    out("config-rollback=" + config_status)
    if _config_names_new(config):
        completed = "dropin" if dropin_plan == "removable" else "none"
        if config_status in {"restored", "reversed"}:
            completed = completed + ",config" if completed != "none" else "config"
        done = set() if completed == "none" else set(completed.split(","))
        remaining = [item for item in ("dropin", "config", "restart") if item not in done]
        _rollback_refuse(
            running=running,
            next_start=_next_start_root(dropin, _desired_dropin_bytes(evidence)),
            names_new="yes",
            dropin_status="removed" if dropin_plan == "removable" else "absent",
            config_status=config_status,
            reason="config.yaml still names the new checkout",
            detail="foreign-checkout",
            completed=completed,
            incomplete=",".join(remaining),
        )
    reloaded = _confirm_dropin_unloaded(user)
    if _config_names_new(config):
        _rollback_refuse(
            running="none",
            next_start="stable",
            names_new="yes",
            dropin_status="removed" if dropin_plan == "removable" else "absent",
            config_status=config_status,
            reason="config.yaml still names the new checkout",
            detail="foreign-checkout",
            completed="dropin,config",
            incomplete="restart",
        )
    if not _stop_held(reloaded):
        _rollback_refuse(
            running=_live_root_label(reloaded, stable),
            next_start="stable",
            names_new="no",
            dropin_status="removed" if dropin_plan == "removable" else "absent",
            config_status=config_status,
            reason="gateway did not stay stopped",
            detail="stop-unverified",
            completed="dropin,config",
            incomplete="restart",
            repeat_status=False,
        )
    _start_stopped(user, before, stable, False)
    out("rollback=done")
    out("STEP 10 OK")
    return 0


def cmd_confirm() -> int:
    return _run_locked(_cmd_confirm_locked)


def _cmd_confirm_locked() -> int:
    evidence = evidence_root()
    _recorded, user = _same_scope(evidence)
    shown, env, pid = _live_gateway(user)
    if shown.get("NeedDaemonReload") != "no":
        die("daemon reload is pending")
    if str(env.get("FLEET_CONTROL_PYTHON", "")).strip():
        die("FLEET_CONTROL_PYTHON is set")
    stable = (evidence / "stable_dir").read_text(encoding="utf-8").strip()
    if env.get("HERMES_FLEET_CONTROL_ROOT") != stable:
        die("running root is not the stable checkout")
    require_pins(Path(stable), STABLE_SHA, STABLE_TREE)
    if "fleet-delegation.conf" not in dropin_names(shown):
        die("fleet-delegation.conf is not loaded")
    if any(Path(part).name == "fleet-retirement.conf" for part in shown.get("DropInPaths", "").split()):
        die("retirement drop-in is still loaded")
    delegation = stored_path(evidence, "delegation.path")
    retirement = delegation.with_name("fleet-retirement.conf")
    if retirement.exists() or retirement.is_symlink():
        die("retirement drop-in is still on disk")
    manifest_file = evidence / "journals.manifest"
    if manifest_file.is_symlink() or not manifest_file.is_file():
        die("baseline is missing")
    warn_journals(journal_difference(env, manifest_file.read_text(encoding="utf-8")), action="confirm")
    warn_side_files(_side_labels(evidence), action="confirm")
    config = stored_path(evidence, "config.path")
    if config.is_symlink() or not config.is_file():
        die("config.yaml is missing")
    try:
        config_bytes = config.read_bytes()
        config_text = config_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        out("config-mcp=not-stable-compatible")
        out("config-mcp-detail=config-unreadable")
        die("config.yaml fleet mcp is not stable-compatible")
    server_name = _recorded_server_name(evidence)
    if server_name is None:
        out("config-mcp=not-stable-compatible")
        out("config-mcp-detail=fleet-server-name-missing")
        die("config.yaml fleet mcp is not stable-compatible")
    recorded = evidence / "config.yaml"
    verified = False
    try:
        recorded_bytes = recorded.read_bytes() if recorded.is_file() and not recorded.is_symlink() else b""
        verified = (
            config_bytes == recorded_bytes
            and _baseline_identity_matches(evidence, recorded_bytes)
            and str(NEW).encode() not in config_bytes
        )
    except OSError:
        verified = False
    if verified:
        out("config-mcp=stable-compatible")
        out("config-mcp-detail=verified-baseline")
    else:
        verdict = fleet_mcp_compatibility(config_text, stable, server_name)
        if verdict != "compatible":
            out("config-mcp=not-stable-compatible")
            out("config-mcp-detail=" + verdict)
            if str(NEW) in config_text:
                die("config.yaml names the new checkout")
            die("config.yaml fleet mcp is not stable-compatible")
        out("config-mcp=stable-compatible")
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


COMMANDS = {
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


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in COMMANDS:
        sys.stderr.write("STOP: usage: c08cb1e_material.py " + "|".join(COMMANDS) + "\n")
        return 2
    try:
        return COMMANDS[argv[1]]()
    except Stop:
        return 1
    except Exception as exc:
        sys.stderr.write("STOP: command failed (" + type(exc).__name__ + ")\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
