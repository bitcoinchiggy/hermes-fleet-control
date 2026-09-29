"""``worker_status``: GET /v1/workers or GET /v1/workers/{name}."""

from __future__ import annotations

import os
import sys
from typing import Any

from fleet_control.config import load_fleet_api_settings
from fleet_control.errors import ControlError, fail
from fleet_control.http import FleetClient
from fleet_control.output import public_json


def worker_status(
    name: str | None = None,
    *,
    environ: dict[str, str] | None = None,
    file_bytes: bytes | None = None,
    transport=None,
) -> dict[str, Any]:
    """Return the public Fleet worker list, or one public worker document."""
    env = os.environ if environ is None else environ
    settings, token = load_fleet_api_settings(environ=env, file_bytes=file_bytes)
    client = FleetClient(settings, token, transport=transport)
    if name is None:
        return client.list_workers()
    return client.get_worker(name)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) > 1:
            raise fail("invalid_name")
        body = worker_status(args[0] if args else None)
    except ControlError as exc:
        sys.stdout.write(public_json(exc.public_body()))
        return 1
    except Exception:
        sys.stdout.write(public_json(fail("helper_failed").public_body()))
        return 1
    sys.stdout.write(public_json(body))
    return 0
