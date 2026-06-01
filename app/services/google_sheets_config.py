from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import streamlit as st
from google.oauth2.service_account import Credentials
from streamlit.errors import StreamlitSecretNotFoundError

DEFAULT_GOOGLE_SHEETS_CONFIG = {
    "base_spreadsheet_id": "1MBeZLGF_z37kbu32g-WiQ8Q0_ZyY9QGyGJY5tReIDdY",
    "base_worksheet_name": "BASE_ESTRUCTURAL",
    "log_spreadsheet_id": "1Zw6I3sxiM618TRnmP04d0016to_vjKXITvdOBc8z8Tg",
    "log_worksheet_name": "LOG_PUBLICACIONES",
}

GOOGLE_SHEETS_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)

REQUIRED_SERVICE_ACCOUNT_KEYS = (
    "type",
    "project_id",
    "private_key_id",
    "private_key",
    "client_email",
    "client_id",
    "auth_uri",
    "token_uri",
    "auth_provider_x509_cert_url",
    "client_x509_cert_url",
)


@dataclass(frozen=True)
class GoogleSheetsConfigStatus:
    enabled: bool
    missing_keys: list[str]
    base_spreadsheet_id: str | None
    base_worksheet_name: str | None
    log_spreadsheet_id: str | None
    log_worksheet_name: str | None
    service_account_email: str | None


def get_google_sheets_config_status(
    secrets: Mapping[str, Any] | None = None,
) -> GoogleSheetsConfigStatus:
    root_secrets = _resolve_secrets_root(secrets)
    google_sheets = {
        **DEFAULT_GOOGLE_SHEETS_CONFIG,
        **_normalized_section(_read_section(root_secrets, "google_sheets")),
    }
    service_account = _normalized_section(
        _read_section(root_secrets, "gcp_service_account")
    )
    missing_keys = [
        f"gcp_service_account.{key}"
        for key in REQUIRED_SERVICE_ACCOUNT_KEYS
        if not service_account.get(key)
    ]
    return GoogleSheetsConfigStatus(
        enabled=not missing_keys,
        missing_keys=missing_keys,
        base_spreadsheet_id=_non_empty(
            google_sheets.get("base_spreadsheet_id")
        ),
        base_worksheet_name=_non_empty(
            google_sheets.get("base_worksheet_name")
        ),
        log_spreadsheet_id=_non_empty(
            google_sheets.get("log_spreadsheet_id")
        ),
        log_worksheet_name=_non_empty(
            google_sheets.get("log_worksheet_name")
        ),
        service_account_email=_non_empty(service_account.get("client_email")),
    )


def is_google_sheets_integration_enabled(
    secrets: Mapping[str, Any] | None = None,
) -> bool:
    return get_google_sheets_config_status(secrets).enabled


def build_google_service_account_credentials(
    secrets: Mapping[str, Any] | None = None,
) -> Credentials | None:
    status = get_google_sheets_config_status(secrets)
    if not status.enabled:
        return None
    root_secrets = _resolve_secrets_root(secrets)
    service_account = _normalized_section(
        _read_section(root_secrets, "gcp_service_account")
    )
    return Credentials.from_service_account_info(
        service_account,
        scopes=list(GOOGLE_SHEETS_SCOPES),
    )


def _resolve_secrets_root(
    secrets: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if secrets is not None:
        return secrets
    return st.secrets


def _read_section(
    secrets: Mapping[str, Any],
    name: str,
) -> Mapping[str, Any]:
    try:
        if hasattr(secrets, "get"):
            section = secrets.get(name, {})
        else:
            section = secrets[name]
    except (KeyError, StreamlitSecretNotFoundError, TypeError):
        return {}
    return _coerce_mapping(section)


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


def _normalized_section(section: Mapping[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in section.items():
        cleaned = _non_empty(value)
        if cleaned is not None:
            normalized[str(key)] = cleaned
    return normalized


def _non_empty(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text
