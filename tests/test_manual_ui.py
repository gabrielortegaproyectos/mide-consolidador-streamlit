from __future__ import annotations

from app.main import _render_google_sheets_status
from app.services.google_sheets_config import GoogleSheetsConfigStatus
from app.ui import manual as manual_ui


def test_render_manual_content_targets_end_users(monkeypatch) -> None:
    markdowns: list[str] = []
    infos: list[str] = []
    warnings: list[str] = []
    successes: list[str] = []
    dataframe_calls: list[str] = []

    monkeypatch.setattr(manual_ui.st, "markdown", lambda text: markdowns.append(text))
    monkeypatch.setattr(manual_ui.st, "info", lambda text: infos.append(text))
    monkeypatch.setattr(manual_ui.st, "warning", lambda text: warnings.append(text))
    monkeypatch.setattr(manual_ui.st, "success", lambda text: successes.append(text))
    monkeypatch.setattr(
        manual_ui.st,
        "dataframe",
        lambda *args, **kwargs: dataframe_calls.append("dataframe"),
    )

    manual_ui.render_manual_content()

    rendered = "\n".join(markdowns + infos + warnings + successes)
    assert "Archivos que debes subir" in rendered
    assert "Publicar nueva carrera" in rendered
    assert "Reemplazar carrera" in rendered
    assert "Cancelar" in rendered
    assert "Descargar el Excel" in rendered
    assert "no publiques" in rendered
    assert dataframe_calls == []


def test_google_sheets_status_hides_configured_production_details(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr("app.main.st.success", lambda text: calls.append(text))
    monkeypatch.setattr("app.main.st.caption", lambda text: calls.append(text))
    monkeypatch.setattr("app.main.st.info", lambda text: calls.append(text))

    _render_google_sheets_status(
        GoogleSheetsConfigStatus(
            enabled=True,
            missing_keys=[],
            base_spreadsheet_id="base-sheet-id",
            base_worksheet_name="BASE_ESTRUCTURAL",
            log_spreadsheet_id="log-sheet-id",
            log_worksheet_name="LOG_PUBLICACIONES",
            service_account_email="svc@example.com",
        )
    )

    assert calls == []
