"""Pinned-FD access to a named Hermes profile ``.env``.

``destination`` is a profile name, not a filesystem path. After the
profile directory is opened, reads and the allowlist replace use that
directory FD and ``O_NOFOLLOW``. Delegation reads. Only the inbound
allowlist command replaces the file, and it must keep ``BUZZ_PRIVATE_KEY``.
"""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

from fleet_control.support.names import NAME_RE

# Default Hermes profile root when Control does not set an override.
HERMES_PROFILES_DIR = "/home/hermes/.hermes/profiles"

ERR_INVALID_DESTINATION = "invalid destination"
ERR_PROFILE_NOT_FOUND = "profile not found"
ERR_UNSAFE_ENV_TARGET = "unsafe env target"
ERR_SECRET_WRITE_FAILED = "secret write failed"

ENV_FILENAME = ".env"
MAX_ENV_BYTES = 1024 * 1024
_TMP_PREFIX = ".hf-env-"
_TMP_SUFFIX = ".tmp"
_TMP_ATTEMPTS = 16


class ProfileEnvError(ValueError):
    """Fixed public failure. Never includes file contents."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.public_message = message

    def __repr__(self) -> str:
        return f"ProfileEnvError({self.public_message!r})"


def validate_profile_name(destination: object) -> str:
    """Accept a Hermes profile name. Reject paths and traversal.

    Whole-name ``.`` / ``..`` are rejected. Substring ``..`` inside an
    otherwise valid name is one path component, not traversal.
    """
    if not isinstance(destination, str) or not destination:
        raise ProfileEnvError(ERR_INVALID_DESTINATION)
    if destination in {".", ".."}:
        raise ProfileEnvError(ERR_INVALID_DESTINATION)
    if os.path.isabs(destination):
        raise ProfileEnvError(ERR_INVALID_DESTINATION)
    if any(ch in destination for ch in ("/", "\\", "\x00")):
        raise ProfileEnvError(ERR_INVALID_DESTINATION)
    if any(ch.isspace() or ord(ch) < 32 for ch in destination):
        raise ProfileEnvError(ERR_INVALID_DESTINATION)
    if not NAME_RE.fullmatch(destination):
        raise ProfileEnvError(ERR_INVALID_DESTINATION)
    if Path(destination).name != destination:
        raise ProfileEnvError(ERR_INVALID_DESTINATION)
    return destination


class OpenedHermesProfile:
    """Profile directory pinned by FD. ``read_env`` returns secret-bearing bytes."""

    def __init__(self, root_fd: int, profile_fd: int) -> None:
        self._root_fd = root_fd
        self._profile_fd = profile_fd
        self._closed = False

    def read_env(self) -> bytes:
        """Return ``.env`` bytes. Caller must not log or print them."""
        self._require_open()
        return _read_existing_env(self._profile_fd)

    def replace_env(self, new_bytes: bytes) -> None:
        """Replace ``.env`` via a same-directory temp file and ``os.replace``."""
        self._require_open()
        if not isinstance(new_bytes, (bytes, bytearray)):
            raise ProfileEnvError(ERR_SECRET_WRITE_FAILED)
        _atomic_replace_env(self._profile_fd, bytes(new_bytes))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _close_fd(self._profile_fd)
        _close_fd(self._root_fd)

    def _require_open(self) -> None:
        if self._closed:
            raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)

    def __enter__(self) -> OpenedHermesProfile:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __repr__(self) -> str:
        return "OpenedHermesProfile(<fd>)"


def open_named_profile(
    destination: object,
    *,
    profiles_root: str | Path = HERMES_PROFILES_DIR,
) -> OpenedHermesProfile:
    """Open an existing named profile with ``O_DIRECTORY | O_NOFOLLOW``."""
    name = validate_profile_name(destination)
    root_fd: int | None = None
    profile_fd: int | None = None
    mapped: str | None = None
    try:
        root_fd = _open_profiles_root(Path(profiles_root))
        profile_fd = _open_profile_dir(root_fd, name)
    except ProfileEnvError as exc:
        mapped = exc.public_message
    if mapped is not None:
        _close_fd(profile_fd)
        _close_fd(root_fd)
        raise ProfileEnvError(mapped)
    if root_fd is None or profile_fd is None:
        _close_fd(profile_fd)
        _close_fd(root_fd)
        raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)
    return OpenedHermesProfile(root_fd, profile_fd)


def _open_flags(*bits: int) -> int:
    flags = 0
    for bit in bits:
        flags |= bit
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    return flags


def _open_profiles_root(profiles_root: Path) -> int:
    flags = _open_flags(os.O_RDONLY, os.O_DIRECTORY)
    fd: int | None = None
    missing = False
    unsafe = False
    try:
        fd = os.open(str(profiles_root), flags)
    except FileNotFoundError:
        missing = True
    except OSError:
        unsafe = True
    if missing:
        raise ProfileEnvError(ERR_PROFILE_NOT_FOUND)
    if unsafe or fd is None:
        raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode):
        _close_fd(fd)
        raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)
    return fd


def _open_profile_dir(root_fd: int, name: str) -> int:
    flags = _open_flags(os.O_RDONLY, os.O_DIRECTORY)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd: int | None = None
    missing = False
    unsafe = False
    try:
        fd = os.open(name, flags, dir_fd=root_fd)
    except FileNotFoundError:
        missing = True
    except OSError:
        unsafe = True
    if missing:
        raise ProfileEnvError(ERR_PROFILE_NOT_FOUND)
    if unsafe or fd is None:
        raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode):
        _close_fd(fd)
        raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)
    return fd


def _read_existing_env(profile_fd: int) -> bytes:
    flags = _open_flags(os.O_RDONLY)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    fd: int | None = None
    missing = False
    unsafe = False
    try:
        fd = os.open(ENV_FILENAME, flags, dir_fd=profile_fd)
    except FileNotFoundError:
        missing = True
    except OSError:
        unsafe = True
    if missing:
        return b""
    if unsafe or fd is None:
        raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)
    data: bytes | None = None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            unsafe = True
        else:
            chunks = bytearray()
            too_big = False
            while True:
                piece = os.read(fd, 8192)
                if not piece:
                    break
                chunks.extend(piece)
                if len(chunks) > MAX_ENV_BYTES:
                    too_big = True
                    break
            if too_big:
                unsafe = True
            else:
                data = bytes(chunks)
    except Exception:
        unsafe = True
        data = None
    finally:
        _close_fd(fd)
    if unsafe or data is None:
        raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)
    if b"\x00" in data:
        raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)
    utf8_ok = False
    try:
        data.decode("utf-8")
        utf8_ok = True
    except UnicodeDecodeError:
        utf8_ok = False
    if not utf8_ok:
        raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)
    return data


def _create_exclusive_temp(profile_fd: int) -> tuple[int, str]:
    flags = _open_flags(os.O_WRONLY, os.O_CREAT, os.O_EXCL)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    for _ in range(_TMP_ATTEMPTS):
        name = f"{_TMP_PREFIX}{secrets.token_hex(8)}{_TMP_SUFFIX}"
        fd: int | None = None
        exists = False
        failed = False
        try:
            fd = os.open(name, flags, 0o600, dir_fd=profile_fd)
        except FileExistsError:
            exists = True
        except OSError:
            failed = True
        if exists:
            continue
        if failed or fd is None:
            break
        chmod_failed = False
        try:
            os.fchmod(fd, 0o600)
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o600:
                chmod_failed = True
        except OSError:
            chmod_failed = True
        if chmod_failed:
            _close_fd(fd)
            _unlink_in_dir(profile_fd, name)
            break
        return fd, name
    raise ProfileEnvError(ERR_SECRET_WRITE_FAILED)


def _refuse_env_entry_if_present_unsafe(profile_fd: int) -> None:
    missing = False
    unsafe = False
    st = None
    try:
        st = os.lstat(ENV_FILENAME, dir_fd=profile_fd)
    except FileNotFoundError:
        missing = True
    except OSError:
        unsafe = True
    if missing:
        return
    if unsafe or st is None:
        raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise ProfileEnvError(ERR_UNSAFE_ENV_TARGET)


def _atomic_replace_env(profile_fd: int, new_bytes: bytes) -> None:
    tmp_fd: int | None = None
    tmp_name: str | None = None
    write_error = False
    replaced = False
    try:
        tmp_fd, tmp_name = _create_exclusive_temp(profile_fd)
        view = memoryview(new_bytes)
        written = 0
        while written < len(new_bytes):
            count = os.write(tmp_fd, view[written:])
            if count <= 0:
                raise OSError("short write")
            written += count
        os.fsync(tmp_fd)
        os.close(tmp_fd)
        tmp_fd = None
        _refuse_env_entry_if_present_unsafe(profile_fd)
        os.replace(tmp_name, ENV_FILENAME, src_dir_fd=profile_fd, dst_dir_fd=profile_fd)
        replaced = True
        tmp_name = None
    except ProfileEnvError:
        raise
    except Exception:
        write_error = True
    finally:
        _close_fd(tmp_fd)
        if tmp_name is not None and not replaced:
            _unlink_in_dir(profile_fd, tmp_name)
    if write_error:
        raise ProfileEnvError(ERR_SECRET_WRITE_FAILED)


def _unlink_in_dir(dir_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=dir_fd)
    except OSError:
        pass


def _close_fd(fd: int | None) -> None:
    if fd is None:
        return
    try:
        os.close(fd)
    except OSError:
        pass
