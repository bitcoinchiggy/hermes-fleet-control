"""Spawn the local Buzz CLI with an argv array. Never a shell."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable
from typing import Any

from fleet_control.errors import ControlError, fail

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_BUZZ_BIN = "/usr/local/bin/buzz"
BUZZ_BIN_KEY = "FLEET_CONTROL_BUZZ_BIN"
MAX_STDOUT = 65536

BuzzRunner = Callable[..., tuple[int, bytes, bytes]]
# `messages send` exits that mean the CLI failed before it could have
# submitted the event. See parse_send.
PRE_SUBMIT_EXITS = frozenset({1, 4})


class BuzzTimeout(Exception):
    """The Buzz child exceeded its deadline. Carries no child output."""


class BuzzOutputUnusable(Exception):
    """Stdout was not a bounded response. Carries no child output."""


def buzz_binary(environ: dict[str, str]) -> str:
    configured = str(environ.get(BUZZ_BIN_KEY) or DEFAULT_BUZZ_BIN)
    if not os.path.isabs(configured) or any(ch.isspace() or ch == "\x00" for ch in configured):
        raise fail("helper_failed")
    return configured


def default_buzz_runner(
    argv: list[str],
    env: dict[str, str],
    stdin: bytes,
    on_started: Callable[[], None] | None = None,
) -> tuple[int, bytes, bytes]:
    """Run Buzz. ``shell`` is false. stderr is returned to the caller to discard.

    ``on_started`` runs only after ``Popen`` succeeds and before stdin is
    written. The child blocks in ``read_to_string`` until then, so a crash
    before ``Popen`` cannot look like an uncertain send, and stdin is not
    released until the caller has recorded that the child exists.
    """
    if not argv or not os.path.isabs(argv[0]):
        raise fail("helper_failed")
    try:
        proc = subprocess.Popen(
            list(argv),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            shell=False,
        )
    except Exception:
        raise fail("helper_failed") from None
    try:
        if on_started is not None:
            on_started()
    except Exception:
        _stop_child(proc)
        raise
    try:
        stdout, stderr = proc.communicate(input=stdin, timeout=30)
    except subprocess.TimeoutExpired:
        _stop_child(proc)
        raise BuzzTimeout() from None
    except Exception:
        _stop_child(proc)
        raise fail("helper_failed") from None
    code = proc.returncode
    if not isinstance(code, int):
        raise fail("helper_failed")
    return code, stdout or b"", stderr or b""


def invoke(
    runner: BuzzRunner,
    argv: list[str],
    env: dict[str, str],
    stdin: bytes,
    on_started: Callable[[], None] | None = None,
) -> tuple[int, bytes]:
    """Run one Buzz command and drop stderr so it cannot reach a public error."""
    try:
        code, stdout, _stderr = runner(argv, env, stdin, on_started)
    except BuzzTimeout:
        raise
    except ControlError:
        raise
    except Exception:
        raise fail("helper_failed") from None
    if not isinstance(code, int) or not isinstance(stdout, (bytes, bytearray)):
        raise fail("helper_failed")
    if len(stdout) > MAX_STDOUT:
        raise BuzzOutputUnusable()
    return code, bytes(stdout)


def _stop_child(proc: subprocess.Popen) -> None:
    """Kill a child that must not observe stdin. Output is discarded."""
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        pass


def open_dm_argv(binary: str, public_hex: str) -> list[str]:
    return [binary, "dms", "open", "--pubkey", public_hex]


def send_argv(binary: str, channel_id: str, public_hex: str) -> list[str]:
    """Address one already-authorized worker with ``--mention``.

    Buzz turns that hex pubkey into a message ``p`` tag. The value is the
    Fleet-resolved worker key, not a caller-supplied mention, channel, or
    pubkey. ``--content -`` stays last so the task remains on stdin.
    """
    if not UUID_RE.fullmatch(channel_id) or not HEX64_RE.fullmatch(public_hex):
        raise fail("helper_failed")
    return [
        binary,
        "messages",
        "send",
        "--channel",
        channel_id,
        "--mention",
        public_hex,
        "--content",
        "-",
    ]


def delegation_stdin(delegation_id: str, task: str) -> bytes:
    """Prefix the task so a leading slash cannot be a gateway command."""
    return f"[fleet-delegation {delegation_id}]\n{task}".encode("utf-8")


def parse_dm_open(stdout: bytes) -> str:
    """Return the relay DM id. ``created`` true and false are both usable."""
    body = _object(stdout, "dm_open_malformed")
    if body.get("accepted") is not True:
        raise fail("dm_open_malformed")
    dm_id = body.get("dm_id")
    if not isinstance(dm_id, str) or not UUID_RE.fullmatch(dm_id):
        raise fail("dm_open_malformed")
    created, channel_id = _created(body)
    if not isinstance(created, bool):
        raise fail("dm_open_malformed")
    if channel_id is not None and channel_id != dm_id:
        raise fail("dm_open_malformed")
    return dm_id


def parse_send(code: int, stdout: bytes) -> str:
    """Return the event id, or raise rejection / ambiguity. Never echoes stdout.

    Verified against ``buzz-cli`` ``error::exit_code`` and ``cmd_send_message``
    (kind 9 goes through ``submit_stored_event``):

    - Exit 1 is ``Usage`` or ``NotFound``. Mention mismatch, content checks,
      and channel parsing return ``Usage`` before ``submit_event``. The CLI
      prints that error on stderr and leaves stdout empty.
    - Exit 4 is ``Other``. Membership and profile mention preflight,
      ``build_message``, and ``sign_event`` return ``Other`` before
      ``submit_event``. ``sign_nip98`` also returns ``Other``, and
      ``with_retry_body`` does not retry it, so that failure aborts on the
      first attempt before HTTP ``send``. Empty stdout is the stderr-only
      error path: no acceptance object was printed.
    - Exit 2 is ``Network``, non-auth ``Relay``, and ``DeliveryUnknown``.
      Those cannot be separated by status, and ``DeliveryUnknown`` means the
      relay may already have stored the event.
    - Exit 3 is ``Auth``, ``Key``, and relay 401/403. That is not a
      pre-submit usage failure; the request may already have been sent.
    - Exit 5 is a write conflict. It is not a pre-submit ``messages send``
      result.
    - Timeout, a non-empty stdout that is not ``accepted: false``, and a
      success object that is missing a usable event id stay ambiguous.
      ``accepted: false`` is an explicit non-acceptance.
    """
    body = _json_object(stdout)
    if isinstance(body, dict) and body.get("accepted") is False:
        raise fail("send_rejected")
    if isinstance(body, dict) and body.get("accepted") is True:
        event_id = body.get("event_id")
        if code == 0 and isinstance(event_id, str) and HEX64_RE.fullmatch(event_id):
            return event_id
        raise _ambiguous()
    if code in PRE_SUBMIT_EXITS and not stdout.strip():
        raise fail("send_rejected")
    raise _ambiguous()


def _ambiguous() -> ControlError:
    return fail("send_ambiguous")


def _json_object(stdout: bytes) -> dict[str, Any] | None:
    try:
        body = json.loads(stdout.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(body, dict):
        return None
    return body


def _object(stdout: bytes, code: str) -> dict[str, Any]:
    try:
        body = json.loads(stdout.decode("utf-8"))
    except Exception:
        raise fail(code) from None
    if not isinstance(body, dict):
        raise fail(code)
    return body


def _created(body: dict[str, Any]) -> tuple[Any, str | None]:
    nested_created, channel_id = _message_response(body.get("message"))
    created = body.get("created", nested_created)
    if "created" in body and nested_created is not None and body.get("created") != nested_created:
        raise fail("dm_open_malformed")
    return created, channel_id


def _message_response(message: Any) -> tuple[Any, str | None]:
    if message is None:
        return None, None
    if not isinstance(message, str) or not message.startswith("response:"):
        return None, None
    try:
        payload = json.loads(message[len("response:") :])
    except Exception:
        raise fail("dm_open_malformed") from None
    if not isinstance(payload, dict):
        raise fail("dm_open_malformed")
    channel_id = payload.get("channel_id")
    if channel_id is not None and not isinstance(channel_id, str):
        raise fail("dm_open_malformed")
    return payload.get("created"), channel_id
