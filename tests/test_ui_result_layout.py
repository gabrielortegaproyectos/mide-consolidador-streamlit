from __future__ import annotations

import pandas as pd

from app.services.google_sheets_config import GoogleSheetsConfigStatus
from app.services.google_sheets_client import PublicationResult
from app.services.validation_summary import READY_WITH_WARNINGS, ValidationSummary
from app.ui import upload_panel, validation_panel


def test_run_result_renders_preview_before_technical_logs(monkeypatch) -> None:
    events: list[str] = []

    monkeypatch.setattr(upload_panel.st, "divider", lambda: events.append("divider"))
    monkeypatch.setattr(upload_panel.st, "success", lambda _: events.append("success"))
    monkeypatch.setattr(upload_panel, "render_validation_summary", lambda _: events.append("summary"))
    monkeypatch.setattr(upload_panel.st, "markdown", lambda _: events.append("preview-title"))
    monkeypatch.setattr(upload_panel.st, "dataframe", lambda *args, **kwargs: events.append("preview"))
    monkeypatch.setattr(upload_panel, "render_technical_logs", lambda _: events.append("logs"))
    monkeypatch.setattr(
        upload_panel,
        "render_publication_review_panel",
        lambda *args, **kwargs: events.append("publication-review"),
    )
    monkeypatch.setattr(upload_panel.st, "download_button", lambda *args, **kwargs: None)
    monkeypatch.setattr(upload_panel.st, "caption", lambda _: None)

    upload_panel._render_run_result(
        {
            "summary": ValidationSummary(status=READY_WITH_WARNINGS),
            "warnings": [],
            "pipeline_version": "test-version",
            "artifacts": {
                "consolidated_excel": {"name": "tributacion_final.xlsx", "bytes": b"xlsx"}
            },
            "consolidated_preview": pd.DataFrame({"ASIGNATURA": ["A"]}),
        }
    )

    assert events.index("summary") < events.index("preview") < events.index("logs")


def test_render_technical_logs_uses_collapsible_logs_section(monkeypatch) -> None:
    captured: list[str] = []

    class _Expander:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        validation_panel.st,
        "expander",
        lambda label: captured.append(label) or _Expander(),
    )
    monkeypatch.setattr(validation_panel.st, "caption", lambda _: None)
    monkeypatch.setattr(validation_panel.st, "markdown", lambda _: None)
    monkeypatch.setattr(validation_panel.st, "warning", lambda _: None)
    monkeypatch.setattr(validation_panel.st, "dataframe", lambda *args, **kwargs: None)

    class _MetricColumn:
        def metric(self, *_args, **_kwargs) -> None:
            return None

    monkeypatch.setattr(
        validation_panel.st,
        "columns",
        lambda count: [_MetricColumn() for _ in range(count)],
    )

    validation_panel.render_technical_logs(
        ValidationSummary(
            status=READY_WITH_WARNINGS,
            match_counts={"EXACTO": 2},
            code_counts={"MATCH_OK": 2},
            main_columns=["CARRERA"],
            warnings=["Advertencia tecnica"],
            problematic_subjects=pd.DataFrame(),
        )
    )

    assert captured == ["🔎 Logs tecnicos"]


def test_run_result_renders_publication_summary_when_available(monkeypatch) -> None:
    events: list[str] = []

    monkeypatch.setattr(upload_panel.st, "divider", lambda: None)
    monkeypatch.setattr(upload_panel.st, "success", lambda _: None)
    monkeypatch.setattr(upload_panel, "render_validation_summary", lambda _: None)
    monkeypatch.setattr(upload_panel, "render_technical_logs", lambda _: None)
    monkeypatch.setattr(upload_panel.st, "download_button", lambda *args, **kwargs: None)
    monkeypatch.setattr(upload_panel.st, "caption", lambda _: None)
    monkeypatch.setattr(upload_panel, "render_publication_review_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        upload_panel,
        "render_publication_result_summary",
        lambda result: events.append(result.publication_id),
    )

    upload_panel._render_run_result(
        {
            "summary": ValidationSummary(status=READY_WITH_WARNINGS),
            "warnings": [],
            "pipeline_version": "test-version",
            "artifacts": {
                "consolidated_excel": {"name": "tributacion_final.xlsx", "bytes": b"xlsx"}
            },
            "consolidated_preview": pd.DataFrame(),
            "publication_result": PublicationResult(
                success=True,
                operation_type="append",
                facultad="Salud",
                carrera="Nutricion",
                career_key="salud nutricion",
                rows_before=0,
                rows_replaced=0,
                rows_published=2,
                result_status="published",
                published_at="2026-06-01T21:00:00+00:00",
                publication_id="publication-42",
            ),
        }
    )

    assert events == ["publication-42"]


def test_run_result_keeps_local_download_when_google_sheets_is_not_configured(
    monkeypatch,
) -> None:
    events: list[str] = []

    monkeypatch.setattr(upload_panel.st, "divider", lambda: None)
    monkeypatch.setattr(upload_panel.st, "success", lambda _: None)
    monkeypatch.setattr(upload_panel, "render_validation_summary", lambda _: None)
    monkeypatch.setattr(upload_panel.st, "markdown", lambda _: None)
    monkeypatch.setattr(upload_panel.st, "dataframe", lambda *args, **kwargs: None)
    monkeypatch.setattr(upload_panel, "render_technical_logs", lambda _: None)
    monkeypatch.setattr(
        upload_panel,
        "render_publication_review_panel",
        lambda *args, **kwargs: events.append("publication-review"),
    )
    monkeypatch.setattr(
        upload_panel,
        "get_google_sheets_config_status",
        lambda: GoogleSheetsConfigStatus(
            enabled=False,
            missing_keys=["gcp_service_account.client_email"],
            base_spreadsheet_id=None,
            base_worksheet_name=None,
            log_spreadsheet_id=None,
            log_worksheet_name=None,
            service_account_email=None,
        ),
    )
    monkeypatch.setattr(
        upload_panel.st,
        "download_button",
        lambda *args, **kwargs: events.append("download"),
    )
    monkeypatch.setattr(upload_panel.st, "info", lambda _: events.append("info"))
    monkeypatch.setattr(upload_panel.st, "caption", lambda _: None)

    upload_panel._render_run_result(
        {
            "summary": ValidationSummary(status=READY_WITH_WARNINGS),
            "warnings": [],
            "pipeline_version": "test-version",
            "artifacts": {
                "consolidated_excel": {"name": "tributacion_final.xlsx", "bytes": b"xlsx"}
            },
            "consolidated_preview": pd.DataFrame(),
        }
    )

    assert "download" in events
    assert "publication-review" not in events
