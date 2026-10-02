"""Effective Buzz authorization for one Hermes profile.

Inspected against Nous Research hermes-agent ``be5e9f72c6681af9dfb75bf480f08844f1499949``.
The profile ``.env`` is not the whole allowlist.

``BUZZ_ALLOW_ALL_USERS`` is allow-all only when its value is ``true``, ``1``,
or ``yes``. An absent variable is not that. The same rule applies to
``allow_all_users`` in ``config.yaml`` and to ``GATEWAY_ALLOW_ALL_USERS``.
An open grant is not a finite set of humans.

When ``BUZZ_ALLOWED_USERS`` is absent or blank, Hermes does not deny every
human. The gateway still authorizes pairing approvals
(``platforms/pairing/buzz-approved.json`` and the legacy ``pairing/`` copy)
and, when no Buzz allowlist is configured, ``config.yaml``
``allow_from`` plus nostr-shaped ``GATEWAY_ALLOWED_USERS`` entries.
``config.yaml`` ``allowed_users`` is the Buzz allowlist when the env list is
blank. A non-empty Buzz allowlist is also the adapter intake filter, so a
pairing approval outside that list is not currently effective and is not
copied in.

Unreadable configuration or pairing state fails closed. This module returns
public hex keys only.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from fleet_control.support.envfile import EnvFileError, env_assignment_values
from fleet_control.support.nostr_codec import InvalidNostrKeyError, decode_npub
from fleet_control.support.profile_env import OpenedHermesProfile, ProfileEnvError

_TRUTHY = frozenset({"true", "1", "yes"})
_ALLOW_ALL = "BUZZ_ALLOW_ALL_USERS"
_ALLOWED_USERS = "BUZZ_ALLOWED_USERS"
_GATEWAY_ALLOW_ALL = "GATEWAY_ALLOW_ALL_USERS"
_GATEWAY_ALLOWED = "GATEWAY_ALLOWED_USERS"
_PUBHEX = re.compile(r"^[0-9a-f]{64}$")
_SECRET = re.compile("nsec1|sk-|" + "xp" + "rv", re.IGNORECASE)

_CONFIG_PARTS = ("config.yaml",)
_GATEWAY_JSON_PARTS = ("gateway.json",)
_PAIRING_PARTS = (
    ("platforms", "pairing", "buzz-approved.json"),
    ("pairing", "buzz-approved.json"),
)


class HermesAuthzError(ValueError):
    """Secret-free failure. Existing authorization was not established."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.public_message = message

    def __repr__(self) -> str:
        return f"HermesAuthzError({self.public_message!r})"


@dataclass(frozen=True)
class EffectiveBuzzAuthorization:
    """Public view of who can already reach Control's Buzz gateway."""

    allow_all_users: bool
    allow_all_source: str
    humans: tuple[str, ...]
    human_sources: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.allow_all_users:
            raise HermesAuthzError("allow_all_users is not a control authorization")
        if self.allow_all_source not in {"env", "config", "hermes_default"}:
            raise HermesAuthzError("existing authorization cannot be established")


def _unquote(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _assignments(raw: bytes, key: str) -> list[str]:
    try:
        values = env_assignment_values(raw, key)
    except EnvFileError:
        raise HermesAuthzError("existing authorization cannot be established") from None
    if len(values) > 1:
        raise HermesAuthzError("existing authorization cannot be established")
    return values


def _optional_env(raw: bytes, key: str) -> str | None:
    """One assignment, or ``None`` when the variable is absent or blank."""
    values = _assignments(raw, key)
    if not values:
        return None
    text = _unquote(values[0]).strip()
    if not text:
        return None
    if _SECRET.search(text):
        raise HermesAuthzError("refusing secret material")
    return text


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY
    raise HermesAuthzError("existing authorization cannot be established")


def _identity(token: object, *, strict: bool, casefold: bool = True) -> str | None:
    """Hex or npub to lowercase hex.

    Buzz adapter allowlists fold case. The gateway's global allowlist does
    not, so ``casefold=False`` keeps only an already-lowercase hex entry.
    """
    if isinstance(token, bool) or not isinstance(token, str):
        raise HermesAuthzError("existing authorization cannot be established")
    text = token.strip()
    if not text:
        return None
    if text == "*" or _SECRET.search(text):
        raise HermesAuthzError("existing authorization cannot be established")
    lowered = text.lower()
    if lowered.startswith("npub1"):
        try:
            return decode_npub(lowered).hex()
        except (InvalidNostrKeyError, ValueError):
            raise HermesAuthzError("existing authorization cannot be established") from None
    candidate = lowered if casefold else text
    if _PUBHEX.fullmatch(candidate):
        return candidate
    if strict:
        raise HermesAuthzError("existing authorization cannot be established")
    return None


def _identity_list(value: object, *, strict: bool, casefold: bool = True) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                value = parsed
            else:
                value = stripped.split(",")
        else:
            value = stripped.split(",")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        items = list(value)
    else:
        raise HermesAuthzError("existing authorization cannot be established")
    found: list[str] = []
    seen: set[str] = set()
    for item in items:
        identity = _identity(item, strict=strict, casefold=casefold)
        if identity is None or identity in seen:
            continue
        seen.add(identity)
        found.append(identity)
    return tuple(found)


def _mapping(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise HermesAuthzError("existing authorization cannot be established")
    return dict(value)


def _load_structured(raw: bytes | None, kind: str) -> dict[str, object] | None:
    if raw is None:
        return None
    if kind == "yaml":
        try:
            import yaml
        except ImportError:
            raise HermesAuthzError("existing authorization cannot be established") from None
        try:
            loaded = yaml.safe_load(raw)
        except Exception:
            raise HermesAuthzError("existing authorization cannot be established") from None
    else:
        try:
            loaded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HermesAuthzError("existing authorization cannot be established") from None
    if loaded is None:
        return {}
    mapped = _mapping(loaded)
    if mapped is None:
        raise HermesAuthzError("existing authorization cannot be established")
    return mapped


def _buzz_extra(document: Mapping[str, object] | None) -> dict[str, object]:
    """Merge Buzz platform blocks in Hermes's config order. Later keys win."""
    if not document:
        return {}
    gateway = document.get("gateway")
    gateway_map = gateway if isinstance(gateway, Mapping) else {}
    blocks: list[object] = []
    nested = gateway_map.get("platforms") if isinstance(gateway_map, Mapping) else None
    if isinstance(nested, Mapping):
        blocks.append(nested.get("buzz"))
    top = document.get("platforms")
    if isinstance(top, Mapping):
        blocks.append(top.get("buzz"))
    if isinstance(gateway_map, Mapping):
        blocks.append(gateway_map.get("buzz"))
    extra: dict[str, object] = {}
    for block in blocks:
        if block is None:
            continue
        mapped = _mapping(block)
        if mapped is None:
            continue
        block_extra = mapped.get("extra")
        if isinstance(block_extra, Mapping):
            extra.update(block_extra)
        elif block_extra is not None:
            raise HermesAuthzError("existing authorization cannot be established")
    return extra


def _merge_extra(base: dict[str, object], incoming: Mapping[str, object]) -> dict[str, object]:
    merged = dict(base)
    merged.update(incoming)
    return merged


def _pairing_humans(opened: OpenedHermesProfile) -> tuple[str, ...]:
    found: list[str] = []
    seen: set[str] = set()
    saw_file = False
    try:
        for parts in _PAIRING_PARTS:
            raw = opened.read_relative(parts)
            if raw is None:
                continue
            saw_file = True
            try:
                loaded = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise HermesAuthzError("existing authorization cannot be established") from None
            if not isinstance(loaded, Mapping):
                raise HermesAuthzError("existing authorization cannot be established")
            for key in loaded:
                # Buzz pairing compares the stored id to the lowercase event
                # pubkey with no case fold and no npub decode.
                if not isinstance(key, str) or not _PUBHEX.fullmatch(key.strip()):
                    raise HermesAuthzError("existing authorization cannot be established")
                identity = key.strip()
                if identity in seen:
                    continue
                seen.add(identity)
                found.append(identity)
    except ProfileEnvError:
        raise HermesAuthzError("existing authorization cannot be established") from None
    if not saw_file:
        return ()
    return tuple(found)


def _configured_allow_all(
    env_value: str | None,
    configured: object,
    present: bool,
) -> tuple[bool, str]:
    """Env wins over config. Absent on both sides is Hermes's default, false."""
    if env_value is not None:
        return _truthy(env_value), "env"
    if present:
        return _truthy(configured), "config"
    return False, "hermes_default"


def _gateway_allow_all_value(documents: Sequence[Mapping[str, object]]) -> tuple[bool, object]:
    """Return whether a gateway allow-all key is present, and its value.

    Top-level ``allow_all_users`` wins over ``gateway.allow_all_users``.
    ``config.yaml`` is later in ``documents`` and wins over legacy ``gateway.json``.
    """
    present = False
    value: object = None
    for document in documents:
        if "allow_all_users" in document:
            present = True
            value = document.get("allow_all_users")
            continue
        gateway = document.get("gateway")
        if isinstance(gateway, Mapping) and "allow_all_users" in gateway:
            present = True
            value = gateway.get("allow_all_users")
    return present, value


def _allow_all_decision(
    env_buzz: str | None,
    env_gateway: str | None,
    buzz_extra: Mapping[str, object],
    config_documents: Sequence[Mapping[str, object]],
) -> tuple[bool, str]:
    buzz_open, buzz_source = _configured_allow_all(
        env_buzz,
        buzz_extra.get("allow_all_users"),
        "allow_all_users" in buzz_extra,
    )
    gateway_present, gateway_value = _gateway_allow_all_value(config_documents)
    gateway_open, gateway_source = _configured_allow_all(env_gateway, gateway_value, gateway_present)
    if buzz_open or gateway_open:
        return True, "env" if "env" in {buzz_source, gateway_source} else "config"
    if buzz_source == "hermes_default" and gateway_source == "hermes_default":
        return False, "hermes_default"
    if buzz_source == "env" or gateway_source == "env":
        return False, "env"
    return False, "config"


def effective_buzz_authorization(opened: OpenedHermesProfile, env_bytes: bytes) -> EffectiveBuzzAuthorization:
    """Public humans already authorized, using Hermes's current precedence."""
    if not isinstance(env_bytes, (bytes, bytearray)):
        raise HermesAuthzError("existing authorization cannot be established")
    raw = bytes(env_bytes)
    env_users = _optional_env(raw, _ALLOWED_USERS)
    env_buzz_all = _optional_env(raw, _ALLOW_ALL)
    env_gateway_all = _optional_env(raw, _GATEWAY_ALLOW_ALL)
    env_gateway_users = _optional_env(raw, _GATEWAY_ALLOWED)

    try:
        config_raw = opened.read_relative(_CONFIG_PARTS)
        gateway_raw = opened.read_relative(_GATEWAY_JSON_PARTS)
    except ProfileEnvError:
        raise HermesAuthzError("existing authorization cannot be established") from None
    config_doc = _load_structured(config_raw, "yaml")
    gateway_doc = _load_structured(gateway_raw, "json")
    # Legacy gateway.json is the base layer. config.yaml wins on shared keys.
    extra = _buzz_extra(gateway_doc)
    extra = _merge_extra(extra, _buzz_extra(config_doc))
    documents = [doc for doc in (gateway_doc, config_doc) if doc is not None]

    allow_all, source = _allow_all_decision(env_buzz_all, env_gateway_all, extra, documents)
    if allow_all:
        raise HermesAuthzError("allow_all_users is not a control authorization")

    # A present pairing file that cannot be parsed hides approvals. Read it
    # even when those approvals are not part of the effective set.
    paired = _pairing_humans(opened)
    sources: list[str] = []
    humans: list[str] = []
    configured_users = (
        _identity_list(extra.get("allowed_users"), strict=True) if "allowed_users" in extra else ()
    )
    if env_users is not None:
        humans.extend(_identity_list(env_users, strict=True))
        sources.append("env_allowed_users")
    elif configured_users:
        humans.extend(configured_users)
        sources.append("config_allowed_users")
    else:
        if paired:
            humans.extend(paired)
            sources.append("pairing")
        if "allow_from" in extra:
            allowed_from = _identity_list(extra.get("allow_from"), strict=True)
            if allowed_from:
                humans.extend(identity for identity in allowed_from if identity not in humans)
                sources.append("config_allow_from")
        if env_gateway_users is not None:
            global_users = _identity_list(env_gateway_users, strict=False, casefold=False)
            added = [identity for identity in global_users if identity not in humans]
            if added:
                humans.extend(added)
                sources.append("gateway_allowed_users")
    deduped: list[str] = []
    seen: set[str] = set()
    for identity in humans:
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(identity)
    return EffectiveBuzzAuthorization(
        allow_all_users=False,
        allow_all_source=source,
        humans=tuple(deduped),
        human_sources=tuple(sources),
    )
