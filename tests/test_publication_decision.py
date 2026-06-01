from __future__ import annotations

import pandas as pd

from app.services.publication_decision import (
    ACTION_APPEND,
    ACTION_CANCEL,
    ACTION_REPLACE,
    CASE_EXACT_MATCH,
    CASE_FACULTY_CONFLICT,
    CASE_INVALID_METADATA,
    CASE_NEW_CAREER,
    CASE_POSSIBLE_DUPLICATE,
    build_publication_decision_state,
    classify_master_career_matches,
    detect_existing_publication,
)
from app.services.validation_summary import ValidationSummary


def test_detect_existing_publication_returns_new_career_without_matches() -> None:
    detection = classify_master_career_matches(
        pd.DataFrame(
            [
                {"FACULTAD": "Salud", "CARRERA": "Nutricion", "ASIGNATURA": "A"},
            ]
        ),
        faculty="Ingenieria",
        career="Informatica",
    )

    assert detection.case_type == CASE_NEW_CAREER
    assert detection.suggested_action == ACTION_APPEND
    assert detection.rows_to_replace == 0
    assert detection.matches == []


def test_detect_existing_publication_returns_exact_match_and_counts_rows() -> None:
    detection = classify_master_career_matches(
        pd.DataFrame(
            [
                {"FACULTAD": "Ingeniería", "CARRERA": "Informática", "ASIGNATURA": "A"},
                {"FACULTAD": "Ingenieria", "CARRERA": " Informatica ", "ASIGNATURA": "B"},
                {"FACULTAD": "Salud", "CARRERA": "Nutricion", "ASIGNATURA": "C"},
            ]
        ),
        faculty="Ingenieria",
        career="Informatica",
    )

    assert detection.case_type == CASE_EXACT_MATCH
    assert detection.suggested_action == ACTION_REPLACE
    assert detection.rows_to_replace == 2
    assert detection.matches[0].current_rows == 2


def test_detect_existing_publication_returns_faculty_conflict() -> None:
    detection = classify_master_career_matches(
        pd.DataFrame(
            [
                {"FACULTAD": "Salud", "CARRERA": "Nutricion", "ASIGNATURA": "A"},
                {"FACULTAD": "Ciencias", "CARRERA": "Nutricion", "ASIGNATURA": "B"},
            ]
        ),
        faculty="Ingenieria",
        career="Nutricion",
    )

    assert detection.case_type == CASE_FACULTY_CONFLICT
    assert detection.suggested_action == ACTION_CANCEL
    assert detection.rows_to_replace == 0
    assert {match.existing_faculty for match in detection.matches} == {
        "Salud",
        "Ciencias",
    }


def test_detect_existing_publication_returns_possible_duplicate() -> None:
    detection = classify_master_career_matches(
        pd.DataFrame(
            [
                {
                    "FACULTAD": "Ingenieria",
                    "CARRERA": "Ingenieria en Computacion",
                    "ASIGNATURA": "A",
                },
            ]
        ),
        faculty="Ingenieria",
        career="Ingenieria Computacional",
    )

    assert detection.case_type == CASE_POSSIBLE_DUPLICATE
    assert detection.suggested_action == ACTION_CANCEL
    assert detection.matches[0].current_rows == 1
    assert detection.matches[0].similarity is not None


def test_detect_existing_publication_returns_invalid_metadata() -> None:
    summary = ValidationSummary(
        status="listo_para_descargar",
        career="",
        faculty="Ingenieria",
    )

    detection = detect_existing_publication(summary, master_df=pd.DataFrame())

    assert detection.case_type == CASE_INVALID_METADATA
    assert detection.suggested_action == ACTION_CANCEL
    assert detection.rows_to_replace == 0


def test_detect_existing_publication_only_reads_master_sheet() -> None:
    client = _ReadOnlyClient(
        pd.DataFrame(
            [
                {"FACULTAD": "Ingenieria", "CARRERA": "Informatica", "ASIGNATURA": "A"},
            ]
        )
    )

    detection = detect_existing_publication(
        ValidationSummary(
            status="listo_para_descargar",
            career="Informatica",
            faculty="Ingenieria",
        ),
        client=client,
    )

    assert detection.case_type == CASE_EXACT_MATCH
    assert client.load_calls == 1
    assert client.append_calls == 0
    assert client.replace_calls == 0


def test_build_publication_decision_state_serializes_selected_action() -> None:
    detection = classify_master_career_matches(
        pd.DataFrame(),
        faculty="Ingenieria",
        career="Informatica",
    )

    state = build_publication_decision_state(
        detection,
        selected_action=ACTION_APPEND,
        enabled=True,
        review_ready=True,
    )

    assert state["case_type"] == CASE_NEW_CAREER
    assert state["suggested_action"] == ACTION_APPEND
    assert state["selected_action"] == ACTION_APPEND
    assert state["enabled"] is True
    assert state["review_ready"] is True


class _ReadOnlyClient:
    def __init__(self, master_df: pd.DataFrame) -> None:
        self.master_df = master_df
        self.load_calls = 0
        self.append_calls = 0
        self.replace_calls = 0

    def load_master_sheet(self) -> pd.DataFrame:
        self.load_calls += 1
        return self.master_df.copy()

    def append_consolidated_rows(self, *args, **kwargs) -> None:
        del args, kwargs
        self.append_calls += 1
        raise AssertionError("append_consolidated_rows should not be called")

    def replace_career_rows(self, *args, **kwargs) -> None:
        del args, kwargs
        self.replace_calls += 1
        raise AssertionError("replace_career_rows should not be called")
