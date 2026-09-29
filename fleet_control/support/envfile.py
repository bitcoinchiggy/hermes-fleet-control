"""Read ``KEY=value`` assignments. Quotes are not stripped. Nothing is written."""

from __future__ import annotations

import re

_ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class EnvFileError(ValueError):
    """The env bytes or the requested key cannot be parsed."""


def env_assignment_values(existing: bytes, key: str) -> list[str]:
    """Return every ``KEY=`` value in env bytes, in file order.

    Duplicate assignments are preserved so callers can fail closed.
    Values are the raw text after ``=`` (quotes are not stripped).
    """
    if not isinstance(key, str) or not _ENV_KEY_RE.match(key):
        raise EnvFileError("invalid env key")
    if not isinstance(existing, (bytes, bytearray)):
        raise EnvFileError("existing env must be bytes")
    raw = bytes(existing)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise EnvFileError("existing env is not UTF-8") from None
    if "\x00" in text:
        raise EnvFileError("existing env is not UTF-8")
    match = re.compile(rf"^(?:export\s+)?{re.escape(key)}\s*=")
    values: list[str] = []
    for line in text.splitlines():
        body = line.lstrip()
        found = match.match(body)
        if found:
            values.append(body[found.end() :])
    return values
