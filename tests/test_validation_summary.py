from pathlib import Path

import pandas as pd

from app.services.validation_summary import (
    NEEDS_REVIEW,
    READY,
    READY_WITH_WARNINGS,
    build_validation_summary,
    expected_excel_fields,
)


def test_expected_excel_fields_documents_core_fields():
    fields = expected_excel_fields()

    assert {"Campo", "Grupo", "Origen", "Uso"}.issubset(fields.columns)
    assert "ASIGNATURA" in fields["Campo"].to_list()
    assert "NIVEL O SEMESTRE" in fields["Campo"].to_list()
    assert not fields.empty


def test_build_validation_summary_reports_ready_state(tmp_path: Path):
    artifacts = _write_artifacts(
        tmp_path,
        matching_rows=[
            {
                "SEMESTRE": "1",
                "SEMESTRE_PDF": "1",
                "ASIGNATURA_MATRIZ": "Matematica",
                "ASIGNATURA_PDF": "Matematica",
                "TIPO_MATCH": "EXACTO",
                "SCORE": "1",
            }
        ],
        code_rows=[
            {
                "CARRERA": "Informatica",
                "CARRERA_BASE": "Informatica",
                "ASIGNATURA": "Matematica",
                "CODIGO_OFICIAL": "MAT101",
                "ESTADO_CODIGO": "MATCH_OK",
            }
        ],
    )

    summary = build_validation_summary(artifacts)

    assert summary.status == READY
    assert summary.total_rows == 2
    assert summary.total_columns == 4
    assert summary.career == "Informatica"
    assert summary.max_semester == 2
    assert summary.subject_count == 2
    assert summary.cycle_labels == ["LICENCIATURA"]
    assert summary.main_columns == ["CARRERA", "CICLO", "NIVEL O SEMESTRE", "ASIGNATURA"]
    assert summary.match_counts == {"EXACTO": 1}
    assert summary.code_counts == {"MATCH_OK": 1}
    assert summary.match_rate == 1
    assert summary.problematic_subjects.empty


def test_build_validation_summary_requires_review_for_sin_match(tmp_path: Path):
    artifacts = _write_artifacts(
        tmp_path,
        matching_rows=[
            {
                "SEMESTRE": "1",
                "SEMESTRE_PDF": "",
                "ASIGNATURA_MATRIZ": "Fisica",
                "ASIGNATURA_PDF": "",
                "TIPO_MATCH": "SIN MATCH",
                "SCORE": "0",
            }
        ],
        code_rows=[],
    )

    summary = build_validation_summary(artifacts)

    assert summary.status == NEEDS_REVIEW
    assert summary.match_rate == 0
    assert not summary.problematic_subjects.empty
    assert summary.problematic_subjects.iloc[0]["Asignatura"] == "Fisica"


def test_build_validation_summary_warns_for_code_issues(tmp_path: Path):
    artifacts = _write_artifacts(
        tmp_path,
        matching_rows=[
            {
                "SEMESTRE": "1",
                "SEMESTRE_PDF": "1",
                "ASIGNATURA_MATRIZ": "Quimica",
                "ASIGNATURA_PDF": "Quimica",
                "TIPO_MATCH": "EXACTO",
                "SCORE": "1",
            }
        ],
        code_rows=[
            {
                "CARRERA": "Informatica",
                "CARRERA_BASE": "Informatica",
                "ASIGNATURA": "Quimica",
                "CODIGO_OFICIAL": "sin codigo",
                "ESTADO_CODIGO": "SIN_MATCH",
            }
        ],
    )

    summary = build_validation_summary(artifacts)

    assert summary.status == READY_WITH_WARNINGS
    assert summary.code_counts == {"SIN_MATCH": 1}
    assert summary.problematic_subjects.iloc[0]["Problema"] == "SIN_MATCH"


def test_build_validation_summary_warns_when_diagnostics_are_missing(tmp_path: Path):
    consolidated = tmp_path / "tributacion_final.xlsx"
    pd.DataFrame({"ASIGNATURA": ["A"]}).to_excel(consolidated, index=False)

    summary = build_validation_summary({"consolidated_excel": consolidated})

    assert summary.status == READY_WITH_WARNINGS
    assert summary.warnings == [
        "No se encontro diagnostico de matching matriz/PDF.",
        "No se encontro diagnostico de codigos de asignatura.",
    ]


def test_build_validation_summary_reports_finalization_labels(tmp_path: Path):
    artifacts = _write_artifacts(
        tmp_path,
        matching_rows=[],
        code_rows=[],
        extra_consolidated={
            "FINALIZACION": ["Gestion", "Investigacion"],
        },
    )

    summary = build_validation_summary(artifacts)

    assert summary.finalization_count == 2
    assert summary.finalization_labels == ["Gestion", "Investigacion"]


def _write_artifacts(
    tmp_path: Path,
    *,
    matching_rows: list[dict[str, str]],
    code_rows: list[dict[str, str]],
    extra_consolidated: dict[str, list[object]] | None = None,
) -> dict[str, Path]:
    consolidated = tmp_path / "tributacion_final.xlsx"
    matching = tmp_path / "tributacion_final_matching.csv"
    codes = tmp_path / "tributacion_final_subject_codes_matching.csv"

    consolidated_data: dict[str, list[object]] = {
        "CARRERA": ["Informatica", "Informatica"],
        "ASIGNATURA": ["A", "B"],
        "NIVEL O SEMESTRE": [1, 2],
        "CICLO": ["LICENCIATURA", "LICENCIATURA"],
    }
    if extra_consolidated:
        consolidated_data.update(extra_consolidated)
    pd.DataFrame(consolidated_data).to_excel(consolidated, index=False)
    pd.DataFrame(matching_rows).to_csv(matching, index=False)
    pd.DataFrame(
        code_rows,
        columns=[
            "CARRERA",
            "CARRERA_BASE",
            "ASIGNATURA",
            "CODIGO_OFICIAL",
            "ESTADO_CODIGO",
        ],
    ).to_csv(codes, index=False)

    return {
        "consolidated_excel": consolidated,
        "matching_matriz_pdf_csv": matching,
        "matching_codigos_csv": codes,
    }

