"""Submit one deprovision, then read status.

The reservation is durable before the POST and stores the worker
identity read on that call. A later call for a different VM, provenance,
or public key does not send. An uncertain result is not sent again
unless the caller asks for the documented retry after that outcome.
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

RETIRE_JOURNAL_DIR = "FLEET_RETIRE_JOURNAL_DIR"
_STATES = frozenset({"reserved", "accepted", "ambiguous", "refused"})
_RECORD_KEYS = frozenset(
    {"worker", "state", "refusal_code", "confirm_retained", "binding", "created_at", "updated_at"}
)
_BINDING_KEYS = frozenset({"git_sha", "vmid", "public_key_hex", "onboarding_id"})
_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ONBOARDING_ID = re.compile(r"^onb_[0-9a-f]{32}$")
_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ERROR_KEYS = frozenset({"code", "message", "retryable", "worker"})
_REQUEST_CODES = frozenset({"invalid_request", "invalid_name", "invalid_worker", "invalid_role"})
_RETRYABLE = frozenset(
    {
        "reconciliation_in_progress",
        "rename_in_progress",
        "coordination_retirement_refused",
        "fleet_unauthorized",
    }
)
_REFUSAL_MESSAGES = {
    "retained_worker": "retained worker retirement requires explicit confirmation",
    "reconciliation_in_progress": "another reconciliation holds this worker",
    "rename_in_progress": "a rename is in progress",
    "coordination_retirement_refused": "coordination retirement was refused",
    "undeclared_worker": "worker is not declared",
    "invalid_request": "retirement request is invalid",
    "invalid_name": "worker name is invalid",
    "invalid_worker": "worker declaration is invalid",
    "invalid_role": "worker role is invalid",
    "fleet_unauthorized": "fleet API rejected the caller",
}


def retire_worker(
    name: str,
    *,
    confirm_retained: bool = False,
    retry: bool = False,
    environ: dict[str, str] | None = None,
    file_bytes: bytes | None = None,
    transport=None,
    journal_dir: Path | None = None,
) -> dict[str, Any]:
    """Retire one inspected worker through the deprovision route."""
    try:
        validate_worker_name(name)
    except InvalidNameError:
        raise fail("invalid_name") from None
    if confirm_retained not in (True, False) or retry not in (True, False):
        raise fail("retire_request_invalid")
    if confirm_retained and retry:
        raise fail("retire_request_invalid")
    env = os.environ if environ is None else environ
    settings, token = load_fleet_api_settings(environ=env, file_bytes=file_bytes)
    client = FleetClient(settings, token, transport=transport)
    directory = _resolve_dir(env, journal_dir)
    with _exclusive(directory, name):
        return _locked(
            name,
            client=client,
            directory=directory,
            token=token,
            confirm_retained=confirm_retained,
            retry=retry,
        )


def _locked(
    name: str,
    *,
    client: FleetClient,
    directory: Path,
    token: str,
    confirm_retained: bool,
    retry: bool,
) -> dict[str, Any]:
    record = _read(directory, name)
    if record is None:
        return _first(
            name,
            client=client,
            directory=directory,
            token=token,
            confirm_retained=confirm_retained,
            retry=retry,
        )
    document = _status_document(client, name)
    if not _identity_matches(record["binding"], document):
        raise fail("retire_identity_changed")
    if confirm_retained:
        return _confirm(record, document, client=client, directory=directory, token=token)
    if retry:
        return _retry(record, document, client=client, directory=directory, token=token)
    return _report(record, document, directory=directory, token=token)


def _first(
    name: str,
    *,
    client: FleetClient,
    directory: Path,
    token: str,
    confirm_retained: bool,
    retry: bool,
) -> dict[str, Any]:
    if retry:
        raise fail("retire_retry_unavailable")
    document = client.get_worker(name)
    binding = _binding(name, document)
    if _terminal(document):
        return document
    if document.get("retained") is True and not confirm_retained:
        raise fail("retained_worker", detail=document)
    if confirm_retained and document.get("retained") is not True:
        raise fail("retained_confirmation_mismatch")
    created = utc_rfc3339()
    record = _blank(name, "reserved", None, created, created, confirm_retained, binding)
    _write(directory, record, token)
    return _submit(client, directory, record, token)


def _report(
    record: dict[str, Any],
    document: dict[str, Any],
    *,
    directory: Path,
    token: str,
) -> dict[str, Any]:
    if record["state"] == "refused":
        raise _stored_refusal(record, document)
    if _terminal(document):
        if record["state"] != "accepted":
            _transition(directory, record, "accepted", None, token)
        return document
    if record["state"] == "accepted":
        return document
    raise fail("retire_ambiguous", detail=document)


def _confirm(
    record: dict[str, Any],
    document: dict[str, Any],
    *,
    client: FleetClient,
    directory: Path,
    token: str,
) -> dict[str, Any]:
    if record["state"] in {"accepted", "ambiguous", "reserved"} or record["confirm_retained"] is True:
        return _report(record, document, directory=directory, token=token)
    if record["state"] != "refused" or record["refusal_code"] != "retained_worker":
        raise _stored_refusal(record, document)
    if document.get("retained") is not True or _terminal(document):
        raise fail("retained_confirmation_mismatch")
    record = _blank(
        record["worker"],
        "reserved",
        None,
        record["created_at"],
        utc_rfc3339(),
        True,
        record["binding"],
    )
    _write(directory, record, token)
    return _submit(client, directory, record, token)


def _retry(
    record: dict[str, Any],
    document: dict[str, Any],
    *,
    client: FleetClient,
    directory: Path,
    token: str,
) -> dict[str, Any]:
    if record["state"] == "accepted" or _terminal(document):
        if record["state"] != "accepted":
            _transition(directory, record, "accepted", None, token)
        return document
    if record["state"] == "refused" and record["refusal_code"] not in _RETRYABLE:
        raise _stored_refusal(record, document)
    if not _live(document):
        raise fail("retire_identity_changed")
    record = _blank(
        record["worker"],
        "reserved",
        None,
        record["created_at"],
        utc_rfc3339(),
        record["confirm_retained"] is True,
        record["binding"],
    )
    _write(directory, record, token)
    return _submit(client, directory, record, token)


def _submit(client: FleetClient, directory: Path, record: dict[str, Any], token: str) -> dict[str, Any]:
    try:
        status, body = client.deprovision_worker(
            record["worker"], confirm_retained=record["confirm_retained"] is True
        )
    except ControlError as exc:
        _transport_failure(directory, record, exc, token)
        raise
    return _classify(directory, record, status, body, token)


def _transport_failure(directory: Path, record: dict[str, Any], exc: ControlError, token: str) -> None:
    if exc.code == "fleet_unauthorized":
        _transition(directory, record, "refused", "fleet_unauthorized", token)
        raise fail("fleet_unauthorized") from None
    _transition(directory, record, "ambiguous", None, token)
    if exc.code == "fleet_response_unsafe":
        raise fail("fleet_response_unsafe") from None
    raise fail("retire_ambiguous") from None


def _classify(
    directory: Path,
    record: dict[str, Any],
    status: int,
    body: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    code = _error_code(body)
    if status in (200, 202) and _worker_shape(body, record["worker"]) and _identity_matches(
        record["binding"], body
    ):
        _transition(directory, record, "accepted", None, token)
        return body
    if status == 404 and code == "undeclared_worker":
        _transition(directory, record, "refused", "undeclared_worker", token)
        raise fail("undeclared_worker")
    if status == 400 and code in _REQUEST_CODES:
        _transition(directory, record, "refused", code, token)
        return _raise_refusal(code)
    if status == 409 and code in _REFUSAL_MESSAGES and _error_shape(body):
        _transition(directory, record, "refused", code, token)
        return _raise_refusal(code)
    _transition(directory, record, "ambiguous", None, token)
    raise fail("retire_ambiguous")


def _raise_refusal(code: str) -> dict[str, Any]:
    message = _REFUSAL_MESSAGES.get(code)
    if message is None:
        raise fail("retire_ambiguous")
    if code in {"undeclared_worker", "invalid_name", "fleet_unauthorized"}:
        raise fail(code)
    raise ControlError(code, message)


def _stored_refusal(record: dict[str, Any], document: dict[str, Any] | None = None) -> ControlError:
    code = record.get("refusal_code")
    if not isinstance(code, str):
        return fail("retire_journal_unusable")
    message = _REFUSAL_MESSAGES.get(code)
    if message is None:
        return fail("retire_journal_unusable")
    if code in {"undeclared_worker", "invalid_name", "fleet_unauthorized"}:
        return fail(code, detail=document)
    return ControlError(code, message, detail=document)


def _status_document(client: FleetClient, name: str) -> dict[str, Any]:
    try:
        return client.get_worker(name)
    except ControlError as exc:
        if exc.code == "fleet_response_unsafe":
            raise
        raise fail("retire_ambiguous") from None


def _binding(name: str, document: dict[str, Any]) -> dict[str, Any]:
    if not _worker_shape(document, name):
        raise fail("retire_identity_unbound")
    if not isinstance(document.get("retained"), bool):
        raise fail("retire_identity_unbound")
    provenance = document.get("provenance")
    observed = document.get("observed")
    if not isinstance(provenance, dict) or not isinstance(observed, dict):
        raise fail("retire_identity_unbound")
    git_sha = provenance.get("git_sha")
    vmid = observed.get("vmid")
    public_key = observed.get("buzz_public_key_hex")
    if not isinstance(git_sha, str) or _SHA.fullmatch(git_sha) is None:
        raise fail("retire_identity_unbound")
    if isinstance(vmid, bool) or not isinstance(vmid, int) or vmid < 1:
        raise fail("retire_identity_unbound")
    if not isinstance(public_key, str) or _HEX64.fullmatch(public_key) is None:
        raise fail("retire_identity_unbound")
    onboarding_id = _onboarding_id(document)
    return {
        "git_sha": git_sha,
        "vmid": vmid,
        "public_key_hex": public_key,
        "onboarding_id": onboarding_id,
    }


def _onboarding_id(document: dict[str, Any]) -> str | None:
    onboarding = document.get("onboarding")
    if onboarding is None:
        return None
    if not isinstance(onboarding, dict):
        raise fail("retire_identity_unbound")
    ident = onboarding.get("id")
    if not isinstance(ident, str) or _ONBOARDING_ID.fullmatch(ident) is None:
        raise fail("retire_identity_unbound")
    return ident


def _worker_shape(document: dict[str, Any], name: str) -> bool:
    return (
        isinstance(document, dict)
        and document.get("api_version") == "v1"
        and document.get("kind") == "Worker"
        and document.get("name") == name
    )


def _terminal(document: dict[str, Any]) -> bool:
    if isinstance(document.get("tombstone"), dict):
        return True
    observed = document.get("observed")
    if isinstance(observed, dict) and observed.get("state") in {"absent", "deprovisioning"}:
        return True
    requested = document.get("requested")
    return isinstance(requested, dict) and requested.get("state") == "absent"


def _live(document: dict[str, Any]) -> bool:
    return not _terminal(document)


def _identity_matches(binding: dict[str, Any], document: dict[str, Any]) -> bool:
    if not isinstance(document, dict):
        return False
    provenance = document.get("provenance")
    observed = document.get("observed")
    if not isinstance(provenance, dict) or not isinstance(observed, dict):
        return False
    if provenance.get("git_sha") != binding.get("git_sha") or observed.get("vmid") != binding.get("vmid"):
        return False
    public_key = observed.get("buzz_public_key_hex")
    if public_key != binding.get("public_key_hex"):
        if not (public_key is None and _identity_may_be_absent(document)):
            return False
    try:
        onboarding_id = _onboarding_id(document)
    except ControlError:
        return False
    bound_onboarding = binding.get("onboarding_id")
    if onboarding_id != bound_onboarding and not (onboarding_id is None and bound_onboarding is not None):
        return False
    return True


def _identity_may_be_absent(document: dict[str, Any]) -> bool:
    if isinstance(document.get("tombstone"), dict):
        return True
    observed = document.get("observed")
    return isinstance(observed, dict) and observed.get("state") == "absent"


def _error_code(body: dict[str, Any]) -> str | None:
    if not _error_shape(body):
        return None
    code = body["error"].get("code")
    if not isinstance(code, str) or _CODE.fullmatch(code) is None:
        return None
    return code


def _error_shape(body: dict[str, Any]) -> bool:
    if not isinstance(body, dict) or body.get("api_version") != "v1":
        return False
    error = body.get("error")
    if not isinstance(error, dict) or set(error) - _ERROR_KEYS:
        return False
    return isinstance(error.get("code"), str) and isinstance(error.get("message"), str)


def _resolve_dir(env: dict[str, str], override: Path | None) -> Path:
    if override is not None:
        return _private_dir(Path(override))
    configured = str(env.get(RETIRE_JOURNAL_DIR) or "").strip()
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            raise fail("retire_journal_unusable")
        return _private_dir(path)
    try:
        profile = validate_profile_name(env.get(PROFILE_ENV))
    except Exception:
        raise fail("control_profile_unusable") from None
    root = str(env.get(PROFILES_ROOT_ENV) or HERMES_PROFILES_DIR)
    return _private_dir(Path(root) / profile / "fleet-retirements")


def _private_dir(path: Path) -> Path:
    try:
        return ensure_journal_dir(path)
    except ControlError as exc:
        if exc.code == "journal_unusable":
            raise fail("retire_journal_unusable") from None
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
        raise fail("retire_journal_unusable") from None
    if blocked:
        if fd is not None:
            os.close(fd)
        raise fail("retire_in_flight")
    try:
        yield
    finally:
        if fd is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def _blank(
    name: str,
    state: str,
    refusal: str | None,
    created: str,
    updated: str,
    confirm_retained: bool,
    binding: dict[str, Any],
) -> dict[str, Any]:
    return {
        "worker": name,
        "state": state,
        "refusal_code": refusal,
        "confirm_retained": confirm_retained,
        "binding": binding,
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
        _blank(
            record["worker"],
            state,
            refusal,
            record["created_at"],
            utc_rfc3339(),
            record["confirm_retained"] is True,
            record["binding"],
        ),
        token,
    )


def _read(directory: Path, name: str) -> dict[str, Any] | None:
    path = _journal_path(directory, name)
    if path.is_symlink():
        raise fail("retire_journal_unusable")
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        raise fail("retire_journal_unusable") from None
    if len(raw) > 8192:
        raise fail("retire_journal_unusable")
    try:
        parsed = json.loads(raw.decode("utf-8"))
        dump_safe_json(parsed)
    except Exception:
        raise fail("retire_journal_unusable") from None
    if not isinstance(parsed, dict) or set(parsed) != _RECORD_KEYS:
        raise fail("retire_journal_unusable")
    if parsed.get("worker") != name or parsed.get("state") not in _STATES:
        raise fail("retire_journal_unusable")
    if parsed.get("confirm_retained") not in (True, False):
        raise fail("retire_journal_unusable")
    if not isinstance(parsed.get("created_at"), str) or _STAMP.fullmatch(parsed["created_at"]) is None:
        raise fail("retire_journal_unusable")
    if not isinstance(parsed.get("updated_at"), str) or _STAMP.fullmatch(parsed["updated_at"]) is None:
        raise fail("retire_journal_unusable")
    refusal = parsed.get("refusal_code")
    if parsed["state"] == "refused":
        if refusal not in _REFUSAL_MESSAGES:
            raise fail("retire_journal_unusable")
    elif refusal is not None:
        raise fail("retire_journal_unusable")
    binding = parsed.get("binding")
    if not isinstance(binding, dict) or set(binding) != _BINDING_KEYS:
        raise fail("retire_journal_unusable")
    if not isinstance(binding.get("git_sha"), str) or _SHA.fullmatch(binding["git_sha"]) is None:
        raise fail("retire_journal_unusable")
    vmid = binding.get("vmid")
    if isinstance(vmid, bool) or not isinstance(vmid, int) or vmid < 1:
        raise fail("retire_journal_unusable")
    if (
        not isinstance(binding.get("public_key_hex"), str)
        or _HEX64.fullmatch(binding["public_key_hex"]) is None
    ):
        raise fail("retire_journal_unusable")
    onboarding_id = binding.get("onboarding_id")
    if onboarding_id is not None and (
        not isinstance(onboarding_id, str) or _ONBOARDING_ID.fullmatch(onboarding_id) is None
    ):
        raise fail("retire_journal_unusable")
    return parsed


def _write(directory: Path, record: dict[str, Any], token: str) -> None:
    name = record.get("worker")
    if not isinstance(name, str):
        raise fail("retire_journal_unusable")
    try:
        payload = (dump_safe_json(record) + "\n").encode("utf-8")
    except Exception:
        raise fail("retire_journal_unusable") from None
    lowered = payload.lower()
    if b"BUZZ_PRIVATE_KEY" in payload or b"nsec1" in lowered or b"authorization" in lowered:
        raise fail("retire_journal_unusable")
    if token and token.encode("utf-8") in payload:
        raise fail("retire_journal_unusable")
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
                raise fail("retire_journal_unusable")
            view = view[written:]
        os.fsync(fd)
    except OSError:
        raise fail("retire_journal_unusable") from None
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
        raise fail("retire_journal_unusable") from None


def _journal_path(directory: Path, name: str) -> Path:
    path = directory / f"{name}.json"
    if path.parent != directory:
        raise fail("retire_journal_unusable")
    return path


def parse_retire_request(raw: str) -> tuple[bool, bool]:
    """Read an explicit confirmation or retry. An empty body is the default."""
    if raw.strip() == "":
        return False, False
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise fail("retire_request_invalid") from None
    if not isinstance(payload, dict):
        raise fail("retire_request_invalid")
    allowed = {"confirm_retained", "retry"}
    if any(key not in allowed for key in payload):
        raise fail("retire_request_invalid")
    confirm = payload.get("confirm_retained", False)
    retry = payload.get("retry", False)
    if confirm not in (True, False) or retry not in (True, False):
        raise fail("retire_request_invalid")
    return confirm, retry


def main(argv: list[str] | None = None) -> int:
    from fleet_control.output import public_json

    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) != 1:
            raise fail("invalid_name")
        raw = "" if sys.stdin.isatty() else sys.stdin.read()
        confirm, retry = parse_retire_request(raw)
        body = retire_worker(args[0], confirm_retained=confirm, retry=retry)
    except ControlError as exc:
        sys.stdout.write(public_json(exc.public_body()))
        return 1
    except Exception:
        sys.stdout.write(public_json(fail("helper_failed").public_body()))
        return 1
    sys.stdout.write(public_json(body))
    return 0
