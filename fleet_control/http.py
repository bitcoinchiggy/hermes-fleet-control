"""Control-local Fleet HTTP client. GET for status, PUT {} for ensure.

Delegation uses GET only. The caller token stays in the Authorization
header and is never written into errors, URLs, or logs.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib import error, request

from fleet_control.support.names import InvalidNameError, validate_worker_name
from fleet_control.support.redact import NSEC_RE, SECRET_KEYS, SK_KEY_RE, dump_safe_json

from fleet_control.config import FleetApiSettings
from fleet_control.errors import fail

Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]
MAX_BODY = 1_000_000
_FORBIDDEN_KEYS = SECRET_KEYS | frozenset({"litellm_key_token"})


def urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    *,
    timeout: float = 30,
) -> tuple[int, bytes]:
    """Perform one HTTPS request. Failures omit response text and the token."""
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read(MAX_BODY + 1)
    except error.HTTPError as exc:
        try:
            payload = exc.read(MAX_BODY + 1)
        except Exception:
            payload = b""
        return int(exc.code), payload
    except Exception:
        raise fail("fleet_unreachable") from None


class FleetClient:
    """Thin bearer client. ``token`` must not appear in ``repr``."""

    def __init__(
        self,
        settings: FleetApiSettings,
        token: str,
        *,
        transport: Transport | None = None,
    ) -> None:
        self._settings = settings
        self._token = token
        self._transport = transport or urllib_transport

    def __repr__(self) -> str:
        return f"FleetClient(url={self._settings.url!r})"

    def get_worker(self, name: str) -> dict[str, Any]:
        self._name(name)
        return self._json("GET", f"/v1/workers/{name}", None)

    def list_workers(self) -> dict[str, Any]:
        return self._json("GET", "/v1/workers", None)

    def ensure_worker(self, name: str) -> dict[str, Any]:
        self._name(name)
        return self._json("PUT", f"/v1/workers/{name}/ensure", b"{}")

    def _name(self, name: str) -> None:
        try:
            validate_worker_name(name)
        except InvalidNameError:
            raise fail("invalid_name") from None

    def _json(self, method: str, path: str, body: bytes | None) -> dict[str, Any]:
        url = self._settings.url + path
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "hermes-fleet-control",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            status, payload = self._transport(method, url, headers, body)
        except Exception as exc:
            if type(exc).__name__ == "ControlError":
                raise
            raise fail("fleet_unreachable") from None
        if self._token and self._token.encode("utf-8") in payload:
            raise fail("fleet_response_unsafe")
        if len(payload) > MAX_BODY:
            raise fail("fleet_response_unsafe")
        if status in (401, 403):
            raise fail("fleet_unauthorized")
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except Exception:
            raise fail("fleet_response_unsafe") from None
        _assert_public_json(parsed)
        if status == 404:
            raise fail("undeclared_worker")
        if status < 200 or status >= 300:
            raise fail("fleet_unreachable")
        if not isinstance(parsed, dict):
            raise fail("fleet_response_unsafe")
        return parsed


def _assert_public_json(obj: Any) -> None:
    """Reject secret-shaped Fleet payloads before they reach stdout."""
    try:
        dump_safe_json(obj)
    except Exception:
        raise fail("fleet_response_unsafe") from None
    _walk(obj)


def _walk(obj: Any) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise fail("fleet_response_unsafe")
            _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            _walk(item)
    elif isinstance(obj, str):
        if SK_KEY_RE.search(obj) or NSEC_RE.search(obj):
            raise fail("fleet_response_unsafe")
