"""``ensure_worker``: PUT /v1/workers/{name}/ensure with an empty object."""

from __future__ import annotations

import os
import sys
from typing import Any

from fleet_control.config import load_fleet_api_settings
from fleet_control.errors import ControlError, fail
from fleet_control.http import FleetClient
from fleet_control.output import public_json


def ensure_worker(
    name: str,
    *,
    environ: dict[str, str] | None = None,
    file_bytes: bytes | None = None,
    transport=None,
) -> dict[str, Any]:
    """Ask Fleet to ensure one worker. The body is exactly ``{}``."""
    env = os.environ if environ is None else environ
    settings, token = load_fleet_api_settings(environ=env, file_bytes=file_bytes)
    client = FleetClient(settings, token, transport=transport)
    return client.ensure_worker(name)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) != 1:
            raise fail("invalid_name")
        body = ensure_worker(args[0])
    except ControlError as exc:
        sys.stdout.write(public_json(exc.public_body()))
        return 1
    except Exception:
        sys.stdout.write(public_json(fail("helper_failed").public_body()))
        return 1
    sys.stdout.write(public_json(body))
    return 0
