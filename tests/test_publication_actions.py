from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from io import BytesIO

import pandas as pd

from app.services.delivery_package import UploadedFileTrace
from app.services.google_sheets_client import GoogleSheetsClient, PublicationResult
from app.services.google_sheets_config import get_google_sheets_settings
from app.services.publication_decision import ACTION_APPEND, ACTION_CANCEL, ACTION_REPLACE
from app.services.validation_summary import READY, ValidationSummary
from app.ui import upload_panel


def test_publication_blocks_without_human_review() -> None:
    client = RecordingClient()

    result = upload_panel._execute_publication_action(
        _build_run_result(),
        decision_state={
            "selected_action": ACTION_APPEND,
            "review_ready": False,
            "can_advance": False,
        },
        client=client,
    )

    assert result.result_status == "blocked"
    assert "revision humana" in result.error_message
    assert client.calls == []


def test_append_publication_calls_append_client() -> None:
    client = RecordingClient()

    result = upload_panel._execute_publication_action(
        _build_run_result(),
        decision_state={
            "selected_action": ACTION_APPEND,
            "review_ready": True,
            "can_advance": True,
        },
        client=client,
    )

    assert result.success is True
    assert client.calls == [ACTION_APPEND]


def test_replace_publication_blocks_without_strong_confirmation() -> None:
    client = RecordingClient()

    result = upload_panel._execute_publication_action(
        _build_run_result(),
        decision_state={
            "selected_action": ACTION_REPLACE,
            "review_ready": True,
            "can_advance": False,
            "replacement_confirmed": False,
            "rows_to_replace": 2,
        },
        client=client,
    )

    assert result.result_status == "blocked"
    assert "REEMPLAZAR" in result.error_message
    assert client.calls == []


def test_replace_publication_calls_replace_client_after_confirmation() -> None:
    client = RecordingClient()

    result = upload_panel._execute_publication_action(
        _build_run_result(),
        decision_state={
            "selected_action": ACTION_REPLACE,
            "review_ready": True,
            "can_advance": True,
            "replacement_confirmed": True,
            "rows_to_replace": 2,
        },
        client=client,
    )

    assert result.success is True
    assert client.calls == [ACTION_REPLACE]


def test_cancel_publication_does_not_call_write_client() -> None:
    client = RecordingClient()

    result = upload_panel._execute_publication_action(
        _build_run_result(),
        decision_state={
            "selected_action": ACTION_CANCEL,
            "review_ready": True,
            "can_advance": True,
        },
        client=client,
    )

    assert result.result_status == "cancelled"
    assert client.calls == []


def test_client_error_is_reported_as_failed_result() -> None:
    client = RecordingClient(error_message="No fue posible escribir en Google Sheets.")

    result = upload_panel._execute_publication_action(
        _build_run_result(),
        decision_state={
            "selected_action": ACTION_APPEND,
            "review_ready": True,
            "can_advance": True,
        },
        client=client,
    )

    assert result.result_status == "failed"
    assert result.error_message == "No fue posible escribir en Google Sheets."


def test_successful_publication_appends_audit_log() -> None:
    client = _build_google_sheets_client(
        master_values=[["FACULTAD", "CARRERA", "ASIGNATURA"]],
    )

    result = upload_panel._execute_publication_action(
        _build_run_result(),
        decision_state={
            "selected_action": ACTION_APPEND,
            "review_ready": True,
            "can_advance": True,
        },
        client=client,
    )

    assert result.result_status == "published"
    assert client._log_worksheet().get_all_values()[1][3] == ACTION_APPEND


def test_failed_publication_appends_audit_log() -> None:
    client = _build_google_sheets_client(
        master_values=[
            ["FACULTAD", "CARRERA", "ASIGNATURA"],
            ["Salud", "Nutricion", "Anatomia"],
        ],
    )

    result = upload_panel._execute_publication_action(
        _build_run_result(),
        decision_state={
            "selected_action": ACTION_APPEND,
            "review_ready": True,
            "can_advance": True,
        },
        client=client,
    )

    assert result.result_status == "failed"
    assert client._log_worksheet().get_all_values()[1][3] == ACTION_APPEND
    assert client._log_worksheet().get_all_values()[1][21] == "failed"


def _build_run_result() -> dict[str, object]:
    dataframe = pd.DataFrame(
        [
            {
                "FACULTAD": "Salud",
                "CARRERA": "Nutricion",
                "ASIGNATURA": "Bioquimica",
            }
        ]
    )
    return {
        "summary": ValidationSummary(
            status=READY,
            total_rows=1,
            total_columns=3,
            faculty="Salud",
            career="Nutricion",
        ),
        "warnings": ["Advertencia controlada"],
        "pipeline_version": "test-version",
        "artifacts": {
            "consolidated_excel": {
                "name": "tributacion_final.xlsx",
                "bytes": _excel_bytes(dataframe),
            }
        },
        "uploaded_files": {
            "PDF plan de estudio": UploadedFileTrace(
                name="plan.pdf",
                sha256="abc123",
                size_bytes=10,
            ),
            "Matriz Excel tributacion": UploadedFileTrace(
                name="matriz.xlsx",
                sha256="def456",
                size_bytes=20,
            ),
        },
    }


def _excel_bytes(dataframe: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    dataframe.to_excel(buffer, index=False)
    return buffer.getvalue()


class RecordingClient:
    def __init__(self, error_message: str | None = None) -> None:
        self.calls: list[str] = []
        self.error_message = error_message

    def append_consolidated_rows(self, dataframe: pd.DataFrame, metadata) -> PublicationResult:
        self.calls.append(ACTION_APPEND)
        return self._result(
            operation_type=ACTION_APPEND,
            error_message=self.error_message,
            rows_published=len(dataframe),
        )

    def replace_career_rows(self, dataframe: pd.DataFrame, metadata) -> PublicationResult:
        self.calls.append(ACTION_REPLACE)
        return self._result(
            operation_type=ACTION_REPLACE,
            error_message=self.error_message,
            rows_published=len(dataframe),
        )

    def _result(
        self,
        *,
        operation_type: str,
        error_message: str | None,
        rows_published: int,
    ) -> PublicationResult:
        success = error_message is None
        return PublicationResult(
            success=success,
            operation_type=operation_type,
            facultad="Salud",
            carrera="Nutricion",
            career_key="salud nutricion",
            rows_before=0,
            rows_replaced=0,
            rows_published=rows_published if success else 0,
            result_status="published" if success else "failed",
            published_at="2026-06-02T00:00:00+00:00",
            error_message=error_message,
        )


def _build_google_sheets_client(
    *,
    master_values: list[list[str]],
    log_values: list[list[str]] | None = None,
) -> GoogleSheetsClient:
    settings = get_google_sheets_settings(secrets=_configured_secrets())
    client = FakeSheetsClient(
        {
            settings.base_spreadsheet_id: FakeSpreadsheet(
                {
                    settings.base_worksheet_name: FakeWorksheet(master_values),
                }
            ),
            settings.log_spreadsheet_id: FakeSpreadsheet(
                {
                    settings.log_worksheet_name: FakeWorksheet(
                        log_values
                        or [
                            [
                                "publication_id",
                                "run_id",
                                "published_at",
                                "operation_type",
                                "base_spreadsheet_id",
                                "base_worksheet_name",
                                "log_spreadsheet_id",
                                "log_worksheet_name",
                                "facultad",
                                "carrera",
                                "career_key",
                                "rows_before",
                                "rows_replaced",
                                "rows_published",
                                "pipeline_version",
                                "source_pdf_name",
                                "source_matrix_name",
                                "source_pdf_trace",
                                "source_matrix_trace",
                                "validation_status",
                                "warnings",
                                "result_status",
                                "error_message",
                            ]
                        ],
                    ),
                }
            ),
        }
    )
    return GoogleSheetsClient(
        sheets_client=client,
        secrets=_configured_secrets(),
        now_provider=lambda: datetime(2026, 6, 2, 0, 0, tzinfo=UTC),
    )


def _configured_secrets() -> dict[str, dict[str, str]]:
    return {
        "google_sheets": {
            "base_spreadsheet_id": "base-sheet-id",
            "base_worksheet_name": "BASE",
            "log_spreadsheet_id": "log-sheet-id",
            "log_worksheet_name": "LOG",
        }
    }


class FakeSheetsClient:
    def __init__(self, spreadsheets: dict[str, "FakeSpreadsheet"]) -> None:
        self.spreadsheets = spreadsheets

    def open_by_key(self, key: str) -> "FakeSpreadsheet":
        return self.spreadsheets[key]


class FakeSpreadsheet:
    def __init__(self, worksheets: dict[str, "FakeWorksheet"]) -> None:
        self.worksheets = worksheets

    def worksheet(self, name: str) -> "FakeWorksheet":
        return self.worksheets[name]


class FakeWorksheet:
    def __init__(self, values: list[list[str]]) -> None:
        self._values = deepcopy(values)

    def get_all_values(self) -> list[list[str]]:
        return deepcopy(self._values)

    def append_rows(
        self,
        rows: list[list[str]],
        value_input_option: str | None = None,
    ) -> None:
        del value_input_option
        self._values.extend(_stringify_rows(rows))

    def append_row(
        self,
        row: list[str],
        value_input_option: str | None = None,
    ) -> None:
        del value_input_option
        self._values.append([str(value) for value in row])

    def clear(self) -> None:
        self._values = []

    def update(self, values: list[list[str]]) -> None:
        self._values = _stringify_rows(values)


def _stringify_rows(rows: list[list[object]]) -> list[list[str]]:
    return [[str(value) for value in row] for row in rows]
