"""Control-local delegation journal. Mode 0600. No secrets.

Records written by this revision store the task and the trusted human
origin next to the worker identity and the accepted event. Records
written before that stay readable and are not backfilled.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from fleet_control.support.profile_env import HERMES_PROFILES_DIR, validate_profile_name
from fleet_control.support.redact import dump_safe_json, utc_rfc3339

from fleet_control.errors import ControlError, fail

JOURNAL_DIR_KEY = "FLEET_DELEGATION_JOURNAL_DIR"
PROFILE_ENV = "FLEET_CONTROL_HERMES_PROFILE"
PROFILES_ROOT_ENV = "FLEET_CONTROL_PROFILES_ROOT"
STATES = frozenset({"bound", "failed", "pending", "ambiguous", "accepted"})
MAX_JOURNAL_FILES = 1024
MAX_REPLY_EVENTS = 32
TASK_MAX = 8000
_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_LEGACY = (
    "delegation_id",
    "worker",
    "worker_public_key_hex",
    "channel_id",
    "event_id",
    "task_sha256",
    "state",
    "created_at",
    "updated_at",
)
_CURRENT = _LEGACY + (
    "task",
    "origin_platform",
    "origin_chat_id",
    "origin_session_key",
    "reply_event_ids",
)
_ROUTED = _CURRENT + (
    "origin_thread_id",
    "origin_message_id",
    "origin_chat_type",
    "origin_scope_id",
    "origin_user_id",
)
_DELIVERY_STATES = frozenset({"pending", "inflight", "completed"})
_DELIVERY_ITEM_KEYS = frozenset({"event_id", "state", "claim_id", "owner", "pid"})
_LEGACY_KEYS = tuple(sorted(_LEGACY))
_CURRENT_KEYS = tuple(sorted(_CURRENT))
_ROUTED_KEYS = tuple(sorted(_ROUTED))
_TRACKED_CURRENT_KEYS = tuple(sorted(_CURRENT + ("reply_deliveries",)))
_TRACKED_ROUTED_KEYS = tuple(sorted(_ROUTED + ("reply_deliveries",)))
_READABLE_KEYS = frozenset(
    {_LEGACY_KEYS, _CURRENT_KEYS, _ROUTED_KEYS, _TRACKED_CURRENT_KEYS, _TRACKED_ROUTED_KEYS}
)
_CHAT_TYPES = frozenset({"dm", "group", "channel", "thread"})
_CLAIM_RE = re.compile(r"^[0-9a-f]{32}$")


def ensure_journal_dir(path: Path) -> Path:
    """Create a private directory. Symlinks and missing parents are refused."""
    parent = path.parent
    if path.is_symlink() or parent.is_symlink() or not parent.is_dir():
        raise fail("journal_unusable")
    try:
        path.mkdir(mode=0o700, exist_ok=True)
    except OSError:
        raise fail("journal_unusable") from None
    os.chmod(path, 0o700)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise fail("journal_unusable")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise fail("journal_unusable")
    return path


@contextmanager
def exclusive_delegation(directory: Path, delegation_id: str) -> Iterator[None]:
    """Hold a non-blocking exclusive lock for one delegation id."""
    lock_path = directory / f"{delegation_id}.lock"
    fd: int | None = None
    blocked = False
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        blocked = True
    except OSError:
        if fd is not None:
            os.close(fd)
        raise fail("journal_unusable") from None
    if blocked:
        if fd is not None:
            os.close(fd)
        raise fail("delegation_in_flight")
    try:
        yield
    finally:
        if fd is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


@contextmanager
def exclusive_delegation_wait(directory: Path, delegation_id: str, timeout: float = 5.0) -> Iterator[None]:
    """Serialize reply claims. A busy lock is retried until ``timeout``."""
    deadline = time.monotonic() + timeout
    while True:
        entered = False
        try:
            with exclusive_delegation(directory, delegation_id):
                entered = True
                yield
            return
        except ControlError as exc:
            if entered or exc.code != "delegation_in_flight" or time.monotonic() >= deadline:
                raise
            time.sleep(0.005)


def read_record(directory: Path, delegation_id: str) -> dict[str, Any] | None:
    path = directory / f"{delegation_id}.json"
    if path.is_symlink():
        raise fail("journal_unusable")
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        raise fail("journal_unusable") from None
    if len(raw) > 65536:
        raise fail("journal_unusable")
    try:
        parsed = json.loads(raw.decode("utf-8"))
        dump_safe_json(parsed)
    except Exception:
        raise fail("journal_unusable") from None
    if not isinstance(parsed, dict):
        raise fail("journal_unusable")
    keys = tuple(sorted(parsed))
    if keys not in _READABLE_KEYS:
        raise fail("journal_unusable")
    if parsed.get("delegation_id") != delegation_id or parsed.get("state") not in STATES:
        raise fail("journal_unusable")
    _validate_identity(parsed)
    if keys in (_CURRENT_KEYS, _ROUTED_KEYS, _TRACKED_CURRENT_KEYS, _TRACKED_ROUTED_KEYS):
        _validate_current(parsed)
    if keys in (_ROUTED_KEYS, _TRACKED_ROUTED_KEYS):
        _validate_routed(parsed)
    if keys in (_TRACKED_CURRENT_KEYS, _TRACKED_ROUTED_KEYS):
        _validate_deliveries(parsed)
    return parsed


def write_record(directory: Path, record: dict[str, Any]) -> None:
    """Atomically replace one journal file and fsync it into place."""
    delegation_id = record.get("delegation_id")
    if not isinstance(delegation_id, str):
        raise fail("journal_unusable")
    try:
        payload = (dump_safe_json(record) + "\n").encode("utf-8")
    except Exception:
        raise fail("journal_unusable") from None
    if b"BUZZ_PRIVATE_KEY" in payload or b"nsec1" in payload.lower():
        raise fail("journal_unusable")
    final_name = f"{delegation_id}.json"
    tmp_name = f".{delegation_id}.{secrets.token_hex(4)}.tmp"
    tmp_path = directory / tmp_name
    fd: int | None = None
    try:
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.fchmod(fd, 0o600)
        view = payload
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise fail("journal_unusable")
            view = view[written:]
        os.fsync(fd)
    except OSError:
        raise fail("journal_unusable") from None
    finally:
        if fd is not None:
            os.close(fd)
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, directory / final_name)
    os.chmod(directory / final_name, 0o600)
    dir_fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def fresh_record(
    *,
    delegation_id: str,
    worker: str,
    worker_public_key_hex: str,
    task_sha256: str,
    state: str,
    task: str | None = None,
    origin_platform: str | None = None,
    origin_chat_id: str | None = None,
    origin_session_key: str | None = None,
    origin_thread_id: str | None = None,
    origin_message_id: str | None = None,
    origin_chat_type: str | None = None,
    origin_scope_id: str | None = None,
    origin_user_id: str | None = None,
) -> dict[str, Any]:
    now = utc_rfc3339()
    record: dict[str, Any] = {
        "delegation_id": delegation_id,
        "worker": worker,
        "worker_public_key_hex": worker_public_key_hex,
        "channel_id": None,
        "event_id": None,
        "task_sha256": task_sha256,
        "state": state,
        "created_at": now,
        "updated_at": now,
    }
    if task is None and origin_platform is None and origin_chat_id is None and origin_session_key is None:
        return record
    if (
        task is None
        or origin_platform is None
        or origin_chat_id is None
        or origin_session_key is None
    ):
        raise fail("journal_unusable")
    record["task"] = task
    record["origin_platform"] = origin_platform
    record["origin_chat_id"] = origin_chat_id
    record["origin_session_key"] = origin_session_key
    record["reply_event_ids"] = []
    routed = (
        origin_thread_id,
        origin_message_id,
        origin_chat_type,
        origin_scope_id,
        origin_user_id,
    )
    if all(value is None for value in routed):
        return record
    if any(value is None for value in routed):
        raise fail("journal_unusable")
    record["origin_thread_id"] = origin_thread_id
    record["origin_message_id"] = origin_message_id
    record["origin_chat_type"] = origin_chat_type
    record["origin_scope_id"] = origin_scope_id
    record["origin_user_id"] = origin_user_id
    return record


def resolve_journal_dir(env: Mapping[str, str], override: Path | None = None) -> Path:
    """Return the private journal directory for this helper process."""
    if override is not None:
        return ensure_journal_dir(Path(override))
    configured = str(env.get(JOURNAL_DIR_KEY) or "").strip()
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            raise fail("journal_unusable")
        return ensure_journal_dir(path)
    try:
        profile = validate_profile_name(env.get(PROFILE_ENV))
    except Exception:
        raise fail("control_profile_unusable") from None
    root = str(env.get(PROFILES_ROOT_ENV) or HERMES_PROFILES_DIR)
    return ensure_journal_dir(Path(root) / profile / "fleet-delegations")


def iter_records(directory: Path) -> list[dict[str, Any]]:
    """Read every delegation file. A symlink or a corrupt file fails closed."""
    try:
        paths = []
        for path in sorted(directory.glob("dlg_*.json")):
            if path.is_symlink():
                raise fail("journal_unusable")
            if path.is_file():
                paths.append(path)
    except OSError:
        raise fail("journal_unusable") from None
    if len(paths) > MAX_JOURNAL_FILES:
        raise fail("journal_unusable")
    return [record for path in paths if (record := read_record(directory, path.stem)) is not None]


def _validate_identity(parsed: Mapping[str, Any]) -> None:
    worker_key = parsed.get("worker_public_key_hex")
    if not isinstance(worker_key, str) or not _HEX64_RE.fullmatch(worker_key):
        raise fail("journal_unusable")
    for field, pattern in (("channel_id", None), ("event_id", _HEX64_RE)):
        value = parsed.get(field)
        if value is None:
            continue
        if field == "channel_id":
            if not isinstance(value, str) or not value or len(value) > 256:
                raise fail("journal_unusable")
            continue
        if not isinstance(value, str) or pattern is None or not pattern.fullmatch(value):
            raise fail("journal_unusable")


def _validate_current(parsed: Mapping[str, Any]) -> None:
    task = parsed.get("task")
    digest = parsed.get("task_sha256")
    if (
        not isinstance(task, str)
        or "\x00" in task
        or not task.strip()
        or len(task) > TASK_MAX
        or not isinstance(digest, str)
        or hashlib.sha256(task.encode("utf-8")).hexdigest() != digest
    ):
        raise fail("journal_unusable")
    replies = parsed.get("reply_event_ids")
    if (
        not isinstance(replies, list)
        or len(replies) > MAX_REPLY_EVENTS
        or len(set(replies)) != len(replies)
        or any(not isinstance(item, str) or not _HEX64_RE.fullmatch(item) for item in replies)
    ):
        raise fail("journal_unusable")


def _validate_deliveries(parsed: Mapping[str, Any]) -> None:
    deliveries = parsed.get("reply_deliveries")
    replies = parsed.get("reply_event_ids")
    if not isinstance(deliveries, list) or len(deliveries) > MAX_REPLY_EVENTS:
        raise fail("journal_unusable")
    seen: set[str] = set()
    for item in deliveries:
        if not isinstance(item, dict) or set(item) != _DELIVERY_ITEM_KEYS:
            raise fail("journal_unusable")
        event_id = item.get("event_id")
        state = item.get("state")
        claim_id = item.get("claim_id")
        owner = item.get("owner")
        pid = item.get("pid")
        if (
            not isinstance(event_id, str)
            or not _HEX64_RE.fullmatch(event_id)
            or event_id in seen
            or not isinstance(replies, list)
            or event_id not in replies
            or state not in _DELIVERY_STATES
            or not isinstance(claim_id, str)
            or not _CLAIM_RE.fullmatch(claim_id)
            or not isinstance(owner, str)
            or (owner and not _CLAIM_RE.fullmatch(owner))
            or isinstance(pid, bool)
            or not isinstance(pid, int)
            or pid < 0
            or pid >= 2**31
        ):
            raise fail("journal_unusable")
        if state == "inflight":
            if not owner or pid <= 0:
                raise fail("journal_unusable")
        elif owner or pid:
            raise fail("journal_unusable")
        seen.add(event_id)


def reply_hold_dir(directory: Path) -> Path:
    """Private directory for one inflight reply body. Not a delegation record."""
    path = directory / "reply-holds"
    if path.is_symlink():
        raise fail("journal_unusable")
    try:
        path.mkdir(mode=0o700, exist_ok=True)
    except OSError:
        raise fail("journal_unusable") from None
    os.chmod(path, 0o700)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise fail("journal_unusable")
    return path


def write_reply_hold(directory: Path, delegation_id: str, event_id: str, payload: Mapping[str, Any]) -> None:
    """Atomically store the worker text needed to retry one unfinished reply."""
    folder = reply_hold_dir(directory)
    try:
        body = (dump_safe_json(dict(payload)) + "\n").encode("utf-8")
    except Exception:
        raise fail("journal_unusable") from None
    if len(body) > 65536 or b"BUZZ_PRIVATE_KEY" in body or b"nsec1" in body.lower():
        raise fail("journal_unusable")
    final = folder / f"{delegation_id}.{event_id}.json"
    if final.is_symlink():
        raise fail("journal_unusable")
    tmp = folder / f".{delegation_id}.{event_id}.{secrets.token_hex(4)}.tmp"
    fd: int | None = None
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.fchmod(fd, 0o600)
        view = body
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise fail("journal_unusable")
            view = view[written:]
        os.fsync(fd)
    except OSError:
        raise fail("journal_unusable") from None
    finally:
        if fd is not None:
            os.close(fd)
    os.chmod(tmp, 0o600)
    os.replace(tmp, final)
    os.chmod(final, 0o600)


def read_reply_hold(directory: Path, delegation_id: str, event_id: str) -> dict[str, Any] | None:
    path = reply_hold_dir(directory) / f"{delegation_id}.{event_id}.json"
    if path.is_symlink():
        raise fail("journal_unusable")
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        raise fail("journal_unusable") from None
    if len(raw) > 65536:
        raise fail("journal_unusable")
    try:
        parsed = json.loads(raw.decode("utf-8"))
        dump_safe_json(parsed)
    except Exception:
        raise fail("journal_unusable") from None
    if not isinstance(parsed, dict):
        raise fail("journal_unusable")
    return parsed


def delete_reply_hold(directory: Path, delegation_id: str, event_id: str) -> None:
    path = directory / "reply-holds" / f"{delegation_id}.{event_id}.json"
    if path.is_symlink():
        raise fail("journal_unusable")
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        raise fail("journal_unusable") from None


def _validate_routed(parsed: Mapping[str, Any]) -> None:
    chat_type = parsed.get("origin_chat_type")
    if not isinstance(chat_type, str) or chat_type not in _CHAT_TYPES:
        raise fail("journal_unusable")
    for field in ("origin_thread_id", "origin_message_id", "origin_scope_id", "origin_user_id"):
        value = parsed.get(field)
        if not isinstance(value, str) or len(value) > 256:
            raise fail("journal_unusable")
        if value and any(ord(char) < 32 or char.isspace() for char in value):
            raise fail("journal_unusable")
        if value and ("nsec1" in value.lower() or "buzz_private_key" in value.lower()):
            raise fail("journal_unusable")


def update_record(record: dict[str, Any], **changes: Any) -> dict[str, Any]:
    updated = dict(record)
    updated.update(changes)
    updated["updated_at"] = utc_rfc3339()
    return updated
