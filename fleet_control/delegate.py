"""Control-local ``delegate_worker``. Signs with Control's Buzz identity.

Phase 1 returns when the relay accepts the DM. It does not wait for the
worker model turn. ``delivery`` is ``relay_accepted``, which is not
execution and not task completion.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sys
from pathlib import Path
from typing import Any

from fleet_control.support.names import InvalidNameError, validate_worker_name
from fleet_control.support.profile_env import HERMES_PROFILES_DIR, validate_profile_name
from fleet_control.support.redact import NSEC_RE

from fleet_control.authorize import authorize_target
from fleet_control.buzz_exec import (
    HEX64_RE,
    UUID_RE,
    BuzzOutputUnusable,
    BuzzTimeout,
    buzz_binary,
    default_buzz_runner,
    delegation_stdin,
    invoke,
    open_dm_argv,
    parse_dm_open,
    parse_send,
    send_argv,
)
from fleet_control.config import load_fleet_api_settings, refuse_forbidden_environment
from fleet_control.errors import ControlError, fail
from fleet_control.http import FleetClient
from fleet_control.identity import (
    PROFILE_KEY,
    PROFILES_ROOT_KEY,
    load_control_buzz_identity,
    read_profile_env,
)
from fleet_control.journal import (
    JOURNAL_DIR_KEY,
    ensure_journal_dir,
    exclusive_delegation,
    fresh_record,
    read_record,
    update_record,
    write_record,
)

DELEGATION_ID_RE = re.compile(r"^dlg_[0-9a-f]{32}$")
_REQUEST_KEYS = frozenset({"worker", "task", "delegation_id"})
TASK_MAX = 8000


def parse_delegate_request(payload: Any) -> tuple[str, str, str | None]:
    """Accept only worker, task, and an optional delegation id."""
    if not isinstance(payload, dict) or any(key not in _REQUEST_KEYS for key in payload):
        raise fail("invalid_request")
    if "worker" not in payload or "task" not in payload:
        raise fail("invalid_request")
    worker = payload.get("worker")
    task = payload.get("task")
    try:
        validate_worker_name(worker if isinstance(worker, str) else "")
    except InvalidNameError:
        raise fail("invalid_name") from None
    if (
        not isinstance(task, str)
        or "\x00" in task
        or not task.strip()
        or len(task) > TASK_MAX
    ):
        raise fail("invalid_task")
    delegation_id: str | None = None
    if "delegation_id" in payload:
        supplied = payload.get("delegation_id")
        if not isinstance(supplied, str) or not DELEGATION_ID_RE.fullmatch(supplied):
            raise fail("invalid_delegation_id")
        delegation_id = supplied
    if "BUZZ_PRIVATE_KEY" in task or NSEC_RE.search(task):
        raise fail("task_rejected")
    return worker, task, delegation_id


def delegate_worker(
    payload: Any,
    *,
    environ: dict[str, str] | None = None,
    fleet_file_bytes: bytes | None = None,
    profile_env_bytes: bytes | None = None,
    profile_reader=None,
    transport=None,
    buzz_runner=None,
    journal_dir: Path | None = None,
) -> dict[str, Any]:
    """Delegate one task. The return value never includes signing material."""
    import os

    env = dict(os.environ if environ is None else environ)
    supplied_hint = _caller_delegation_id(payload)
    try:
        worker, task, supplied = parse_delegate_request(payload)
        refuse_forbidden_environment(env)
        profile = _profile_name(env)
        profiles_root = str(env.get(PROFILES_ROOT_KEY) or HERMES_PROFILES_DIR)
        directory = _journal_directory(env, profile, profiles_root, journal_dir)
    except ControlError as exc:
        raise _with_delegation_id(exc, supplied_hint) from None
    delegation_id = supplied if supplied is not None else "dlg_" + secrets.token_hex(16)
    task_hash = hashlib.sha256(task.encode("utf-8")).hexdigest()
    reader = profile_reader or read_profile_env
    runner = buzz_runner or default_buzz_runner
    try:
        with exclusive_delegation(directory, delegation_id):
            return _with_lock(
                directory=directory,
                delegation_id=delegation_id,
                worker=worker,
                task=task,
                task_hash=task_hash,
                env=env,
                profile=profile,
                profiles_root=profiles_root,
                fleet_file_bytes=fleet_file_bytes,
                profile_env_bytes=profile_env_bytes,
                profile_reader=reader,
                transport=transport,
                buzz_runner=runner,
            )
    except ControlError as exc:
        raise _with_delegation_id(exc, delegation_id) from None


def _with_lock(
    *,
    directory: Path,
    delegation_id: str,
    worker: str,
    task: str,
    task_hash: str,
    env: dict[str, str],
    profile: str,
    profiles_root: str,
    fleet_file_bytes: bytes | None,
    profile_env_bytes: bytes | None,
    profile_reader,
    transport,
    buzz_runner,
) -> dict[str, Any]:
    record = read_record(directory, delegation_id)
    if record is not None and not _same_work(record, worker, task_hash):
        raise fail("delegation_conflict")
    if record is not None and record["state"] == "accepted":
        return _receipt_from_record(record)
    if record is not None and record["state"] == "pending":
        write_record(directory, update_record(record, state="ambiguous"))
        raise fail("delegation_ambiguous")
    if record is not None and record["state"] == "ambiguous":
        raise fail("delegation_ambiguous")

    target = _target(worker, env, fleet_file_bytes, transport)
    if record is not None and record["worker_public_key_hex"] != target.public_key_hex:
        raise fail("delegation_conflict")
    if record is None:
        record = fresh_record(
            delegation_id=delegation_id,
            worker=worker,
            worker_public_key_hex=target.public_key_hex,
            task_sha256=task_hash,
            state="bound",
        )
        write_record(directory, record)

    identity = _identity(
        env,
        profile,
        profiles_root,
        profile_env_bytes,
        profile_reader,
    )
    if identity.exposes_secret(task):
        raise fail("task_rejected")
    if identity.public_key_hex == target.public_key_hex:
        raise fail("self_target")
    if identity.relay_url != target.relay_url:
        raise fail("relay_mismatch")

    binary = buzz_binary(env)
    child_env = identity.child_env(env)
    try:
        code, stdout = invoke(
            buzz_runner, open_dm_argv(binary, target.public_key_hex), child_env, b""
        )
        if code != 0:
            raise fail("dm_open_failed")
        channel_id = parse_dm_open(stdout)
    except ControlError as exc:
        if exc.code in ("dm_open_failed", "dm_open_malformed", "helper_failed"):
            write_record(directory, update_record(record, state="failed"))
        raise
    except (BuzzTimeout, BuzzOutputUnusable):
        write_record(directory, update_record(record, state="failed"))
        raise fail("dm_open_failed") from None
    except Exception:
        write_record(directory, update_record(record, state="failed"))
        raise fail("dm_open_failed") from None

    started = False

    def on_started() -> None:
        nonlocal record, started
        record = update_record(record, state="pending", channel_id=channel_id)
        write_record(directory, record)
        started = True

    try:
        code, stdout = invoke(
            buzz_runner,
            send_argv(binary, channel_id, target.public_key_hex),
            child_env,
            delegation_stdin(delegation_id, task),
            on_started=on_started,
        )
        event_id = parse_send(code, stdout)
    except ControlError as exc:
        _record_send_error(directory, record, channel_id, exc.code, started)
        raise
    except (BuzzTimeout, BuzzOutputUnusable):
        write_record(directory, update_record(record, state="ambiguous", channel_id=channel_id))
        raise fail("send_ambiguous") from None
    except Exception as exc:
        if isinstance(exc, AssertionError):
            raise
        state = "ambiguous" if started else "failed"
        write_record(directory, update_record(record, state=state, channel_id=channel_id))
        raise fail("send_ambiguous" if started else "helper_failed") from None

    record = update_record(
        record,
        state="accepted",
        channel_id=channel_id,
        event_id=event_id,
    )
    write_record(directory, record)
    return _receipt(delegation_id, worker, channel_id, event_id)


def _caller_delegation_id(payload: Any) -> str | None:
    """Return a caller-supplied id. Never allocates one."""
    if not isinstance(payload, dict):
        return None
    supplied = payload.get("delegation_id")
    if isinstance(supplied, str) and DELEGATION_ID_RE.fullmatch(supplied):
        return supplied
    return None


def _with_delegation_id(exc: ControlError, delegation_id: str | None) -> ControlError:
    """Attach an id that already exists. Do not replace one already present."""
    if delegation_id is None or exc.delegation_id is not None:
        return exc
    if not DELEGATION_ID_RE.fullmatch(delegation_id):
        return exc
    return ControlError(exc.code, exc.message, delegation_id)


def _record_send_error(
    directory: Path,
    record: dict[str, Any],
    channel_id: str,
    code: str,
    started: bool,
) -> None:
    """Map a send error onto failed (not submitted) or ambiguous (uncertain)."""
    if code == "send_rejected" or (code == "helper_failed" and not started):
        state = "failed"
    elif code in ("send_ambiguous", "helper_failed"):
        state = "ambiguous"
    else:
        return
    write_record(directory, update_record(record, state=state, channel_id=channel_id))


def _same_work(record: dict[str, Any], worker: str, task_hash: str) -> bool:
    return record.get("worker") == worker and record.get("task_sha256") == task_hash


def _receipt(delegation_id: str, worker: str, channel_id: str, event_id: str) -> dict[str, Any]:
    return {
        "accepted": True,
        "delivery": "relay_accepted",
        "delegation_id": delegation_id,
        "worker": worker,
        "channel_id": channel_id,
        "event_id": event_id,
    }


def _receipt_from_record(record: dict[str, Any]) -> dict[str, Any]:
    channel_id = record.get("channel_id")
    event_id = record.get("event_id")
    worker = record.get("worker")
    delegation_id = record.get("delegation_id")
    if not all(isinstance(item, str) and item for item in (channel_id, event_id, worker, delegation_id)):
        raise fail("journal_unusable")
    if not UUID_RE.fullmatch(channel_id) or not HEX64_RE.fullmatch(event_id):
        raise fail("journal_unusable")
    if not DELEGATION_ID_RE.fullmatch(delegation_id):
        raise fail("journal_unusable")
    return _receipt(delegation_id, worker, channel_id, event_id)


def _target(worker: str, env: dict[str, str], fleet_file_bytes: bytes | None, transport):
    settings, token = load_fleet_api_settings(environ=env, file_bytes=fleet_file_bytes)
    client = FleetClient(settings, token, transport=transport)
    try:
        body = client.get_worker(worker)
    except ControlError:
        raise
    except Exception:
        raise fail("fleet_unreachable") from None
    return authorize_target(body, worker)


def _identity(env, profile, profiles_root, profile_env_bytes, profile_reader):
    if profile_env_bytes is None:
        raw = profile_reader(profile, profiles_root)
    else:
        raw = profile_env_bytes
    if not isinstance(raw, (bytes, bytearray)):
        raise fail("control_profile_unusable")
    return load_control_buzz_identity(bytes(raw))


def _profile_name(env: dict[str, str]) -> str:
    try:
        return validate_profile_name(env.get(PROFILE_KEY))
    except Exception:
        raise fail("control_profile_unusable") from None


def main(argv: list[str] | None = None, stdin: Any = None) -> int:
    """Read one JSON object from stdin. Extra argv is rejected."""
    from fleet_control.output import public_json

    args = list(sys.argv[1:] if argv is None else argv)
    source = sys.stdin.buffer if stdin is None else stdin
    try:
        if args:
            raise fail("invalid_request")
        raw = source.read(65537)
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > 65536:
            raise fail("invalid_request")
        try:
            payload = json.loads(bytes(raw).decode("utf-8"))
        except Exception:
            raise fail("invalid_request") from None
        body = delegate_worker(payload)
    except ControlError as exc:
        sys.stdout.write(public_json(exc.public_body()))
        return 1
    except Exception:
        sys.stdout.write(public_json(fail("internal_error").public_body()))
        return 1
    sys.stdout.write(public_json(body))
    return 0


def _journal_directory(
    env: dict[str, str],
    profile: str,
    profiles_root: str,
    override: Path | None,
) -> Path:
    if override is not None:
        return ensure_journal_dir(Path(override))
    configured = str(env.get(JOURNAL_DIR_KEY) or "").strip()
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            raise fail("journal_unusable")
        return ensure_journal_dir(path)
    return ensure_journal_dir(Path(profiles_root) / profile / "fleet-delegations")
