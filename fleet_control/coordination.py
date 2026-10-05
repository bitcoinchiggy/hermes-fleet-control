"""Optional private coordination channel for new delegations.

The id is ``fleet.coordination_channel_id`` in the Control profile's
``config.yaml``. It is a public channel UUID, not a secret and not an
environment variable. When it is absent, delegation still opens the
worker DM. When it is present, new work is a top-level kind-9 message
in that channel, mentioning the recorded worker. Records that already
have a channel id are not retargeted.
"""

from __future__ import annotations

import re
from pathlib import Path

from fleet_control.errors import fail
from fleet_control.support.profile_env import validate_profile_name

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def coordination_channel_id(profile: str, profiles_root: str) -> str | None:
    """Return the configured channel, or None when the key is absent.

    A present but unusable value fails closed. It does not fall back to a DM.
    """
    try:
        name = validate_profile_name(profile)
    except Exception:
        raise fail("coordination_channel_invalid") from None
    path = Path(profiles_root) / name / "config.yaml"
    if path.is_symlink():
        raise fail("coordination_channel_invalid")
    if not path.is_file():
        return None
    try:
        import yaml

        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        raise fail("coordination_channel_invalid") from None
    if not isinstance(loaded, dict):
        raise fail("coordination_channel_invalid")
    if "fleet" not in loaded or loaded.get("fleet") is None:
        return None
    fleet = loaded.get("fleet")
    if not isinstance(fleet, dict):
        raise fail("coordination_channel_invalid")
    if "coordination_channel_id" not in fleet:
        return None
    value = fleet.get("coordination_channel_id")
    if not isinstance(value, str) or not _UUID_RE.fullmatch(value.strip().lower()):
        raise fail("coordination_channel_invalid")
    return value.strip().lower()
