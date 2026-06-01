from __future__ import annotations

from app.services import google_sheets_config


def test_google_sheets_status_defaults_to_disabled_without_secrets() -> None:
    status = google_sheets_config.get_google_sheets_config_status(secrets={})

    assert status.enabled is False
    assert status.base_spreadsheet_id == (
        "1MBeZLGF_z37kbu32g-WiQ8Q0_ZyY9QGyGJY5tReIDdY"
    )
    assert status.base_worksheet_name == "BASE_ESTRUCTURAL"
    assert status.log_spreadsheet_id == "1Zw6I3sxiM618TRnmP04d0016to_vjKXITvdOBc8z8Tg"
    assert status.log_worksheet_name == "LOG_PUBLICACIONES"
    assert status.service_account_email is None
    assert "gcp_service_account.private_key" in status.missing_keys


def test_google_sheets_status_detects_complete_configuration() -> None:
    status = google_sheets_config.get_google_sheets_config_status(
        secrets=_configured_secrets()
    )

    assert status.enabled is True
    assert status.missing_keys == []
    assert status.base_spreadsheet_id == "base-sheet-id"
    assert status.base_worksheet_name == "BASE"
    assert status.log_spreadsheet_id == "log-sheet-id"
    assert status.log_worksheet_name == "LOG"
    assert status.service_account_email == "bot@example.iam.gserviceaccount.com"
    assert google_sheets_config.is_google_sheets_integration_enabled(
        _configured_secrets()
    )


def test_build_google_service_account_credentials_returns_none_when_disabled() -> None:
    assert google_sheets_config.build_google_service_account_credentials(
        secrets={}
    ) is None


def test_build_google_service_account_credentials_uses_google_auth(
    monkeypatch,
) -> None:
    calls: list[tuple[dict[str, str], list[str]]] = []

    def fake_from_service_account_info(info: dict[str, str], scopes: list[str]):
        calls.append((info, scopes))
        return "credentials"

    monkeypatch.setattr(
        google_sheets_config.Credentials,
        "from_service_account_info",
        fake_from_service_account_info,
    )

    credentials = google_sheets_config.build_google_service_account_credentials(
        secrets=_configured_secrets()
    )

    assert credentials == "credentials"
    assert len(calls) == 1
    info, scopes = calls[0]
    assert info["client_email"] == "bot@example.iam.gserviceaccount.com"
    assert info["private_key"].startswith("-----BEGIN PRIVATE KEY-----")
    assert scopes == list(google_sheets_config.GOOGLE_SHEETS_SCOPES)


def _configured_secrets() -> dict[str, dict[str, str]]:
    return {
        "google_sheets": {
            "base_spreadsheet_id": "base-sheet-id",
            "base_worksheet_name": "BASE",
            "log_spreadsheet_id": "log-sheet-id",
            "log_worksheet_name": "LOG",
        },
        "gcp_service_account": {
            "type": "service_account",
            "project_id": "demo-project",
            "private_key_id": "key-id",
            "private_key": (
                "-----BEGIN PRIVATE KEY-----\nFAKE_PRIVATE_KEY\n"
                "-----END PRIVATE KEY-----\n"
            ),
            "client_email": "bot@example.iam.gserviceaccount.com",
            "client_id": "client-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": (
                "https://www.googleapis.com/oauth2/v1/certs"
            ),
            "client_x509_cert_url": "https://example.com/cert",
        },
    }
