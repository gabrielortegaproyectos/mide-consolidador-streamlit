from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
import uuid

import pandas as pd

from app.services.delivery_package import UploadedFileTrace
from app.services.google_sheets_client import (
    GoogleSheetsClient,
    PublicationMetadata,
    PublicationLogEntry,
    PublicationResult,
    build_publication_log_entry,
    build_career_key,
    build_publication_result_summary,
    build_audit_log_entry,
    find_existing_career_rows,
    load_master_sheet,
    normalize_key,
)
from app.services.google_sheets_config import get_google_sheets_settings


def test_normalize_key_matches_catalog_style() -> None:
    assert normalize_key("  Ingeniería   en   Gestión  ") == "ingenieria en gestion"
    assert normalize_key("Facultád de Salud") == "facultad de salud"


def test_build_career_key_normalizes_facultad_and_carrera() -> None:
    assert build_career_key(
        "Facultad de Educación",
        "Pedagogía Básica",
    ) == build_career_key(
        " facultad de educacion ",
        " pedagogia   basica ",
    )


def test_find_existing_career_rows_uses_normalized_facultad_and_carrera() -> None:
    master_df = pd.DataFrame(
        [
            {"FACULTAD": "Salúd", "CARRERA": " Nutrición ", "ASIGNATURA": "A"},
            {"FACULTAD": "Salud", "CARRERA": "Enfermería", "ASIGNATURA": "B"},
        ]
    )

    matched_rows = find_existing_career_rows(
        master_df,
        facultad="salud",
        carrera="nutricion",
    )

    assert matched_rows["ASIGNATURA"].tolist() == ["A"]


def test_load_master_sheet_reads_synthetic_online_base(
    online_master_with_existing_career_df: pd.DataFrame,
) -> None:
    loaded = load_master_sheet(
        sheets_client=_build_fake_sheets_client_from_dataframe(
            online_master_with_existing_career_df
        ),
        secrets=_configured_secrets(),
    )

    assert loaded.to_dict(
        orient="records"
    ) == online_master_with_existing_career_df.to_dict(orient="records")


def test_append_consolidated_rows_blocks_blank_required_columns() -> None:
    client = _build_client()
    df = pd.DataFrame(
        [{"FACULTAD": "", "CARRERA": "Nutricion", "ASIGNATURA": "Bioquimica"}]
    )

    result = client.append_consolidated_rows(
        df,
        _metadata(operation_type="append"),
    )

    assert result.success is False
    assert result.result_status == "failed"
    assert "FACULTAD" in result.error_message
    assert client.load_master_sheet().empty


def test_append_consolidated_rows_aligns_to_master_columns_and_logs() -> None:
    client = _build_client(
        master_values=[
            ["FACULTAD", "CARRERA", "ASIGNATURA"],
        ]
    )
    df = pd.DataFrame(
        [
            {
                "ASIGNATURA": "Bioquimica",
                "CARRERA": "Nutricion",
                "FACULTAD": "Salud",
            }
        ]
    )

    result = client.append_consolidated_rows(
        df,
        _metadata(operation_type="append"),
    )

    assert result.success is True
    assert result.rows_published == 1
    assert client._base_worksheet().get_all_values() == [
        ["FACULTAD", "CARRERA", "ASIGNATURA"],
        ["Salud", "Nutricion", "Bioquimica"],
    ]
    assert client._log_worksheet().get_all_values()[1][3] == "append"


def test_replace_career_rows_rebuilds_master_without_previous_block() -> None:
    client = _build_client(
        master_values=[
            ["FACULTAD", "CARRERA", "ASIGNATURA"],
            ["Salud", "Nutricion", "Anatomia"],
            ["Salud", "Nutricion", "Quimica"],
            ["Salud", "Enfermeria", "Clinica"],
        ]
    )
    replacement_df = pd.DataFrame(
        [
            {
                "FACULTAD": "Salud",
                "CARRERA": "Nutricion",
                "ASIGNATURA": "Bioquimica",
            },
            {
                "FACULTAD": "Salud",
                "CARRERA": "Nutricion",
                "ASIGNATURA": "Fisiologia",
            },
        ]
    )

    result = client.replace_career_rows(
        replacement_df,
        _metadata(operation_type="replace"),
    )

    assert result.success is True
    assert result.rows_before == 2
    assert result.rows_replaced == 2
    assert client._base_worksheet().get_all_values() == [
        ["FACULTAD", "CARRERA", "ASIGNATURA"],
        ["Salud", "Enfermeria", "Clinica"],
        ["Salud", "Nutricion", "Bioquimica"],
        ["Salud", "Nutricion", "Fisiologia"],
    ]
    assert client._log_worksheet().get_all_values()[1][3] == "replace"


def test_append_consolidated_rows_rejects_technical_columns(
    publication_consolidated_df: pd.DataFrame,
    publication_metadata: PublicationMetadata,
    online_master_without_career_df: pd.DataFrame,
) -> None:
    client = _build_client_from_dataframe(online_master_without_career_df)
    df = publication_consolidated_df.assign(publication_status="simulated")

    result = client.append_consolidated_rows(df, publication_metadata)

    assert result.success is False
    assert result.result_status == "failed"
    assert "columnas no permitidas" in (result.error_message or "")
    assert client.load_master_sheet().to_dict(orient="records") == online_master_without_career_df.to_dict(
        orient="records"
    )


def test_append_consolidated_rows_keeps_metadata_only_in_audit_log(
    publication_consolidated_df: pd.DataFrame,
    publication_metadata: PublicationMetadata,
    online_master_without_career_df: pd.DataFrame,
) -> None:
    client = _build_client_from_dataframe(online_master_without_career_df)

    result = client.append_consolidated_rows(
        publication_consolidated_df,
        publication_metadata,
    )

    assert result.success is True
    assert client._base_worksheet().get_all_values() == [
        ["FACULTAD", "CARRERA", "ASIGNATURA", "CODIGO"],
        ["Salud", "Enfermeria", "Clinica", "ENF001"],
        ["Salud", "Nutricion", "Bioquimica", "NUT101"],
        ["Salud", "Nutricion", "Fisiologia", "NUT102"],
    ]
    log_row = client._log_worksheet().get_all_values()[1]
    assert log_row[14] == "test-version"
    assert log_row[20] == "warning 1 | warning 2"
    assert "pipeline_version" not in client.load_master_sheet().columns


def test_replace_career_rows_with_synthetic_existing_base(
    publication_consolidated_df: pd.DataFrame,
    publication_metadata: PublicationMetadata,
    online_master_with_existing_career_df: pd.DataFrame,
) -> None:
    client = _build_client_from_dataframe(online_master_with_existing_career_df)

    result = client.replace_career_rows(
        publication_consolidated_df,
        replace(publication_metadata, operation_type="replace"),
    )

    assert result.success is True
    assert result.rows_before == 2
    assert result.rows_replaced == 2
    assert client._base_worksheet().get_all_values() == [
        ["FACULTAD", "CARRERA", "ASIGNATURA", "CODIGO"],
        ["Salud", "Enfermeria", "Clinica", "ENF001"],
        ["Salud", "Nutricion", "Bioquimica", "NUT101"],
        ["Salud", "Nutricion", "Fisiologia", "NUT102"],
    ]


def test_build_audit_log_entry_serializes_publication_metadata() -> None:
    result = PublicationResult(
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
    )
    metadata = PublicationMetadata(
        operation_type="append",
        facultad="Salud",
        carrera="Nutricion",
        career_key="salud nutricion",
        pipeline_version="v1.2.3",
        source_pdf_name="plan.pdf",
        source_matrix_name="matriz.xlsx",
        source_pdf_trace=UploadedFileTrace(
            name="plan.pdf",
            sha256="abc123",
            size_bytes=10,
        ),
        source_matrix_trace={
            "name": "matriz.xlsx",
            "sha256": "def456",
            "size_bytes": 20,
        },
        validation_status="ok",
        warnings=["aviso 1", "aviso 2"],
        publication_id="publication-1",
        run_id="run-1",
    )

    entry = build_audit_log_entry(
        result,
        metadata,
        settings=get_google_sheets_settings(secrets=_configured_secrets()),
    )

    assert entry["publication_id"] == "publication-1"
    assert entry["run_id"] == "run-1"
    assert entry["operation_type"] == "append"
    assert entry["rows_published"] == 2
    assert entry["warnings"] == "aviso 1 | aviso 2"
    assert entry["source_pdf_trace"] == "plan.pdf | sha256=abc123 | bytes=10"
    assert entry["source_matrix_trace"] == "matriz.xlsx | sha256=def456 | bytes=20"
    assert entry["base_worksheet_name"] == "BASE"
    assert entry["log_worksheet_name"] == "LOG"


def test_build_publication_log_entry_uses_fixture_counts_and_warnings(
    publication_result: PublicationResult,
    publication_metadata: PublicationMetadata,
) -> None:
    entry = build_publication_log_entry(
        publication_result,
        publication_metadata,
        settings=get_google_sheets_settings(secrets=_configured_secrets()),
    )

    assert entry.rows_published == 2
    assert entry.rows_replaced == 0
    assert entry.result_status == "published"
    assert entry.warnings == "warning 1 | warning 2"


def test_build_publication_log_entry_generates_publication_id_when_missing() -> None:
    result = PublicationResult(
        success=True,
        operation_type="append",
        facultad="Salud",
        carrera="Nutricion",
        career_key="salud nutricion",
        rows_before=0,
        rows_replaced=0,
        rows_published=1,
        result_status="published",
        published_at="2026-06-01T21:00:00+00:00",
    )

    entry = build_publication_log_entry(
        result,
        _metadata(operation_type="append"),
        settings=get_google_sheets_settings(secrets=_configured_secrets()),
    )

    assert isinstance(entry, PublicationLogEntry)
    assert uuid.UUID(entry.publication_id)


def test_build_publication_log_entry_serializes_failed_publication_error() -> None:
    result = PublicationResult(
        success=False,
        operation_type="replace",
        facultad="Salud",
        carrera="Nutricion",
        career_key="salud nutricion",
        rows_before=2,
        rows_replaced=2,
        rows_published=0,
        result_status="failed",
        published_at="2026-06-01T21:00:00+00:00",
        publication_id="publication-2",
        error_message="No fue posible reemplazar la carrera.",
    )

    entry = build_publication_log_entry(
        result,
        _metadata(operation_type="replace"),
        settings=get_google_sheets_settings(secrets=_configured_secrets()),
    )

    assert entry.rows_replaced == 2
    assert entry.rows_published == 0
    assert entry.error_message == "No fue posible reemplazar la carrera."


def test_build_publication_result_summary_exposes_post_publication_fields() -> None:
    summary = build_publication_result_summary(
        PublicationResult(
            success=True,
            operation_type="replace",
            facultad="Salud",
            carrera="Nutricion",
            career_key="salud nutricion",
            rows_before=2,
            rows_replaced=2,
            rows_published=3,
            result_status="published",
            published_at="2026-06-01T21:00:00+00:00",
            publication_id="publication-3",
        )
    )

    assert summary.publication_id == "publication-3"
    assert summary.operation_type == "replace"
    assert summary.facultad == "Salud"
    assert summary.carrera == "Nutricion"
    assert summary.rows_published == 3
    assert summary.rows_replaced == 2


def _metadata(*, operation_type: str) -> PublicationMetadata:
    return PublicationMetadata(
        operation_type=operation_type,
        facultad="Salud",
        carrera="Nutricion",
        career_key="salud nutricion",
        validation_status="ok",
    )


def _build_client(
    *,
    master_values: list[list[str]] | None = None,
    log_values: list[list[str]] | None = None,
) -> GoogleSheetsClient:
    settings = get_google_sheets_settings(secrets=_configured_secrets())
    client = FakeSheetsClient(
        {
            settings.base_spreadsheet_id: FakeSpreadsheet(
                {
                    settings.base_worksheet_name: FakeWorksheet(master_values or []),
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
        now_provider=lambda: datetime(2026, 6, 1, 21, 0, tzinfo=UTC),
    )


def _build_client_from_dataframe(
    master_df: pd.DataFrame,
    *,
    log_values: list[list[str]] | None = None,
) -> GoogleSheetsClient:
    return _build_client(
        master_values=[
            list(master_df.columns),
            *_stringify_rows(master_df.values.tolist()),
        ],
        log_values=log_values,
    )


def _build_fake_sheets_client_from_dataframe(master_df: pd.DataFrame) -> FakeSheetsClient:
    client = _build_client_from_dataframe(master_df)
    return client._sheets_client


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
