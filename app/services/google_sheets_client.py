from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

import gspread
import pandas as pd

from app.services.google_sheets_config import (
    GoogleSheetsSettings,
    build_google_service_account_credentials,
    get_google_sheets_settings,
)

REQUIRED_PUBLICATION_COLUMNS = ("FACULTAD", "CARRERA")
AUDIT_LOG_COLUMNS = (
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
)


@dataclass(frozen=True)
class PublicationMetadata:
    operation_type: str
    facultad: str
    carrera: str
    career_key: str | None = None
    pipeline_version: str | None = None
    source_pdf_name: str | None = None
    source_matrix_name: str | None = None
    validation_status: str | None = None
    warnings: list[str] = field(default_factory=list)
    publication_id: str | None = None
    run_id: str | None = None


@dataclass(frozen=True)
class PublicationResult:
    success: bool
    operation_type: str
    facultad: str
    carrera: str
    career_key: str
    rows_before: int
    rows_replaced: int
    rows_published: int
    result_status: str
    published_at: str
    error_message: str | None = None


class GoogleSheetsClient:
    def __init__(
        self,
        *,
        sheets_client: Any | None = None,
        secrets: dict[str, Any] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._sheets_client = sheets_client
        self._secrets = secrets
        self._now_provider = now_provider or _utcnow

    def load_master_sheet(self) -> pd.DataFrame:
        return _worksheet_to_dataframe(self._base_worksheet())

    def find_existing_career_rows(
        self,
        master_df: pd.DataFrame,
        facultad: str,
        carrera: str,
    ) -> pd.DataFrame:
        return find_existing_career_rows(master_df, facultad, carrera)

    def append_consolidated_rows(
        self,
        df: pd.DataFrame,
        metadata: PublicationMetadata,
    ) -> PublicationResult:
        published_at = self._timestamp()
        try:
            master_worksheet = self._base_worksheet()
            master_df = _worksheet_to_dataframe(master_worksheet)
            prepared_df, normalized_metadata = _prepare_publication(
                df,
                metadata,
                master_df.columns,
            )
            existing_rows = find_existing_career_rows(
                master_df,
                normalized_metadata.facultad,
                normalized_metadata.carrera,
            )
            if not existing_rows.empty:
                raise ValueError(
                    "La carrera ya existe en BASE_ESTRUCTURAL; use replace."
                )
            _append_rows_to_master(master_worksheet, master_df, prepared_df)
            result = PublicationResult(
                success=True,
                operation_type="append",
                facultad=normalized_metadata.facultad,
                carrera=normalized_metadata.carrera,
                career_key=_metadata_career_key(normalized_metadata),
                rows_before=0,
                rows_replaced=0,
                rows_published=len(prepared_df),
                result_status="published",
                published_at=published_at,
            )
        except Exception as exc:
            result = _build_failed_result(
                metadata,
                operation_type="append",
                error_message=str(exc),
                published_at=published_at,
            )
        return self._append_audit_or_result(result, metadata)

    def replace_career_rows(
        self,
        df: pd.DataFrame,
        metadata: PublicationMetadata,
    ) -> PublicationResult:
        published_at = self._timestamp()
        try:
            master_worksheet = self._base_worksheet()
            master_df = _worksheet_to_dataframe(master_worksheet)
            prepared_df, normalized_metadata = _prepare_publication(
                df,
                metadata,
                master_df.columns,
            )
            existing_rows = find_existing_career_rows(
                master_df,
                normalized_metadata.facultad,
                normalized_metadata.carrera,
            )
            master_without_existing = _drop_career_rows(
                master_df,
                normalized_metadata.facultad,
                normalized_metadata.carrera,
            )
            updated_master = pd.concat(
                [master_without_existing, prepared_df],
                ignore_index=True,
            )
            _rewrite_sheet(master_worksheet, updated_master)
            result = PublicationResult(
                success=True,
                operation_type="replace",
                facultad=normalized_metadata.facultad,
                carrera=normalized_metadata.carrera,
                career_key=_metadata_career_key(normalized_metadata),
                rows_before=len(existing_rows),
                rows_replaced=len(existing_rows),
                rows_published=len(prepared_df),
                result_status="published",
                published_at=published_at,
            )
        except Exception as exc:
            result = _build_failed_result(
                metadata,
                operation_type="replace",
                error_message=str(exc),
                published_at=published_at,
            )
        return self._append_audit_or_result(result, metadata)

    def append_audit_log(
        self,
        result: PublicationResult,
        metadata: PublicationMetadata,
    ) -> None:
        settings = self._settings()
        log_worksheet = self._log_worksheet()
        log_df = _worksheet_to_dataframe(log_worksheet)
        log_columns = list(log_df.columns) or list(AUDIT_LOG_COLUMNS)
        entry = build_audit_log_entry(result, metadata, settings=settings)
        row = [entry.get(column, "") for column in log_columns]
        if log_df.columns.empty:
            log_worksheet.update([log_columns, row])
            return
        log_worksheet.append_row(row, value_input_option="USER_ENTERED")

    def _append_audit_or_result(
        self,
        result: PublicationResult,
        metadata: PublicationMetadata,
    ) -> PublicationResult:
        try:
            self.append_audit_log(result, metadata)
        except Exception as exc:
            return replace(
                result,
                result_status="published_without_audit"
                if result.success
                else "failed_without_audit",
                error_message=_merge_error_messages(
                    result.error_message,
                    f"Audit log error: {exc}",
                ),
            )
        return result

    def _settings(self) -> GoogleSheetsSettings:
        return get_google_sheets_settings(self._secrets)

    def _client(self) -> Any:
        if self._sheets_client is None:
            credentials = build_google_service_account_credentials(self._secrets)
            if credentials is None:
                raise ValueError(
                    "Google Sheets integration is not enabled for this environment."
                )
            self._sheets_client = gspread.authorize(credentials)
        return self._sheets_client

    def _base_worksheet(self) -> Any:
        settings = self._settings()
        return (
            self._client()
            .open_by_key(settings.base_spreadsheet_id)
            .worksheet(settings.base_worksheet_name)
        )

    def _log_worksheet(self) -> Any:
        settings = self._settings()
        return (
            self._client()
            .open_by_key(settings.log_spreadsheet_id)
            .worksheet(settings.log_worksheet_name)
        )

    def _timestamp(self) -> str:
        return self._now_provider().astimezone(UTC).replace(microsecond=0).isoformat()


def load_master_sheet(
    *,
    sheets_client: Any | None = None,
    secrets: dict[str, Any] | None = None,
) -> pd.DataFrame:
    return GoogleSheetsClient(
        sheets_client=sheets_client,
        secrets=secrets,
    ).load_master_sheet()


def find_existing_career_rows(
    master_df: pd.DataFrame,
    facultad: str,
    carrera: str,
) -> pd.DataFrame:
    _validate_required_columns(master_df)
    career_key = build_career_key(facultad, carrera)
    mask = _career_key_series(master_df) == career_key
    return master_df.loc[mask].copy()


def append_consolidated_rows(
    df: pd.DataFrame,
    metadata: PublicationMetadata,
    *,
    sheets_client: Any | None = None,
    secrets: dict[str, Any] | None = None,
) -> PublicationResult:
    return GoogleSheetsClient(
        sheets_client=sheets_client,
        secrets=secrets,
    ).append_consolidated_rows(df, metadata)


def replace_career_rows(
    df: pd.DataFrame,
    metadata: PublicationMetadata,
    *,
    sheets_client: Any | None = None,
    secrets: dict[str, Any] | None = None,
) -> PublicationResult:
    return GoogleSheetsClient(
        sheets_client=sheets_client,
        secrets=secrets,
    ).replace_career_rows(df, metadata)


def append_audit_log(
    result: PublicationResult,
    metadata: PublicationMetadata,
    *,
    sheets_client: Any | None = None,
    secrets: dict[str, Any] | None = None,
) -> None:
    GoogleSheetsClient(
        sheets_client=sheets_client,
        secrets=secrets,
    ).append_audit_log(result, metadata)


def build_audit_log_entry(
    result: PublicationResult,
    metadata: PublicationMetadata,
    *,
    settings: GoogleSheetsSettings,
) -> dict[str, Any]:
    return {
        "publication_id": metadata.publication_id or str(uuid.uuid4()),
        "run_id": metadata.run_id or "",
        "published_at": result.published_at,
        "operation_type": result.operation_type,
        "base_spreadsheet_id": settings.base_spreadsheet_id,
        "base_worksheet_name": settings.base_worksheet_name,
        "log_spreadsheet_id": settings.log_spreadsheet_id,
        "log_worksheet_name": settings.log_worksheet_name,
        "facultad": result.facultad,
        "carrera": result.carrera,
        "career_key": result.career_key,
        "rows_before": result.rows_before,
        "rows_replaced": result.rows_replaced,
        "rows_published": result.rows_published,
        "pipeline_version": metadata.pipeline_version or "",
        "source_pdf_name": metadata.source_pdf_name or "",
        "source_matrix_name": metadata.source_matrix_name or "",
        "validation_status": metadata.validation_status or "",
        "warnings": " | ".join(metadata.warnings),
        "result_status": result.result_status,
        "error_message": result.error_message or "",
    }


def normalize_key(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def build_career_key(facultad: object, carrera: object) -> str:
    return normalize_key(f"{facultad} {carrera}")


def _prepare_publication(
    df: pd.DataFrame,
    metadata: PublicationMetadata,
    master_columns: Sequence[str],
) -> tuple[pd.DataFrame, PublicationMetadata]:
    if df.empty:
        raise ValueError("El consolidado no contiene filas para publicar.")
    _validate_required_columns(df)
    normalized_metadata = _normalize_metadata(metadata)
    df_career_keys = {
        build_career_key(facultad, carrera)
        for facultad, carrera in zip(
            df["FACULTAD"],
            df["CARRERA"],
            strict=False,
        )
    }
    if len(df_career_keys) != 1:
        raise ValueError(
            "El consolidado debe contener filas de una sola facultad/carrera."
        )
    if normalized_metadata.career_key not in df_career_keys:
        raise ValueError(
            "La metadata de publicacion no coincide con FACULTAD + CARRERA."
        )
    aligned_df = _align_columns(df, master_columns)
    return aligned_df, normalized_metadata


def _normalize_metadata(metadata: PublicationMetadata) -> PublicationMetadata:
    career_key = metadata.career_key or build_career_key(
        metadata.facultad,
        metadata.carrera,
    )
    return replace(metadata, career_key=career_key)


def _metadata_career_key(metadata: PublicationMetadata) -> str:
    return _normalize_metadata(metadata).career_key or ""


def _align_columns(
    df: pd.DataFrame,
    master_columns: Sequence[str],
) -> pd.DataFrame:
    if len(master_columns) == 0:
        return df.copy()
    expected_columns = list(master_columns)
    actual_columns = list(df.columns)
    if set(actual_columns) != set(expected_columns):
        missing_columns = [col for col in expected_columns if col not in actual_columns]
        extra_columns = [col for col in actual_columns if col not in expected_columns]
        messages: list[str] = []
        if missing_columns:
            messages.append(
                f"Faltan columnas requeridas: {', '.join(missing_columns)}."
            )
        if extra_columns:
            messages.append(
                f"Hay columnas no permitidas: {', '.join(extra_columns)}."
            )
        raise ValueError(" ".join(messages))
    return df.loc[:, expected_columns].copy()


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing_columns = [
        column for column in REQUIRED_PUBLICATION_COLUMNS if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(
            f"Faltan columnas obligatorias: {', '.join(missing_columns)}."
        )
    for column in REQUIRED_PUBLICATION_COLUMNS:
        normalized = df[column].fillna("").map(normalize_key)
        if (normalized == "").any():
            raise ValueError(
                f"La columna {column} debe tener valor en todas las filas."
            )


def _career_key_series(df: pd.DataFrame) -> pd.Series:
    return df.apply(
        lambda row: build_career_key(row["FACULTAD"], row["CARRERA"]),
        axis=1,
    )


def _drop_career_rows(
    master_df: pd.DataFrame,
    facultad: str,
    carrera: str,
) -> pd.DataFrame:
    if master_df.empty:
        return master_df.copy()
    career_key = build_career_key(facultad, carrera)
    mask = _career_key_series(master_df) != career_key
    return master_df.loc[mask].copy()


def _append_rows_to_master(
    worksheet: Any,
    master_df: pd.DataFrame,
    new_rows_df: pd.DataFrame,
) -> None:
    rows = _dataframe_rows(new_rows_df)
    if not rows:
        return
    if master_df.columns.empty:
        worksheet.update([list(new_rows_df.columns), *rows])
        return
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def _rewrite_sheet(worksheet: Any, df: pd.DataFrame) -> None:
    rows = [list(df.columns), *_dataframe_rows(df)]
    worksheet.clear()
    if rows:
        worksheet.update(rows)


def _worksheet_to_dataframe(worksheet: Any) -> pd.DataFrame:
    values = worksheet.get_all_values()
    if not values:
        return pd.DataFrame()
    header = [str(value) for value in values[0]]
    rows = values[1:]
    if not any(header):
        return pd.DataFrame(rows)
    return pd.DataFrame(rows, columns=header)


def _dataframe_rows(df: pd.DataFrame) -> list[list[Any]]:
    serializable_df = df.where(pd.notna(df), "")
    return serializable_df.values.tolist()


def _build_failed_result(
    metadata: PublicationMetadata,
    *,
    operation_type: str,
    error_message: str,
    published_at: str,
) -> PublicationResult:
    normalized_metadata = _normalize_metadata(metadata)
    return PublicationResult(
        success=False,
        operation_type=operation_type,
        facultad=normalized_metadata.facultad,
        carrera=normalized_metadata.carrera,
        career_key=normalized_metadata.career_key or "",
        rows_before=0,
        rows_replaced=0,
        rows_published=0,
        result_status="failed",
        published_at=published_at,
        error_message=error_message,
    )


def _merge_error_messages(
    first_message: str | None,
    second_message: str,
) -> str:
    if not first_message:
        return second_message
    return f"{first_message} | {second_message}"


def _utcnow() -> datetime:
    return datetime.now(UTC)
