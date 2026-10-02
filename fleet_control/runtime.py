"""Explicit Python runtime for the Control Fleet helpers.

A Hermes update can put another ``python3`` first on ``PATH``. The
delegation helpers import ``cryptography``. Resolving ``python3`` from
that ``PATH`` is not reproducible. A reviewed install creates
``runtime/venv`` from an absolute interpreter and this checkout's
hashed ``requirements.lock`` (direct pins and transitives). The MCP
launcher then execs that virtualenv's Python and passes the helper
script as an argument, so the shebang is not the interpreter selection.

``FLEET_CONTROL_PYTHON``, when set, must be an absolute path. It must
not be Hermes's agent virtualenv. There is no ``PATH`` fallback.

This module is standard library only. The installer may be started by
whatever ``python3`` is on ``PATH``. The helpers it produces must not be.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

HERMES_AGENT_VENV = "/home/hermes/.hermes/hermes-agent/venv"
PYTHON_OVERRIDE = "FLEET_CONTROL_PYTHON"
MANAGED_RELATIVE = ("runtime", "venv", "bin", "python")
UNAVAILABLE = "managed python is unavailable"

Runner = Callable[[Sequence[str]], None]


class RuntimePlanError(ValueError):
    """Fixed public failure. The message does not include secret material."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.public_message = message

    def __repr__(self) -> str:
        return f"RuntimePlanError({self.public_message!r})"


def checkout_root() -> Path:
    """Directory that contains ``fleet_control`` and ``requirements.lock``."""
    return Path(__file__).resolve().parents[1]


def _inside_hermes_agent_venv(path: str) -> bool:
    normalized = os.path.normpath(path)
    prefix = os.path.normpath(HERMES_AGENT_VENV)
    return normalized == prefix or normalized.startswith(prefix + os.sep)


def validate_interpreter(path: object) -> str:
    """Accept one absolute interpreter. Reject ``PATH`` names and the agent venv."""
    if not isinstance(path, str) or not path or path != path.strip():
        raise RuntimePlanError("interpreter must be an absolute path")
    if any(ch in path for ch in ("\n", "\r", "\x00")):
        raise RuntimePlanError("interpreter must be an absolute path")
    if not os.path.isabs(path):
        raise RuntimePlanError("interpreter must be an absolute path")
    normalized = os.path.normpath(path)
    if _inside_hermes_agent_venv(normalized):
        raise RuntimePlanError("refusing Hermes agent virtualenv")
    try:
        if _inside_hermes_agent_venv(os.path.realpath(normalized)):
            raise RuntimePlanError("refusing Hermes agent virtualenv")
    except OSError:
        raise RuntimePlanError("interpreter must be an absolute path") from None
    return normalized


def managed_python(root: str | Path) -> str:
    """Virtualenv interpreter a reviewed install creates under ``root``."""
    return str(Path(root).resolve().joinpath(*MANAGED_RELATIVE))


def intended_venv_prefix(interpreter: str) -> str:
    """Virtualenv root that owns ``interpreter``, without resolving the binary.

    ``bin/python`` is frequently a symlink to the system interpreter.
    Resolving that symlink yields the system prefix, not the virtualenv.
    """
    binary = os.path.abspath(interpreter)
    return os.path.normpath(os.path.join(os.path.dirname(binary), os.pardir))


def running_intended_environment(interpreter: str) -> bool:
    """True when this process is the virtualenv that owns ``interpreter``.

    ``realpath(sys.executable)`` does not establish membership. A virtualenv
    Python and the system Python often resolve to the same binary, while
    ``sys.prefix`` still names the virtualenv and ``sys.base_prefix`` names
    the interpreter the virtualenv was created from.
    """
    prefix = intended_venv_prefix(interpreter)
    if not os.path.isfile(os.path.join(prefix, "pyvenv.cfg")):
        return False
    if os.path.realpath(sys.prefix) == os.path.realpath(sys.base_prefix):
        return False
    # Resolve directory links only. Never compare ``realpath(sys.executable)``.
    return os.path.realpath(sys.prefix) == os.path.realpath(prefix)


def resolve_helper_python(root: str | Path, environ: dict[str, str]) -> str:
    """Interpreter the helpers and the MCP launcher must exec.

    An override is used only when ``FLEET_CONTROL_PYTHON`` is set to an
    absolute path outside the Hermes agent virtualenv. Otherwise the
    managed virtualenv interpreter is required. ``python3`` on ``PATH``
    is never selected.
    """
    override = str(environ.get(PYTHON_OVERRIDE) or "").strip()
    if override:
        return validate_interpreter(override)
    return validate_interpreter(managed_python(root))


def reexec_managed_python() -> None:
    """Replace this process with the managed interpreter before third-party imports.

    A direct ``./fleet-delegate`` still starts through ``#!/usr/bin/env python3``.
    That bootstrap is standard library only. It execs the managed interpreter
    and does not continue on the ``PATH`` interpreter. The MCP launcher does
    not use the shebang; it execs the managed interpreter itself.
    """
    try:
        target = resolve_helper_python(checkout_root(), dict(os.environ))
    except RuntimePlanError:
        _unavailable()
    if not os.path.isfile(target) or not os.access(target, os.X_OK):
        _unavailable()
    if running_intended_environment(target):
        return
    if not os.path.isfile(os.path.join(intended_venv_prefix(target), "pyvenv.cfg")):
        _unavailable()
    try:
        os.execv(target, [target, *sys.argv])
    except OSError:
        _unavailable()


def _unavailable() -> None:
    sys.stderr.write(UNAVAILABLE + "\n")
    raise SystemExit(1)


@dataclass(frozen=True)
class RuntimeInstallPlan:
    """Commands a reviewed install runs. Nothing here contacts a network by itself."""

    interpreter: str
    venv_dir: str
    venv_python: str
    requirements: str
    create_argv: tuple[str, ...]
    install_argv: tuple[str, ...]


def plan_runtime_install(interpreter: object, root: str | Path) -> RuntimeInstallPlan:
    """Plan a virtualenv from an explicit interpreter and ``requirements.lock``.

    Does not create the virtualenv and does not install packages.
    The lock pins direct and transitive dependencies by hash.
    """
    binary = validate_interpreter(interpreter)
    checkout = Path(root).resolve()
    venv_dir = checkout / "runtime" / "venv"
    venv_python = venv_dir / "bin" / "python"
    requirements = checkout / "requirements.lock"
    if _inside_hermes_agent_venv(str(venv_dir)) or _inside_hermes_agent_venv(str(venv_python)):
        raise RuntimePlanError("refusing Hermes agent virtualenv")
    return RuntimeInstallPlan(
        interpreter=binary,
        venv_dir=str(venv_dir),
        venv_python=str(venv_python),
        requirements=str(requirements),
        create_argv=(binary, "-m", "venv", str(venv_dir)),
        install_argv=(
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--require-virtualenv",
            "--require-hashes",
            "--only-binary=:all:",
            "-r",
            str(requirements),
        ),
    )


def execute_runtime_install(plan: RuntimeInstallPlan, runner: Runner | None = None) -> None:
    """Run a previously built plan. The default runner is ``subprocess.run`` without a shell."""
    if not os.path.isfile(plan.interpreter) or not os.access(plan.interpreter, os.X_OK):
        raise RuntimePlanError("interpreter is not executable")
    validate_interpreter(plan.interpreter)
    if not os.path.isfile(plan.requirements):
        raise RuntimePlanError("requirements.lock is missing")

    def _run(argv: Sequence[str]) -> None:
        if runner is not None:
            runner(argv)
            return
        subprocess.run(list(argv), check=True, shell=False)

    _run(plan.create_argv)
    if not os.path.isfile(plan.venv_python) or not os.access(plan.venv_python, os.X_OK):
        raise RuntimePlanError(UNAVAILABLE)
    validate_interpreter(plan.venv_python)
    _run(plan.install_argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Create ``runtime/venv``. Requires ``--python``; does not default to ``PATH``."""
    parser = argparse.ArgumentParser(prog="install-control-runtime")
    parser.add_argument(
        "--python",
        required=True,
        help="absolute interpreter used to create runtime/venv (for example /usr/bin/python3.12)",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="checkout root (defaults to this repository)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    root = Path(args.root) if args.root else checkout_root()
    try:
        plan = plan_runtime_install(args.python, root)
        execute_runtime_install(plan)
    except (RuntimePlanError, subprocess.CalledProcessError):
        sys.stderr.write(UNAVAILABLE + "\n")
        return 1
    sys.stdout.write(plan.venv_python + "\n")
    return 0
