"""Fail-closed checks against the public Fleet worker GET document.

Every fact used here is already on ``GET /v1/workers/{name}``. Delegation
does not add a mutate route and does not invent observations that the
public document does not carry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from fleet_control.support.nostr_codec import decode_npub

from fleet_control.errors import fail


@dataclass(frozen=True)
class DelegationTarget:
    """Public worker identity. No private key."""

    name: str
    public_key_hex: str
    npub: str
    relay_url: str


def canonicalize_relay(url: str) -> str:
    """Map ws/wss onto http/https and compare host, port, and path.

    Default ports are dropped. Userinfo, query, and fragment fail closed.
    """
    if not isinstance(url, str) or not url or any(ch in url for ch in ("\n", "\r", "\x00", " ")):
        raise fail("buzz_identity_incomplete")
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme == "wss":
        scheme = "https"
    elif scheme == "ws":
        scheme = "http"
    elif scheme not in ("https", "http"):
        raise fail("buzz_identity_incomplete")
    if parts.username or parts.password or parts.query or parts.fragment or not parts.hostname:
        raise fail("buzz_identity_incomplete")
    host = parts.hostname.lower()
    port = parts.port
    if (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        port = None
    path = parts.path.rstrip("/")
    host_text = f"[{host}]" if ":" in host else host
    port_text = f":{port}" if port else ""
    return f"{scheme}://{host_text}{port_text}{path}"


def authorize_target(body: dict[str, Any], requested_name: str) -> DelegationTarget:
    """Return the public target or raise a fixed ControlError."""
    if not isinstance(body, dict) or body.get("kind") != "Worker":
        raise fail("fleet_response_unsafe")
    if body.get("declared") is not True or body.get("name") != requested_name:
        raise fail("undeclared_worker")
    if body.get("tombstone") is not None:
        raise fail("worker_not_ready")
    requested = body.get("requested")
    observed = body.get("observed")
    if not isinstance(requested, dict) or requested.get("state") != "ready":
        raise fail("worker_not_ready")
    if not isinstance(observed, dict) or observed.get("state") != "ready":
        raise fail("worker_not_ready")
    reconciliation = body.get("reconciliation")
    if not isinstance(reconciliation, dict) or reconciliation.get("status") != "idle":
        raise fail("reconciliation_unsafe")
    if observed.get("buzz_configured") is not True:
        raise fail("buzz_identity_incomplete")
    public_hex = observed.get("buzz_public_key_hex")
    npub = observed.get("buzz_npub")
    relay = observed.get("buzz_relay_url")
    if not isinstance(public_hex, str) or len(public_hex) != 64 or public_hex != public_hex.lower():
        raise fail("buzz_identity_incomplete")
    if any(ch not in "0123456789abcdef" for ch in public_hex):
        raise fail("buzz_identity_incomplete")
    if not isinstance(npub, str):
        raise fail("buzz_identity_incomplete")
    try:
        decoded = decode_npub(npub).hex()
    except Exception:
        raise fail("buzz_identity_incomplete") from None
    if decoded != public_hex:
        raise fail("buzz_identity_incomplete")
    if not isinstance(relay, str):
        raise fail("buzz_identity_incomplete")
    try:
        canonical = canonicalize_relay(relay)
    except Exception as exc:
        if getattr(exc, "code", None) == "buzz_identity_incomplete":
            raise
        raise fail("buzz_identity_incomplete") from None
    if observed.get("buzz_profile_published") is not True or observed.get("buzz_relay_member") is not True:
        raise fail("buzz_not_converged")
    if observed.get("buzz_gateway_active") is not True:
        raise fail("gateway_inactive")
    return DelegationTarget(
        name=requested_name,
        public_key_hex=public_hex,
        npub=npub,
        relay_url=canonical,
    )
