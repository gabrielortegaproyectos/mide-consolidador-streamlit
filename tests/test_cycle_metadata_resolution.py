from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tributacion.ciclo_catalog import (
    enrich_meta_with_tipo_ciclo,
    infer_tipo_ciclo_from_max_semestre,
)
from tributacion.pipeline import run_pipeline_result


def test_infer_tipo_ciclo_from_matrix_duration() -> None:
    assert infer_tipo_ciclo_from_max_semestre(8) == "8_SEM_Licenciatura_super_titulacion"
    assert infer_tipo_ciclo_from_max_semestre(9) == "9_SEM_Licenciatura_Titulacion"
    assert infer_tipo_ciclo_from_max_semestre(10) == "10_SEM_Licenciatura_Titulacion"
    assert infer_tipo_ciclo_from_max_semestre(7) is None


def test_manual_cycle_catalog_enriches_missing_metadata_from_career() -> None:
    meta = enrich_meta_with_tipo_ciclo({"CARRERA": "CONTADOR AUDITOR"})

    assert meta["GRADO"] == "PREGRADO"
    assert meta["FACULTAD"]
    assert meta["ESCUELA"] == "CONTADOR AUDITOR"
    assert meta["TIPO_CICLO"] == "8_SEM_Licenciatura_super_titulacion"


def test_manual_cycle_catalog_keeps_explicit_metadata() -> None:
    meta = enrich_meta_with_tipo_ciclo(
        {
            "CARRERA": "CONTADOR AUDITOR",
            "FACULTAD": "FACULTAD DECLARADA",
            "TIPO_CICLO": "TIPO_DECLARADO",
        }
    )

    assert meta["FACULTAD"] == "FACULTAD DECLARADA"
    assert meta["TIPO_CICLO"] == "TIPO_DECLARADO"


def test_pipeline_uses_pdf_career_to_enrich_matrix_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "Plan de Estudios Contador Auditor Julio 2025.pdf"
    matrix_path = tmp_path / "matriz.xlsx"
    output_path = tmp_path / "salida.xlsx"
    pdf_path.write_bytes(b"pdf")
    matrix_path.write_bytes(b"xlsx")

    captured_meta: dict[str, str] = {}

    def fake_parse_matrix(*args, **kwargs):
        captured_meta.update(kwargs["meta"])
        return pd.DataFrame(
            {"NIVEL O SEMESTRE": [1], "ASIGNATURA": ["Intro"], "N° DE CRÉDITOS": [5]}
        )

    with (
        patch(
            "tributacion.pipeline.parse_pdf",
            return_value=pd.DataFrame(
                {
                    "CARRERA": ["CONTADOR AUDITOR"],
                    "semestre": [1],
                    "asignatura": ["Intro"],
                }
            ),
        ),
        patch("tributacion.pipeline.parse_matrix", side_effect=fake_parse_matrix),
        patch("tributacion.pipeline.extract_matrix_courses", return_value=pd.DataFrame()),
        patch("tributacion.pipeline.normalize_df_nombre_ra_with_local_catalog", side_effect=lambda df: df),
        patch("tributacion.pipeline.merge_horas", side_effect=lambda df, *args, **kwargs: df),
        patch("tributacion.pipeline.apply_subject_codes", side_effect=lambda df, **kwargs: df),
    ):
        result = run_pipeline_result(pdf_path, matrix_path, output_path)

    assert captured_meta["CARRERA"] == "CONTADOR AUDITOR"
    assert captured_meta["GRADO"] == "PREGRADO"
    assert captured_meta["ESCUELA"] == "CONTADOR AUDITOR"
    assert captured_meta["TIPO_CICLO"] == "8_SEM_Licenciatura_super_titulacion"
    assert result.artifacts.consolidated_excel == output_path
