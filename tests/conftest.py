from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.services.google_sheets_client import PublicationMetadata, PublicationResult


@pytest.fixture
def sample_etl_artifacts(tmp_path: Path) -> dict[str, Path]:
    consolidated = tmp_path / "tributacion_final.xlsx"
    horas_pdf = tmp_path / "tributacion_final_horas_pdf.csv"
    matching = tmp_path / "tributacion_final_matching.csv"
    codes = tmp_path / "tributacion_final_subject_codes_matching.csv"

    pd.DataFrame(
        {
            "NIVEL O SEMESTRE": [1, 2],
            "ASIGNATURA": ["Matematica", "Fisica"],
            "N° DE CREDITOS": [5, 4],
        }
    ).to_excel(consolidated, index=False)
    pd.DataFrame(
        {
            "semestre": [1, 2],
            "asignatura": ["Matematica", "Fisica"],
            "sct": [5, 4],
        }
    ).to_csv(horas_pdf, index=False)
    pd.DataFrame(
        [
            {
                "SEMESTRE": "1",
                "SEMESTRE_PDF": "1",
                "ASIGNATURA_MATRIZ": "Matematica",
                "ASIGNATURA_PDF": "Matematica",
                "TIPO_MATCH": "EXACTO",
                "SCORE": "1",
            },
            {
                "SEMESTRE": "2",
                "SEMESTRE_PDF": "2",
                "ASIGNATURA_MATRIZ": "Fisica",
                "ASIGNATURA_PDF": "Fisica",
                "TIPO_MATCH": "FUZZY",
                "SCORE": "0.92",
            },
        ]
    ).to_csv(matching, index=False)
    pd.DataFrame(
        [
            {
                "CARRERA": "Ingenieria",
                "CARRERA_BASE": "Ingenieria",
                "ASIGNATURA": "Matematica",
                "CODIGO_OFICIAL": "MAT101",
                "ESTADO_CODIGO": "MATCH_OK",
            },
            {
                "CARRERA": "Ingenieria",
                "CARRERA_BASE": "Ingenieria",
                "ASIGNATURA": "Fisica",
                "CODIGO_OFICIAL": "FIS101",
                "ESTADO_CODIGO": "MATCH_OK",
            },
        ]
    ).to_csv(codes, index=False)

    return {
        "consolidated_excel": consolidated,
        "horas_pdf_csv": horas_pdf,
        "matching_matriz_pdf_csv": matching,
        "matching_codigos_csv": codes,
    }


@pytest.fixture
def publication_consolidated_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "FACULTAD": "Salud",
                "CARRERA": "Nutricion",
                "ASIGNATURA": "Bioquimica",
                "CODIGO": "NUT101",
            },
            {
                "FACULTAD": "Salud",
                "CARRERA": "Nutricion",
                "ASIGNATURA": "Fisiologia",
                "CODIGO": "NUT102",
            },
        ]
    )


@pytest.fixture
def online_master_with_existing_career_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "FACULTAD": "Salud",
                "CARRERA": "Nutricion",
                "ASIGNATURA": "Anatomia",
                "CODIGO": "NUT001",
            },
            {
                "FACULTAD": "Salud",
                "CARRERA": "Nutricion",
                "ASIGNATURA": "Quimica",
                "CODIGO": "NUT002",
            },
            {
                "FACULTAD": "Salud",
                "CARRERA": "Enfermeria",
                "ASIGNATURA": "Clinica",
                "CODIGO": "ENF001",
            },
        ]
    )


@pytest.fixture
def online_master_without_career_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "FACULTAD": "Salud",
                "CARRERA": "Enfermeria",
                "ASIGNATURA": "Clinica",
                "CODIGO": "ENF001",
            }
        ]
    )


@pytest.fixture
def publication_metadata() -> PublicationMetadata:
    return PublicationMetadata(
        operation_type="append",
        facultad="Salud",
        carrera="Nutricion",
        career_key="salud nutricion",
        pipeline_version="test-version",
        source_pdf_name="plan.pdf",
        source_matrix_name="matriz.xlsx",
        validation_status="ok",
        warnings=["warning 1", "warning 2"],
        publication_id="publication-1",
        run_id="run-1",
    )


@pytest.fixture
def publication_result() -> PublicationResult:
    return PublicationResult(
        success=True,
        operation_type="append",
        facultad="Salud",
        carrera="Nutricion",
        career_key="salud nutricion",
        rows_before=0,
        rows_replaced=0,
        rows_published=2,
        result_status="published",
        published_at="2026-06-02T00:00:00+00:00",
        publication_id="publication-1",
    )
