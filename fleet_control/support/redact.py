"""Reject secret-shaped JSON before it is stored or printed."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

SK_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]+")
NSEC_RE = re.compile(r"nsec1[a-z0-9]+", re.IGNORECASE)
SECRET_KEYS = frozenset(
    {
        "api_key",
        "key",
        "virtual_key",
        "token_secret",
        "password",
        "authorization",
        "litellm_master_key",
        "pve_token_secret",
        "caller_token",
        "nsec",
        "buzz_private_key",
        "nostr_private_key",
        "token_nsec",
        "buzz_relay_private_key",
        "buzz_fleet_membership_token",
    }
)
# Field names the previous safe-JSON dump refused. Keeping the check
# preserves fail-closed status and journal behavior. This is not a
# provisioner state machine.
_OUT_OF_SCOPE_KEYS = frozenset(
    {
        "buzz_ready",
        "buzz_member",
        "buzz_admitted",
        "human_required",
        "buzz_home_channel",
        "buzz_home_channel_thread_id",
    }
)


class UnsafeJsonError(ValueError):
    """JSON contains a secret-shaped field or string."""


def utc_rfc3339() -> str:
    """Current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _assert_no_secrets(obj: Any) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            lowered = str(key).lower()
            if lowered in SECRET_KEYS or lowered in _OUT_OF_SCOPE_KEYS:
                raise UnsafeJsonError("secret field is not allowed")
            _assert_no_secrets(value)
    elif isinstance(obj, list):
        for item in obj:
            _assert_no_secrets(item)
    elif isinstance(obj, str):
        if SK_KEY_RE.search(obj) or NSEC_RE.search(obj):
            raise UnsafeJsonError("secret material is not allowed")


def dump_safe_json(obj: Any) -> str:
    """Serialize ``obj``. Raise when a secret-shaped key or string is present."""
    _assert_no_secrets(obj)
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    if SK_KEY_RE.search(text) or NSEC_RE.search(text):
        raise UnsafeJsonError("secret material is not allowed")
    return text
