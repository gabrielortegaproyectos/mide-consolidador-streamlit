from __future__ import annotations

from app.services import auth


def test_auth_status_reports_unconfigured_without_secrets() -> None:
    status = auth.get_auth_config_status(secrets={})

    assert status.configured is False
    assert status.expected_password is None


def test_auth_status_reports_configured_with_password_secret() -> None:
    status = auth.get_auth_config_status(secrets={"auth": {"password": "clave-mide"}})

    assert status.configured is True
    assert status.expected_password == "clave-mide"


def test_auth_status_ignores_blank_password_secret() -> None:
    status = auth.get_auth_config_status(secrets={"auth": {"password": "   "}})

    assert status.configured is False
    assert status.expected_password is None


def test_verify_password_accepts_matching_candidate() -> None:
    assert auth.verify_password("clave-mide", "clave-mide") is True


def test_verify_password_rejects_wrong_candidate() -> None:
    assert auth.verify_password("otra-clave", "clave-mide") is False


def test_verify_password_rejects_when_secret_missing() -> None:
    assert auth.verify_password("cualquier-clave", None) is False


def test_verify_password_rejects_empty_candidate() -> None:
    assert auth.verify_password("", "clave-mide") is False
