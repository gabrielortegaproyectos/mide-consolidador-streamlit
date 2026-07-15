from __future__ import annotations

import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

SESSION_STATE_KEY = "mide_authenticated"


@dataclass(frozen=True)
class AuthConfigStatus:
    configured: bool
    expected_password: str | None


def get_auth_config_status(
    secrets: Mapping[str, Any] | None = None,
) -> AuthConfigStatus:
    root_secrets = _resolve_secrets_root(secrets)
    password = _read_password(root_secrets)
    return AuthConfigStatus(configured=password is not None, expected_password=password)


def verify_password(candidate: str, expected_password: str | None) -> bool:
    if not expected_password or not candidate:
        return False
    return hmac.compare_digest(candidate, expected_password)


def is_authenticated() -> bool:
    return bool(st.session_state.get(SESSION_STATE_KEY, False))


def mark_authenticated() -> None:
    st.session_state[SESSION_STATE_KEY] = True


def clear_authentication() -> None:
    st.session_state[SESSION_STATE_KEY] = False


def _resolve_secrets_root(
    secrets: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if secrets is not None:
        return secrets
    return st.secrets


def _read_password(secrets: Mapping[str, Any]) -> str | None:
    try:
        if hasattr(secrets, "get"):
            section = secrets.get("auth", {})
        else:
            section = secrets["auth"]
    except (KeyError, StreamlitSecretNotFoundError, TypeError):
        return None
    section = _coerce_mapping(section)
    return _non_empty(section.get("password"))


def _coerce_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "to_dict"):
        converted = value.to_dict()
        if isinstance(converted, Mapping):
            return converted
    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def _non_empty(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text
