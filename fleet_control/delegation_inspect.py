"""Read one local delegation record. This is not a task viewer."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from fleet_control.errors import ControlError, fail
from fleet_control.journal import read_record, resolve_journal_dir
from fleet_control.output import public_json

_DELEGATION_ID_RE = re.compile(r"^dlg_[0-9a-f]{32}$")


def show_delegation(directory: Path, delegation_id: str) -> dict[str, Any]:
    """Return the journal record that links a task to its private exchanges."""
    if not isinstance(delegation_id, str) or not _DELEGATION_ID_RE.fullmatch(delegation_id):
        raise fail("invalid_delegation_id")
    record = read_record(directory, delegation_id)
    if record is None:
        raise fail("delegation_not_found")
    return dict(record)


def main(argv: list[str] | None = None) -> int:
    """Print one delegation record as a single JSON line."""
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) != 1:
            raise fail("invalid_request")
        import os

        body = show_delegation(resolve_journal_dir(dict(os.environ)), args[0])
    except ControlError as exc:
        sys.stdout.write(public_json(exc.public_body()))
        return 1
    except Exception:
        sys.stdout.write(public_json(fail("internal_error").public_body()))
        return 1
    sys.stdout.write(public_json(body))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
