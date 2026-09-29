"""Stdout for Control helpers. Scans for secret-shaped text before printing."""

from __future__ import annotations

import json
from typing import Any

from fleet_control.support.redact import NSEC_RE, SK_KEY_RE

from fleet_control.errors import fail


def public_json(body: dict[str, Any]) -> str:
    """One JSON line. Secret-shaped text is replaced with a fixed error."""
    text = json.dumps(body, sort_keys=True, separators=(",", ":"))
    if NSEC_RE.search(text) or SK_KEY_RE.search(text) or "BUZZ_PRIVATE_KEY" in text:
        text = json.dumps(fail("internal_error").public_body(), sort_keys=True, separators=(",", ":"))
    return text + "\n"
