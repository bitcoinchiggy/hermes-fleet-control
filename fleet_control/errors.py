"""Public failures for Control-side Fleet helpers. Messages carry no secrets."""

from __future__ import annotations


MESSAGES = {
    "invalid_name": "worker name is invalid",
    "invalid_task": "task is invalid",
    "invalid_delegation_id": "delegation id is invalid",
    "invalid_request": "delegation request is invalid",
    "undeclared_worker": "worker is not declared",
    "worker_not_ready": "worker is not ready for delegation",
    "reconciliation_unsafe": "worker reconciliation is not idle",
    "buzz_identity_incomplete": "worker buzz identity is incomplete",
    "relay_mismatch": "worker relay does not match control",
    "self_target": "refusing to delegate to control's own buzz identity",
    "gateway_inactive": "worker buzz gateway is not observed active",
    "buzz_not_converged": "worker buzz profile or relay membership is not converged",
    "dm_open_failed": "buzz dm open failed",
    "dm_open_malformed": "buzz dm open response is unusable",
    "send_rejected": "buzz send was not accepted",
    "send_ambiguous": "buzz send outcome is ambiguous",
    "delegation_conflict": "delegation id is already bound to different work",
    "delegation_in_flight": "delegation is already in flight",
    "delegation_ambiguous": "delegation outcome is ambiguous",
    "control_profile_unusable": "control buzz profile is unusable",
    "forbidden_environment": "refusing to run where provisioner-only credentials are present",
    "task_rejected": "task was rejected",
    "invalid_control_env": "control env file is unusable",
    "invalid_fleet_url": "fleet API URL is not an https origin",
    "fleet_unreachable": "fleet API request failed",
    "fleet_unauthorized": "fleet API rejected the caller",
    "fleet_response_unsafe": "fleet API response is unusable",
    "journal_unusable": "delegation journal is unusable",
    "origin_unavailable": "originating conversation is unavailable",
    "origin_invalid": "originating conversation is not a safe destination",
    "coordination_channel_invalid": "coordination channel is unusable",
    "delegation_not_found": "delegation record was not found",
    "helper_failed": "fleet helper failed",
    "internal_error": "delegation failed",
}


class ControlError(Exception):
    """Fixed public failure. ``message`` must already be safe to print."""

    def __init__(self, code: str, message: str, delegation_id: str | None = None) -> None:
        self.code = code
        self.message = message
        self.delegation_id = delegation_id
        super().__init__(message)

    def __repr__(self) -> str:
        return f"ControlError({self.code!r})"

    def public_body(self) -> dict:
        body = {"accepted": False, "error": {"code": self.code, "message": self.message}}
        if self.delegation_id is not None:
            body["delegation_id"] = self.delegation_id
        return body


def fail(code: str, delegation_id: str | None = None) -> ControlError:
    """Build a public error. The message is a fixed string, not caller input."""
    try:
        message = MESSAGES[code]
    except KeyError:
        message = MESSAGES["internal_error"]
        code = "internal_error"
    return ControlError(code, message, delegation_id)
