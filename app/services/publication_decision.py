from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from app.services.google_sheets_client import (
    GoogleSheetsClient,
    build_career_key,
    normalize_key,
)
from app.services.validation_summary import ValidationSummary

ACTION_APPEND = "append"
ACTION_REPLACE = "replace"
ACTION_CANCEL = "cancel"

CASE_NEW_CAREER = "new_career"
CASE_EXACT_MATCH = "exact_match"
CASE_POSSIBLE_DUPLICATE = "possible_duplicate"
CASE_FACULTY_CONFLICT = "faculty_conflict"
CASE_INVALID_METADATA = "invalid_metadata"

CASE_LABELS = {
    CASE_NEW_CAREER: "Nueva carrera",
    CASE_EXACT_MATCH: "Carrera existente exacta",
    CASE_POSSIBLE_DUPLICATE: "Posible duplicado",
    CASE_FACULTY_CONFLICT: "Conflicto de facultad",
    CASE_INVALID_METADATA: "Metadata incompleta",
}

ACTION_LABELS = {
    ACTION_APPEND: "Agregar como nueva carrera",
    ACTION_REPLACE: "Reemplazar carrera existente",
    ACTION_CANCEL: "Cancelar publicacion",
}

ACTION_OPTIONS = [
    ACTION_APPEND,
    ACTION_REPLACE,
    ACTION_CANCEL,
]

_DATE_COLUMNS = (
    "published_at",
    "PUBLISHED_AT",
    "fecha_publicacion",
    "FECHA_PUBLICACION",
    "FECHA DE PUBLICACION",
    "FECHA DE PUBLICACIÓN",
)
_PUBLISHER_COLUMNS = (
    "publicador",
    "PUBLICADOR",
    "usuario",
    "USUARIO",
    "published_by",
    "PUBLISHED_BY",
)


@dataclass(frozen=True)
class PublicationCandidateMatch:
    existing_career: str
    existing_faculty: str
    current_rows: int
    match_type: str
    similarity: float | None = None
    last_published_at: str = ""
    publisher: str = ""
    suggested_action: str = ACTION_CANCEL


@dataclass(frozen=True)
class PublicationDetectionResult:
    case_type: str
    suggested_action: str
    rows_to_replace: int
    career_key: str
    matches: list[PublicationCandidateMatch] = field(default_factory=list)
    requires_manual_selection: bool = False


def detect_existing_publication(
    summary: ValidationSummary,
    *,
    client: GoogleSheetsClient | Any | None = None,
    master_df: pd.DataFrame | None = None,
    similarity_threshold: float = 85.0,
) -> PublicationDetectionResult:
    faculty = str(summary.faculty or "")
    career = str(summary.career or "")
    career_key = build_career_key(faculty, career)
    if not normalize_key(faculty) or not normalize_key(career):
        return PublicationDetectionResult(
            case_type=CASE_INVALID_METADATA,
            suggested_action=ACTION_CANCEL,
            rows_to_replace=0,
            career_key=career_key,
            requires_manual_selection=True,
        )

    if master_df is None:
        active_client = client or GoogleSheetsClient()
        master_df = active_client.load_master_sheet()

    return classify_master_career_matches(
        master_df,
        faculty=faculty,
        career=career,
        similarity_threshold=similarity_threshold,
    )


def classify_master_career_matches(
    master_df: pd.DataFrame,
    *,
    faculty: str,
    career: str,
    similarity_threshold: float = 85.0,
) -> PublicationDetectionResult:
    career_key = build_career_key(faculty, career)
    normalized_faculty = normalize_key(faculty)
    normalized_career = normalize_key(career)
    if not normalized_faculty or not normalized_career:
        return PublicationDetectionResult(
            case_type=CASE_INVALID_METADATA,
            suggested_action=ACTION_CANCEL,
            rows_to_replace=0,
            career_key=career_key,
            requires_manual_selection=True,
        )

    if master_df.empty:
        return PublicationDetectionResult(
            case_type=CASE_NEW_CAREER,
            suggested_action=ACTION_APPEND,
            rows_to_replace=0,
            career_key=career_key,
        )

    _validate_master_columns(master_df)
    matches = _collect_candidate_matches(
        master_df,
        faculty=faculty,
        career=career,
        similarity_threshold=similarity_threshold,
    )

    exact_matches = [
        match for match in matches if match.match_type == CASE_EXACT_MATCH
    ]
    faculty_conflicts = [
        match for match in matches if match.match_type == CASE_FACULTY_CONFLICT
    ]
    possible_duplicates = [
        match for match in matches if match.match_type == CASE_POSSIBLE_DUPLICATE
    ]

    if exact_matches:
        return PublicationDetectionResult(
            case_type=CASE_EXACT_MATCH,
            suggested_action=ACTION_REPLACE,
            rows_to_replace=sum(match.current_rows for match in exact_matches),
            career_key=career_key,
            matches=matches,
        )
    if faculty_conflicts:
        return PublicationDetectionResult(
            case_type=CASE_FACULTY_CONFLICT,
            suggested_action=ACTION_CANCEL,
            rows_to_replace=0,
            career_key=career_key,
            matches=matches,
            requires_manual_selection=True,
        )
    if possible_duplicates:
        return PublicationDetectionResult(
            case_type=CASE_POSSIBLE_DUPLICATE,
            suggested_action=ACTION_CANCEL,
            rows_to_replace=0,
            career_key=career_key,
            matches=matches,
            requires_manual_selection=True,
        )
    return PublicationDetectionResult(
        case_type=CASE_NEW_CAREER,
        suggested_action=ACTION_APPEND,
        rows_to_replace=0,
        career_key=career_key,
    )


def build_publication_decision_state(
    detection: PublicationDetectionResult | None,
    *,
    selected_action: str | None = None,
    enabled: bool,
    review_ready: bool,
    error_message: str | None = None,
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "review_ready": review_ready,
        "error_message": error_message or "",
        "case_type": detection.case_type if detection else "",
        "suggested_action": detection.suggested_action if detection else "",
        "selected_action": selected_action or "",
        "rows_to_replace": detection.rows_to_replace if detection else 0,
        "career_key": detection.career_key if detection else "",
        "requires_manual_selection": (
            detection.requires_manual_selection if detection else False
        ),
        "matches": [
            asdict(match)
            for match in (detection.matches if detection else [])
        ],
    }


def _collect_candidate_matches(
    master_df: pd.DataFrame,
    *,
    faculty: str,
    career: str,
    similarity_threshold: float,
) -> list[PublicationCandidateMatch]:
    normalized_faculty = normalize_key(faculty)
    normalized_career = normalize_key(career)
    grouped_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in master_df.to_dict(orient="records"):
        row_faculty = normalize_key(row.get("FACULTAD", ""))
        row_career = normalize_key(row.get("CARRERA", ""))
        if not row_faculty or not row_career:
            continue
        grouped_rows.setdefault((row_faculty, row_career), []).append(row)

    matches: list[PublicationCandidateMatch] = []
    for (row_faculty, row_career), rows in grouped_rows.items():
        career_similarity = round(
            float(fuzz.token_sort_ratio(normalized_career, row_career)),
            2,
        )
        combined_similarity = round(
            float(
                fuzz.token_sort_ratio(
                    build_career_key(faculty, career),
                    build_career_key(rows[0].get("FACULTAD", ""), rows[0].get("CARRERA", "")),
                )
            ),
            2,
        )

        if row_faculty == normalized_faculty and row_career == normalized_career:
            match_type = CASE_EXACT_MATCH
            similarity = 100.0
            suggested_action = ACTION_REPLACE
        elif (
            career_similarity >= similarity_threshold
            and row_faculty != normalized_faculty
        ):
            match_type = CASE_FACULTY_CONFLICT
            similarity = combined_similarity
            suggested_action = ACTION_CANCEL
        elif (
            career_similarity >= similarity_threshold
            and row_faculty == normalized_faculty
        ):
            match_type = CASE_POSSIBLE_DUPLICATE
            similarity = combined_similarity
            suggested_action = ACTION_CANCEL
        else:
            continue

        matches.append(
            PublicationCandidateMatch(
                existing_career=_display_value(rows, "CARRERA"),
                existing_faculty=_display_value(rows, "FACULTAD"),
                current_rows=len(rows),
                match_type=match_type,
                similarity=similarity,
                last_published_at=_last_non_empty(rows, _DATE_COLUMNS),
                publisher=_last_non_empty(rows, _PUBLISHER_COLUMNS),
                suggested_action=suggested_action,
            )
        )

    return sorted(
        matches,
        key=lambda item: (
            item.match_type != CASE_EXACT_MATCH,
            -(item.similarity or 0),
            -item.current_rows,
            item.existing_faculty,
            item.existing_career,
        ),
    )


def _display_value(rows: list[dict[str, Any]], column: str) -> str:
    return _last_non_empty(rows, (column,))


def _last_non_empty(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> str:
    for row in reversed(rows):
        for column in columns:
            text = str(row.get(column, "") or "").strip()
            if text:
                return text
    return ""


def _validate_master_columns(master_df: pd.DataFrame) -> None:
    missing_columns = [
        column for column in ("FACULTAD", "CARRERA") if column not in master_df.columns
    ]
    if missing_columns:
        raise ValueError(
            "La hoja BASE_ESTRUCTURAL no contiene las columnas requeridas: "
            f"{', '.join(missing_columns)}."
        )
