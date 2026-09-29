"""Load the Control-local Fleet API settings. Never log the caller token."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from fleet_control.support.envfile import env_assignment_values

from fleet_control.errors import fail

URL_KEY = "FLEET_PROVISIONER_URL"
TOKEN_KEY = "FLEET_PROVISIONER_CALLER_TOKEN"
ENV_FILE_KEY = "FLEET_CONTROL_ENV_FILE"
MEMBERSHIP_TOKEN_KEY = "BUZZ_FLEET_MEMBERSHIP_TOKEN"
FORBIDDEN_ENV_KEYS = frozenset(
    {
        MEMBERSHIP_TOKEN_KEY,
        "LITELLM_MASTER_KEY",
        "PVE_TOKEN_SECRET",
    }
)


@dataclass(frozen=True)
class FleetApiSettings:
    """Non-secret URL plus the caller bearer. Do not put this in repr logs."""

    url: str

    def __repr__(self) -> str:
        return f"FleetApiSettings(url={self.url!r})"


def refuse_forbidden_environment(environ: dict[str, str] | None = None) -> None:
    """Control must not hold provisioner-only credentials."""
    env = os.environ if environ is None else environ
    for key in FORBIDDEN_ENV_KEYS:
        if str(env.get(key) or "").strip():
            raise fail("forbidden_environment")


def _one_assignment(raw: bytes, key: str) -> str:
    try:
        values = env_assignment_values(raw, key)
    except Exception:
        raise fail("invalid_control_env") from None
    if len(values) != 1:
        raise fail("invalid_control_env")
    value = values[0]
    if value != value.strip() or not value or any(ch in value for ch in ("\n", "\r", "\x00", " ", "'", '"')):
        raise fail("invalid_control_env")
    return value


def _require_https_origin(url: str) -> str:
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise fail("invalid_fleet_url")
    path = parts.path.rstrip("/")
    if path not in ("", "/"):
        raise fail("invalid_fleet_url")
    port = f":{parts.port}" if parts.port else ""
    return f"https://{parts.hostname.lower()}{port}"


def load_fleet_api_settings(
    *,
    environ: dict[str, str] | None = None,
    file_bytes: bytes | None = None,
) -> tuple[FleetApiSettings, str]:
    """Return ``(settings, caller_token)``. Caller must not log the token."""
    refuse_forbidden_environment(environ)
    env = os.environ if environ is None else environ
    raw = file_bytes
    if raw is None:
        path = str(env.get(ENV_FILE_KEY) or "").strip()
        if not path:
            raise fail("invalid_control_env")
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except OSError:
            raise fail("invalid_control_env") from None
    for marker in (
        MEMBERSHIP_TOKEN_KEY.encode("ascii"),
        b"LITELLM_MASTER_KEY",
        b"PVE_TOKEN_SECRET",
        b"BUZZ_PRIVATE_KEY",
    ):
        if marker in raw:
            raise fail("forbidden_environment")
    url = _require_https_origin(_one_assignment(raw, URL_KEY))
    token = _one_assignment(raw, TOKEN_KEY)
    return FleetApiSettings(url=url), token
