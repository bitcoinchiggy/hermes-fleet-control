#!/bin/bash
# Read-only answers for the open questions in c08cb1e-deploy-plan.md.
# Run on the Control host before the first deploy paste.
# This script does not write, restart, install, fetch, checkout, or
# print secret values. It reports present/absent, path class, or redacted.
set -euo pipefail
if [[ $# -ne 0 ]]; then
  echo "STOP: c08cb1e-preflight.sh takes no arguments" >&2
  exit 2
fi
py=/usr/bin/python3.12
if [[ ! -x $py ]]; then
  py=python3
fi
exec "$py" - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

UNIT = "hermes-gateway-control.service"
SHA = "c08cb1ebd073ee7946f49005dd45071366eeb688"
STABLE_SHA = "dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a"
NEW = Path("/opt/hermes-fleet-control") / SHA
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
SAFE_PATH_RE = re.compile(r"^/[A-Za-z0-9._+/-]+$")
CHECKOUT_RE = re.compile(r"^/opt/hermes-fleet-control/[A-Za-z0-9._/-]+$")
HOST_RE = re.compile(r"^[A-Za-z0-9.-]+(?::[0-9]+)?$")
SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PRIVATE|NSEC|CREDENTIAL|KEY)$|^(AUTHORIZATION)$",
    re.IGNORECASE,
)
SKIP_WALK = {".git", "node_modules", "venv", "proc", "sys", "runtime"}


def out(line: str) -> None:
    sys.stdout.write(line + "\n")


def classify_origin(url: str) -> tuple[str, str]:
    """Return (form, embedded-token) without echoing the URL."""
    if "://" in url:
        scheme, rest = url.split("://", 1)
        hostport = rest.split("/", 1)[0]
        token = "present" if "@" in hostport else "absent"
        host = hostport.split("@")[-1]
        if HOST_RE.fullmatch(host) and re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]*", scheme):
            return f"{scheme}://{host}", token
        return "url", token
    if re.match(r"^[A-Za-z0-9._-]+@[^:]+:", url):
        return "scp-like", "absent"
    return "unknown", "unknown"


def classify_mcp_text(value: object) -> str:
    if value is None or value == "":
        return "absent"
    if not isinstance(value, str):
        return "redacted"
    if "${HERMES_FLEET_CONTROL_ROOT}" in value:
        return "interpolated"
    if CHECKOUT_RE.fullmatch(value):
        return "absolute-checkout:" + value
    if value.startswith("/") or "://" in value or "@" in value:
        return "redacted"
    if re.fullmatch(r"[A-Za-z0-9._+/-]+", value):
        return "literal:" + value
    return "redacted"


def classify_mcp_field(value: object) -> str:
    if isinstance(value, list):
        if not value:
            return "absent"
        return ",".join(classify_mcp_text(item) for item in value)
    return classify_mcp_text(value)


def safe_path(value: str) -> str:
    if SAFE_PATH_RE.fullmatch(value):
        return value
    return "redacted"


def presence(env: dict[str, str], key: str) -> str:
    raw = env.get(key, "")
    if raw.strip() == "":
        return "absent"
    return "set"


def _self_check() -> None:
    form, token = classify_origin("https://user:example-token@example.test/org/repo.git")
    assert form == "https://example.test" and token == "present", "url userinfo"
    form, token = classify_origin("https://example.test/org/repo.git")
    assert form == "https://example.test" and token == "absent", "url without userinfo"
    form, token = classify_origin("git@example.test:org/repo.git")
    assert form == "scp-like" and token == "absent", "scp user is not a token"
    assert classify_mcp_text("${HERMES_FLEET_CONTROL_ROOT}/fleet-mcp") == "interpolated"
    assert classify_mcp_text(
        "/opt/hermes-fleet-control/dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a/fleet-mcp"
    ).startswith("absolute-checkout:")
    assert classify_mcp_text("https://user:example-token@example.test/x") == "redacted"
    assert classify_mcp_text("node") == "literal:node"
    assert presence({"FLEET_CONTROL_PYTHON": ""}, "FLEET_CONTROL_PYTHON") == "absent"
    assert presence({"FLEET_CONTROL_PYTHON": "/usr/bin/python3.12"}, "FLEET_CONTROL_PYTHON") == "set"
    assert SECRET_KEY_RE.search("FLEET_PROVISIONER_CALLER_TOKEN")
    assert not SECRET_KEY_RE.search("FLEET_PROVISIONER_GIT_REF")


def run(argv: list[str], *, cwd: str | None = None) -> tuple[int, str]:
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
    code, text = run(
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
    code, text = run(argv)
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
    code, text = run(argv)
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
    names = []
    for part in text.split():
        names.append(Path(part).name)
    return names


def report_dropins(prefix: str, names: list[str]) -> None:
    out(f"{prefix}-dropins=" + (",".join(names) if names else "none"))
    if not names:
        out(f"{prefix}-fleet-delegation-loaded=no")
        out(f"{prefix}-last-sorted-dropin=none")
        out(f"{prefix}-dropin-after-fleet-retirement=none")
        return
    ordered = sorted(names)
    out(f"{prefix}-fleet-delegation-loaded=" + ("yes" if "fleet-delegation.conf" in names else "no"))
    out(f"{prefix}-last-sorted-dropin={ordered[-1]}")
    later = [name for name in names if name > "fleet-retirement.conf"]
    out(
        f"{prefix}-dropin-after-fleet-retirement="
        + (",".join(later) if later else "none")
    )


def stable_dirs() -> list[Path]:
    root = Path("/opt/hermes-fleet-control")
    if not root.is_dir():
        return []
    return sorted(
        path for path in root.glob("dcb3f950*") if path.is_dir() and not path.is_symlink()
    )


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
    candidates = []
    for directory in stable_dirs():
        candidates.append(directory / "runtime" / "venv" / "bin" / "python")
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


def report_skill_place(label: str, paths: list[Path]) -> None:
    if not paths:
        out(f"skill-{label}=absent")
        return
    shown = []
    for path in paths:
        text = str(path)
        shown.append(text if SAFE_PATH_RE.fullmatch(text) else "redacted")
    out(f"skill-{label}=present paths=" + ";".join(shown))


def tombstone_dirs(pid: int, env: dict[str, str]) -> list[str]:
    roots: list[Path] = []
    for key, value in env.items():
        if SECRET_KEY_RE.search(key) or not value.startswith("/") or re.search(r"\s", value):
            continue
        upper = key.upper()
        if not any(token in upper for token in ("STATE", "DATA", "DIR", "ROOT", "JOURNAL", "TOMB", "HOME")):
            continue
        path = Path(value)
        if path.is_dir() and not path.is_symlink() and str(path) not in {"/", "/root", "/home", "/var", "/opt"}:
            roots.append(path)
    try:
        cwd = Path(os.path.realpath(f"/proc/{pid}/cwd"))
    except OSError:
        cwd = None
    if cwd is not None and cwd.is_dir():
        roots.append(cwd)
    seen: list[str] = []
    found: list[str] = []
    walked = 0
    for directory in roots:
        resolved = str(directory.resolve()) if not directory.is_symlink() else ""
        if not resolved or resolved in seen:
            continue
        seen.append(resolved)
        for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
            current = Path(dirpath)
            depth = len(current.relative_to(directory).parts) if current != directory else 0
            if depth > 5:
                dirnames.clear()
                continue
            dirnames[:] = [name for name in dirnames if name not in SKIP_WALK]
            for name in filenames:
                walked += 1
                if walked > 4000:
                    return found + ["walk-capped"]
                if "tombstone" not in str(current / name).lower():
                    continue
                parent = str(current)
                if parent not in found:
                    found.append(safe_path(parent))
    return found


def provisioner_units() -> list[str]:
    code, text = run(["systemctl", "list-units", "--type=service", "--all", "--plain", "--no-legend"])
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


def report_gateway(scope: str, user: bool) -> None:
    shown = systemctl_show(user)
    if shown is None:
        out(f"{scope}-show=unreadable")
        return
    out(f"{scope}-active={shown['ActiveState']}")
    out(f"{scope}-nrestarts={shown['NRestarts']}")
    fragment = shown["FragmentPath"]
    out(f"{scope}-fragment=" + (safe_path(fragment) if fragment.startswith("/") else "redacted"))
    report_dropins(scope, dropin_names(shown))
    try:
        pid = int(shown["MainPID"])
    except ValueError:
        out(f"{scope}-process=not-live")
        return
    if shown["ActiveState"] != "active" or pid <= 1 or not Path(f"/proc/{pid}").exists():
        out(f"{scope}-process=not-live")
        return
    env = read_environ(pid)
    if env is None:
        out(f"{scope}-environ=unreadable")
        return
    out(f"{scope}-pid={pid}")
    out(f"{scope}-FLEET_CONTROL_PYTHON={presence(env, 'FLEET_CONTROL_PYTHON')}")
    out(f"{scope}-FLEET_PROVISIONER_GIT_REF={presence(env, 'FLEET_PROVISIONER_GIT_REF')}")
    out(
        f"{scope}-HERMES_FLEET_CONTROL_INTEGRATION="
        + ("1" if env.get("HERMES_FLEET_CONTROL_INTEGRATION") == "1" else presence(env, "HERMES_FLEET_CONTROL_INTEGRATION"))
    )
    root = env.get("HERMES_FLEET_CONTROL_ROOT", "")
    out(f"{scope}-HERMES_FLEET_CONTROL_ROOT=" + (safe_path(root) if root.startswith("/") else "absent-or-redacted"))
    home = env.get("HERMES_HOME", "")
    out(f"{scope}-HERMES_HOME=" + (safe_path(home) if home.startswith("/") else "absent-or-redacted"))
    server_name = env.get("HERMES_FLEET_MCP_SERVER", "")
    if server_name and NAME_RE.fullmatch(server_name):
        out(f"{scope}-HERMES_FLEET_MCP_SERVER={server_name}")
    elif server_name:
        out(f"{scope}-HERMES_FLEET_MCP_SERVER=redacted")
    else:
        out(f"{scope}-HERMES_FLEET_MCP_SERVER=absent")
    profile = env.get("FLEET_CONTROL_HERMES_PROFILE", "")
    profiles_root = env.get("FLEET_CONTROL_PROFILES_ROOT") or "/home/hermes/.hermes/profiles"
    if NAME_RE.fullmatch(profile) and profiles_root.startswith("/") and SAFE_PATH_RE.fullmatch(profiles_root):
        out(f"{scope}-profile={profile}")
        out(f"{scope}-profiles-root={profiles_root}")
        report_mcp_and_skills(scope, env, Path(profiles_root) / profile / "config.yaml", root, home)
    else:
        out(f"{scope}-profile=absent-or-redacted")
        out(f"{scope}-mcp-config=unknown")
        out(f"{scope}-skill-load=unknown")


def report_mcp_and_skills(scope: str, env: dict[str, str], config: Path, root: str, home: str) -> None:
    view = None
    if config.is_symlink():
        out(f"{scope}-config-yaml=symlink")
        out(f"{scope}-mcp-config=unparsed")
    elif not config.is_file():
        out(f"{scope}-config-yaml=absent")
        out(f"{scope}-mcp-config=unknown")
    else:
        out(f"{scope}-config-yaml={safe_path(str(config))}")
        view = yaml_view(config)
    if config.is_symlink() or not config.is_file():
        pass
    elif view is None:
        out(f"{scope}-mcp-config=unparsed")
        out(f"{scope}-skill-external-dirs=unparsed")
    else:
        server_name = env.get("HERMES_FLEET_MCP_SERVER", "")
        servers = view.get("servers") or {}
        server = servers.get(server_name) if isinstance(servers, dict) else None
        if not isinstance(server, dict):
            out(f"{scope}-mcp-entry=absent")
        else:
            out(f"{scope}-mcp-command={classify_mcp_field(server.get('command'))}")
            out(f"{scope}-mcp-args={classify_mcp_field(server.get('args'))}")
            out(f"{scope}-mcp-cwd={classify_mcp_field(server.get('cwd'))}")
        external = []
        for item in view.get("external_dirs") or []:
            external.append(safe_path(item) if isinstance(item, str) else "redacted")
        out(f"{scope}-skill-external-dirs=" + (",".join(external) if external else "none"))
        create_dir = view.get("create_dir") or ""
        out(
            f"{scope}-skill-create-dir="
            + (safe_path(create_dir) if create_dir.startswith("/") else ("absent" if not create_dir else "redacted"))
        )
    checkout_skill = []
    if root.startswith("/") and SAFE_PATH_RE.fullmatch(root):
        candidate = Path(root) / "skills" / "fleet-delegation" / "SKILL.md"
        if candidate.is_file() and not candidate.is_symlink():
            checkout_skill.append(candidate)
    report_skill_place(f"{scope}-checkout", checkout_skill)
    home_hits = skill_hits(Path(home) / "skills") if home.startswith("/") and SAFE_PATH_RE.fullmatch(home) else []
    report_skill_place(f"{scope}-home", home_hits)
    if checkout_skill and home_hits:
        left = file_sha(checkout_skill[0])
        right = file_sha(home_hits[0])
        if left and right:
            out(f"{scope}-skill-checkout-vs-home=" + ("same" if left == right else "differs"))
    else:
        out(f"{scope}-skill-checkout-vs-home=n/a")
    checkout_skills = Path(root) / "skills" if root.startswith("/") else None
    external_hit = False
    if view and checkout_skills is not None:
        for item in view.get("external_dirs") or []:
            if isinstance(item, str) and SAFE_PATH_RE.fullmatch(item):
                try:
                    if Path(item).resolve() == checkout_skills.resolve():
                        external_hit = True
                except OSError:
                    continue
    out(f"{scope}-skill-external-includes-checkout=" + ("yes" if external_hit else "no"))
    if home_hits:
        preference = "home-skills"
    elif external_hit:
        preference = "external-dir"
    elif checkout_skill:
        preference = "checkout-only-not-on-skill-path"
    else:
        preference = "not-found"
    # fleet-tip loader order (home skills, then external_dirs). Not /proc maps.
    out(f"{scope}-skill-load={preference}")
    out(f"{scope}-skill-load-basis=fleet-tip-loader-not-process-maps")


def report_provisioner() -> None:
    names = provisioner_units()
    if not names:
        out("provisioner-unit=not-on-this-host")
        out("provisioner-FLEET_PROVISIONER_GIT_REF=not-on-this-host")
        out("tombstone-dir=not-on-this-host")
        return
    active = []
    for name in names:
        code, text = run(["systemctl", "show", "-p", "ActiveState", "--value", name])
        state = text.strip() if code == 0 else "unknown"
        out(f"provisioner-unit={name} active={state}")
        if state == "active":
            active.append(name)
    if len(active) != 1:
        out("provisioner-live-count=" + str(len(active)))
        out("provisioner-FLEET_PROVISIONER_GIT_REF=unknown")
        out("tombstone-dir=unknown")
        return
    code, text = run(["systemctl", "show", "-p", "MainPID", "--value", active[0]])
    try:
        pid = int(text.strip()) if code == 0 else 0
    except ValueError:
        pid = 0
    if pid <= 1:
        out("provisioner-process=not-live")
        out("tombstone-dir=unknown")
        return
    env = read_environ(pid)
    if env is None:
        out("provisioner-environ=unreadable")
        out("tombstone-dir=unknown")
        return
    out("provisioner-FLEET_PROVISIONER_GIT_REF=" + presence(env, "FLEET_PROVISIONER_GIT_REF"))
    dirs = tombstone_dirs(pid, env)
    out("tombstone-dir=" + (",".join(dirs) if dirs else "none-found"))


def main() -> None:
    _self_check()
    out("preflight=c08cb1e-control")
    out("read-only=yes")
    out("other-hosts=not-contacted")
    code, short = run(["hostname", "-s"])
    out("hostname=" + (short.strip() if code == 0 and short.strip() else "unknown"))
    code, fqdn = run(["hostname", "-f"])
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
        out("unit-scope=both")
    elif system_state == "loaded":
        out("unit-scope=system")
    elif user_state == "loaded":
        out("unit-scope=user")
    else:
        out("unit-scope=neither")
        out("FLEET_CONTROL_PYTHON=unknown")
        out("gateway-FLEET_PROVISIONER_GIT_REF=unknown")
        out("mcp-config=unknown")
        out("skill-load=unknown")
    guest_node = Path("/etc/pve").is_dir() and shutil.which("qm") is not None
    out("guest-node-signals=" + ("present" if guest_node else "absent"))
    if system_state == "loaded":
        report_gateway("system", False)
    if user_state == "loaded":
        report_gateway("user", True)
    matches = stable_dirs()
    out("stable-dir-count=" + str(len(matches)))
    if len(matches) == 1:
        stable = matches[0]
        out("stable-dir=" + str(stable))
        head = git_read(stable, "rev-parse", "HEAD")
        tree = git_read(stable, "rev-parse", "HEAD^{tree}")
        out("stable-head=" + (head if head else "unreadable"))
        out("stable-tree=" + (tree if tree else "unreadable"))
        out("stable-head-is-dcb3f950=" + ("yes" if head == STABLE_SHA else "no"))
        origin = git_read(stable, "remote", "get-url", "origin")
        if origin is None:
            out("origin-form=unreadable")
            out("origin-embedded-token=unknown")
        else:
            form, token = classify_origin(origin)
            out("origin-form=" + form)
            out("origin-embedded-token=" + token)
    else:
        for path in matches:
            out("stable-dir=" + str(path))
        out("origin-embedded-token=unknown")
    new_exists = NEW.exists()
    out("new-checkout-exists=" + ("yes" if new_exists else "no"))
    if new_exists and (NEW / ".git").exists():
        new_head = git_read(NEW, "rev-parse", "HEAD")
        out("new-head=" + (new_head if new_head else "unreadable"))
    report_provisioner()
    roles = []
    if system_state == "loaded" or user_state == "loaded":
        roles.append("control")
    if guest_node:
        roles.append("guest-node")
    if provisioner_units():
        roles.append("provisioner")
    out("roles-on-this-host=" + (",".join(roles) if roles else "none"))
    out("PREFLIGHT OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.stderr.write("STOP: preflight failed (" + type(exc).__name__ + ")\n")
        raise SystemExit(1)
PY
