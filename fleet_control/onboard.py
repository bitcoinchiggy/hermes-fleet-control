"""Submit one onboarding POST, then read progress with GET.

The reservation is durable before the request is sent. A crash after
that write must not send another POST. Recognized refusals keep their
public codes. Uncertain results stay uncertain.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import secrets
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from fleet_control.support.names import InvalidNameError, validate_worker_name
from fleet_control.support.redact import dump_safe_json, utc_rfc3339

from fleet_control.config import load_fleet_api_settings
from fleet_control.errors import ControlError, fail
from fleet_control.http import FleetClient
from fleet_control.journal import PROFILE_ENV, PROFILES_ROOT_ENV, ensure_journal_dir
from fleet_control.support.profile_env import HERMES_PROFILES_DIR, validate_profile_name

ONBOARD_JOURNAL_DIR = "FLEET_ONBOARD_JOURNAL_DIR"
_STATES = frozenset({"reserved", "accepted", "ambiguous", "refused"})
_RECORD_KEYS = frozenset({"worker", "state", "refusal_code", "created_at", "updated_at"})
_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ONBOARDING_ID = re.compile(r"^onb_[0-9a-f]{32}$")
_TOKEN = re.compile(r"^[a-z0-9_]{1,64}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_NPUB = re.compile(r"^npub1[a-z0-9]{6,90}$")
_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ONBOARDING_KEYS = frozenset(
    {
        "id",
        "status",
        "stage",
        "identity",
        "expected_public_key_hex",
        "expected_npub",
        "vmid",
        "git_sha",
        "retired_reason",
        "error",
        "updated_at",
    }
)
_ONBOARDING_STATUS = frozenset({"running", "blocked", "complete", "retired"})
_RETIRED_REASONS = frozenset({"deprovision_accepted", "tombstone_present"})
_REFUSAL_MESSAGES = {
    "alias_exists": "onboarding was refused because an alias exists",
    "ambiguous_infrastructure": "onboarding was refused because infrastructure is ambiguous",
    "credential_replacement_required": "onboarding was refused because credential replacement is required",
    "enrollment_ambiguous": "onboarding enrollment is ambiguous",
    "enrollment_failed": "onboarding enrollment failed",
    "enrollment_unconfigured": "onboarding enrollment is not configured",
    "ensure_failed": "onboarding ensure did not reach ready",
    "existing_worker": "onboarding was refused because the worker already exists",
    "fleet_capacity": "onboarding was refused because fleet capacity is exhausted",
    "gateway_already_active": "onboarding was refused because the gateway is already active",
    "hermes_revision_unverified": "onboarding was refused because the Hermes revision is unverified",
    "identity_ambiguous": "onboarding identity is ambiguous",
    "identity_generation_failed": "onboarding identity could not be generated",
    "identity_injection_failed": "onboarding identity injection failed",
    "identity_mismatch": "onboarding identity does not match",
    "identity_unreadable": "onboarding identity could not be read",
    "inference_unverified": "onboarding inference is unverified",
    "onboarding_blocked": "onboarding is blocked",
    "onboarding_retired": "onboarding is retired",
    "ownership_mismatch": "onboarding ownership does not match",
    "relay_origin_mismatch": "onboarding relay origin does not match",
    "rename_in_progress": "onboarding was refused because a rename is in progress",
    "template_missing": "onboarding was refused because the template is missing",
    "tombstone_present": "onboarding was refused because a tombstone is present",
    "worker_not_ready": "onboarding was refused because the worker is not ready",
    "worker_replaced": "onboarding is bound to a different worker",
}
_REQUEST_CODES = frozenset({"invalid_request", "invalid_name", "invalid_worker", "invalid_role"})
_REQUEST_MESSAGES = {
    "invalid_request": "onboarding request is invalid",
    "invalid_name": "worker name is invalid",
    "invalid_worker": "worker declaration is invalid",
    "invalid_role": "worker role is invalid",
}
_ERROR_KEYS = frozenset({"code", "message", "retryable", "worker"})
_TOP_KEYS = frozenset({"api_version", "error", "onboarding"})


def onboard_worker(
    name: str,
    *,
    environ: dict[str, str] | None = None,
    file_bytes: bytes | None = None,
    transport=None,
    journal_dir: Path | None = None,
) -> dict[str, Any]:
    """Onboard one declared name, or read its later progress. Never retries a POST."""
    if not isinstance(name, str):
        raise fail("invalid_name")
    try:
        validate_worker_name(name)
    except InvalidNameError:
        raise fail("invalid_name") from None
    env = dict(os.environ if environ is None else environ)
    settings, token = load_fleet_api_settings(environ=env, file_bytes=file_bytes)
    directory = _resolve_dir(env, journal_dir)
    client = FleetClient(settings, token, transport=transport)
    with _exclusive(directory, name):
        return _locked(client, directory, name, token)


def _locked(client: FleetClient, directory: Path, name: str, token: str) -> dict[str, Any]:
    record = _read(directory, name)
    if record is None:
        created = utc_rfc3339()
        record = _blank(name, "reserved", None, created, created)
        _write(directory, record, token)
        return _submit(client, directory, name, record, token)
    return _follow(client, name, record)


def _submit(
    client: FleetClient,
    directory: Path,
    name: str,
    record: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    try:
        status, body = client.onboard_worker(name)
    except ControlError as exc:
        _transport_failure(directory, record, exc, token)
        raise
    except Exception:
        _transition(directory, record, "ambiguous", None, token)
        raise fail("onboard_ambiguous") from None
    kind, code = _classify(name, status, body)
    if kind == "accept":
        _transition(directory, record, "accepted", None, token)
        return body
    if kind == "refuse":
        _transition(directory, record, "refused", code, token)
        raise _refusal(code)
    if kind == "clear":
        _delete(directory, name)
        raise _request_failure(code)
    _transition(directory, record, "ambiguous", None, token)
    raise fail("onboard_ambiguous")


def _transport_failure(directory: Path, record: dict[str, Any], exc: ControlError, token: str) -> None:
    """A definite auth rejection can be attempted later. Anything else cannot."""
    if exc.code == "fleet_unauthorized":
        _delete(directory, record["worker"])
        return
    _transition(directory, record, "ambiguous", None, token)
    if exc.code == "fleet_response_unsafe":
        return
    raise fail("onboard_ambiguous")


def _follow(client: FleetClient, name: str, record: dict[str, Any]) -> dict[str, Any]:
    """Read the public worker. Do not POST."""
    document, get_error = _read_progress(client, name)
    state = record["state"]
    if state == "refused":
        raise _refusal(str(record["refusal_code"]))
    if state == "accepted":
        if document is not None:
            return document
        if get_error is not None:
            raise get_error
        raise fail("fleet_response_unsafe")
    raise fail("onboard_ambiguous")


def _read_progress(
    client: FleetClient, name: str
) -> tuple[dict[str, Any] | None, ControlError | None]:
    try:
        document = client.get_worker(name)
    except ControlError as exc:
        return None, exc
    if _progress_document(name, document):
        return document, None
    return None, fail("fleet_response_unsafe")


def _classify(name: str, status: int, body: dict[str, Any]) -> tuple[str, str]:
    if status in (200, 202) and _accepted_document(name, body):
        return "accept", ""
    if status == 404:
        return "clear", "undeclared_worker"
    if status == 400:
        return "clear", _request_code(name, body)
    if status == 409:
        code = _refusal_code(name, body)
        if code is not None:
            return "refuse", code
    return "ambiguous", ""


def _request_code(name: str, body: dict[str, Any]) -> str:
    code = _error_code(name, body, _REQUEST_CODES)
    if code is None:
        return "invalid_request"
    return code


def _refusal_code(name: str, body: dict[str, Any]) -> str | None:
    return _error_code(name, body, frozenset(_REFUSAL_MESSAGES))


def _error_code(name: str, body: dict[str, Any], allowed: frozenset[str]) -> str | None:
    if not _error_envelope(name, body):
        return None
    code = body["error"]["code"]
    if code not in allowed:
        return None
    return code


def _error_envelope(name: str, body: dict[str, Any]) -> bool:
    if set(body) - _TOP_KEYS:
        return False
    if "api_version" in body and body.get("api_version") != "v1":
        return False
    error = body.get("error")
    if not isinstance(error, dict) or set(error) - _ERROR_KEYS:
        return False
    code = error.get("code")
    message = error.get("message")
    if not isinstance(code, str) or _CODE.fullmatch(code) is None:
        return False
    if not isinstance(message, str) or not message or len(message) > 200 or any(ord(ch) < 32 for ch in message):
        return False
    if "retryable" in error and not isinstance(error.get("retryable"), bool):
        return False
    if "worker" in error and error.get("worker") != name:
        return False
    if "onboarding" in body and not _valid_onboarding(body.get("onboarding")):
        return False
    return True


def _accepted_document(name: str, body: dict[str, Any]) -> bool:
    if body.get("api_version") != "v1" or body.get("kind") != "Worker":
        return False
    if body.get("name") != name or body.get("declared") is not True:
        return False
    return _valid_onboarding(body.get("onboarding"))


def _progress_document(name: str, body: Any) -> bool:
    if not isinstance(body, dict):
        return False
    if body.get("api_version") != "v1" or body.get("kind") != "Worker" or body.get("name") != name:
        return False
    if "onboarding" not in body or body.get("onboarding") is None:
        return True
    return _valid_onboarding(body.get("onboarding"))


def _valid_onboarding(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != _ONBOARDING_KEYS:
        return False
    if not isinstance(value.get("id"), str) or _ONBOARDING_ID.fullmatch(value["id"]) is None:
        return False
    if value.get("status") not in _ONBOARDING_STATUS:
        return False
    if not _optional_token(value.get("stage")) or not _optional_token(value.get("identity")):
        return False
    if not _optional_match(value.get("expected_public_key_hex"), _HEX64):
        return False
    if not _optional_match(value.get("expected_npub"), _NPUB):
        return False
    if not _optional_match(value.get("git_sha"), _SHA):
        return False
    vmid = value.get("vmid")
    if vmid is not None and (isinstance(vmid, bool) or not isinstance(vmid, int) or not 1 <= vmid <= 2**31 - 1):
        return False
    if value.get("retired_reason") not in _RETIRED_REASONS and value.get("retired_reason") is not None:
        return False
    if not _optional_stamp(value.get("updated_at")):
        return False
    error = value.get("error")
    if error is None:
        return True
    if not isinstance(error, dict) or set(error) != {"code", "message"}:
        return False
    code = error.get("code")
    message = error.get("message")
    if not isinstance(code, str) or _CODE.fullmatch(code) is None:
        return False
    return isinstance(message, str) and 0 < len(message) <= 200 and all(ord(ch) >= 32 for ch in message)


def _optional_token(value: Any) -> bool:
    return value is None or (isinstance(value, str) and _TOKEN.fullmatch(value) is not None)


def _optional_match(value: Any, pattern: re.Pattern[str]) -> bool:
    return value is None or (isinstance(value, str) and pattern.fullmatch(value) is not None)


def _optional_stamp(value: Any) -> bool:
    return value is None or (isinstance(value, str) and _STAMP.fullmatch(value) is not None)


def _refusal(code: str) -> ControlError:
    try:
        message = _REFUSAL_MESSAGES[code]
    except KeyError:
        return fail("onboard_ambiguous")
    return ControlError(code, message)


def _request_failure(code: str) -> ControlError:
    if code == "undeclared_worker":
        return fail(code)
    try:
        return ControlError(code, _REQUEST_MESSAGES[code])
    except KeyError:
        return fail("invalid_request")


def _resolve_dir(env: dict[str, str], override: Path | None) -> Path:
    if override is not None:
        return _private_dir(Path(override))
    configured = str(env.get(ONBOARD_JOURNAL_DIR) or "").strip()
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            raise fail("onboard_journal_unusable")
        return _private_dir(path)
    try:
        profile = validate_profile_name(env.get(PROFILE_ENV))
    except Exception:
        raise fail("control_profile_unusable") from None
    root = str(env.get(PROFILES_ROOT_ENV) or HERMES_PROFILES_DIR)
    return _private_dir(Path(root) / profile / "fleet-onboarding")


def _private_dir(path: Path) -> Path:
    try:
        return ensure_journal_dir(path)
    except ControlError as exc:
        if exc.code == "journal_unusable":
            raise fail("onboard_journal_unusable") from None
        raise


@contextmanager
def _exclusive(directory: Path, name: str) -> Iterator[None]:
    lock_path = directory / f"{name}.lock"
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
        raise fail("onboard_journal_unusable") from None
    if blocked:
        if fd is not None:
            os.close(fd)
        raise fail("onboard_in_flight")
    try:
        yield
    finally:
        if fd is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def _blank(name: str, state: str, refusal: str | None, created: str, updated: str) -> dict[str, Any]:
    return {
        "worker": name,
        "state": state,
        "refusal_code": refusal,
        "created_at": created,
        "updated_at": updated,
    }


def _transition(
    directory: Path,
    record: dict[str, Any],
    state: str,
    refusal: str | None,
    token: str,
) -> None:
    _write(
        directory,
        _blank(record["worker"], state, refusal, record["created_at"], utc_rfc3339()),
        token,
    )


def _read(directory: Path, name: str) -> dict[str, Any] | None:
    path = _journal_path(directory, name)
    if path.is_symlink():
        raise fail("onboard_journal_unusable")
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        raise fail("onboard_journal_unusable") from None
    if len(raw) > 4096:
        raise fail("onboard_journal_unusable")
    try:
        parsed = json.loads(raw.decode("utf-8"))
        dump_safe_json(parsed)
    except Exception:
        raise fail("onboard_journal_unusable") from None
    if not isinstance(parsed, dict) or set(parsed) != _RECORD_KEYS:
        raise fail("onboard_journal_unusable")
    if parsed.get("worker") != name or parsed.get("state") not in _STATES:
        raise fail("onboard_journal_unusable")
    if not _optional_stamp(parsed.get("created_at")) or parsed.get("created_at") is None:
        raise fail("onboard_journal_unusable")
    if not _optional_stamp(parsed.get("updated_at")) or parsed.get("updated_at") is None:
        raise fail("onboard_journal_unusable")
    refusal = parsed.get("refusal_code")
    if parsed["state"] == "refused":
        if refusal not in _REFUSAL_MESSAGES:
            raise fail("onboard_journal_unusable")
    elif refusal is not None:
        raise fail("onboard_journal_unusable")
    return parsed


def _write(directory: Path, record: dict[str, Any], token: str) -> None:
    name = record.get("worker")
    if not isinstance(name, str):
        raise fail("onboard_journal_unusable")
    try:
        payload = (dump_safe_json(record) + "\n").encode("utf-8")
    except Exception:
        raise fail("onboard_journal_unusable") from None
    lowered = payload.lower()
    if b"BUZZ_PRIVATE_KEY" in payload or b"nsec1" in lowered or b"authorization" in lowered:
        raise fail("onboard_journal_unusable")
    if token and token.encode("utf-8") in payload:
        raise fail("onboard_journal_unusable")
    path = _journal_path(directory, name)
    tmp = directory / f".{name}.{secrets.token_hex(4)}.tmp"
    fd: int | None = None
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.fchmod(fd, 0o600)
        view = payload
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise fail("onboard_journal_unusable")
            view = view[written:]
        os.fsync(fd)
    except OSError:
        raise fail("onboard_journal_unusable") from None
    finally:
        if fd is not None:
            os.close(fd)
    try:
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
        dir_fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise fail("onboard_journal_unusable") from None


def _delete(directory: Path, name: str) -> None:
    path = _journal_path(directory, name)
    if path.is_symlink():
        raise fail("onboard_journal_unusable")
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        raise fail("onboard_journal_unusable") from None
    dir_fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _journal_path(directory: Path, name: str) -> Path:
    path = directory / f"{name}.json"
    if path.parent != directory:
        raise fail("onboard_journal_unusable")
    return path


def main(argv: list[str] | None = None) -> int:
    from fleet_control.output import public_json

    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) != 1:
            raise fail("invalid_name")
        body = onboard_worker(args[0])
    except ControlError as exc:
        sys.stdout.write(public_json(exc.public_body()))
        return 1
    except Exception:
        sys.stdout.write(public_json(fail("helper_failed").public_body()))
        return 1
    sys.stdout.write(public_json(body))
    return 0
