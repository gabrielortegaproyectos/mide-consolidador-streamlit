from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pandas as pd

from app.services.google_sheets_client import (
    GoogleSheetsClient,
    PublicationMetadata,
    PublicationResult,
    build_audit_log_entry,
    find_existing_career_rows,
    normalize_key,
)
from app.services.google_sheets_config import get_google_sheets_settings


def test_normalize_key_matches_catalog_style() -> None:
    assert normalize_key("  Ingeniería   en   Gestión  ") == "ingenieria en gestion"
    assert normalize_key("Facultád de Salud") == "facultad de salud"


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
    assert entry["base_worksheet_name"] == "BASE"
    assert entry["log_worksheet_name"] == "LOG"


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
