"""Worker-name check used by the Control HTTP client and delegate tool."""

from __future__ import annotations

import re

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")


class InvalidNameError(ValueError):
    """A worker name is not a single safe path component."""

    def __init__(self) -> None:
        super().__init__("worker name is invalid")


def validate_worker_name(name: str) -> str:
    """Return ``name`` when it matches :data:`NAME_RE`. Otherwise raise."""
    if not NAME_RE.fullmatch(name or ""):
        raise InvalidNameError()
    return name
