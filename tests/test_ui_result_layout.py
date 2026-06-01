from __future__ import annotations

import pandas as pd

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
