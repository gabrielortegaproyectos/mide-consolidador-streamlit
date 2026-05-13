from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


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
