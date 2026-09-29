"""Control-local delegation journal. Mode 0600. No task text and no secrets."""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from fleet_control.support.redact import dump_safe_json, utc_rfc3339

from fleet_control.errors import fail

JOURNAL_DIR_KEY = "FLEET_DELEGATION_JOURNAL_DIR"
STATES = frozenset({"bound", "failed", "pending", "ambiguous", "accepted"})
_REQUIRED = (
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
    if tuple(sorted(parsed)) != tuple(sorted(_REQUIRED)):
        raise fail("journal_unusable")
    if parsed.get("delegation_id") != delegation_id or parsed.get("state") not in STATES:
        raise fail("journal_unusable")
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
) -> dict[str, Any]:
    now = utc_rfc3339()
    return {
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


def update_record(record: dict[str, Any], **changes: Any) -> dict[str, Any]:
    updated = dict(record)
    updated.update(changes)
    updated["updated_at"] = utc_rfc3339()
    return updated
