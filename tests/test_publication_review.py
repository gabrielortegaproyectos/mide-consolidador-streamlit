from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.pipeline_runner import PipelineResult
from app.services.publication_review import build_publication_review_state
from app.services.validation_summary import READY, build_validation_summary
from app.ui.upload_panel import _snapshot_pipeline_result


def test_publication_review_ready_when_career_and_faculty_are_confirmed(
    tmp_path: Path,
) -> None:
    artifacts = _write_artifacts(
        tmp_path,
        extra_consolidated={
            "FACULTAD": ["Ingenieria", "Ingenieria"],
            "ESCUELA": ["Computacion", "Computacion"],
            "GRADO": ["Licenciatura", "Licenciatura"],
        },
    )

    summary = build_validation_summary(artifacts)
    review = build_publication_review_state(
        summary,
        career_confirmed=True,
        faculty_confirmed=True,
    )

    assert summary.status == READY
    assert review.ready is True
    assert review.status_label == "Listo"
    assert review.blocking_reasons == []


def test_publication_review_blocks_when_career_is_empty(tmp_path: Path) -> None:
    summary = build_validation_summary(
        _write_artifacts(
            tmp_path,
            extra_consolidated={
                "CARRERA": ["", ""],
                "FACULTAD": ["Ingenieria", "Ingenieria"],
            },
        )
    )

    review = build_publication_review_state(
        summary,
        career_confirmed=True,
        faculty_confirmed=True,
    )

    assert review.ready is False
    assert (
        "La carrera detectada esta vacia. Revisa el consolidado antes de publicar online."
        in review.blocking_reasons
    )


def test_publication_review_blocks_when_faculty_is_empty(tmp_path: Path) -> None:
    summary = build_validation_summary(
        _write_artifacts(
            tmp_path,
            extra_consolidated={
                "FACULTAD": ["", ""],
            },
        )
    )

    review = build_publication_review_state(
        summary,
        career_confirmed=True,
        faculty_confirmed=True,
    )

    assert review.ready is False
    assert (
        "La facultad detectada esta vacia. Revisa el consolidado antes de publicar online."
        in review.blocking_reasons
    )


def test_publication_review_exposes_warnings_and_requires_confirmation(
    tmp_path: Path,
) -> None:
    summary = build_validation_summary(
        _write_artifacts(
            tmp_path,
            extra_consolidated={
                "FACULTAD": ["Ingenieria", "Ingenieria"],
            },
        )
    )

    review = build_publication_review_state(
        summary,
        pipeline_warnings=["Advertencia ETL"],
        career_confirmed=True,
        faculty_confirmed=True,
    )

    assert summary.status == READY
    assert review.warnings == ["Advertencia ETL"]
    assert review.requires_warning_confirmation is True
    assert (
        "Debes confirmar que revisaste las advertencias del pipeline."
        in review.blocking_reasons
    )


def test_local_download_artifact_remains_available_when_publication_review_blocks(
    tmp_path: Path,
) -> None:
    artifacts = _write_artifacts(
        tmp_path,
        extra_consolidated={
            "FACULTAD": ["", ""],
        },
    )
    result = PipelineResult(
        output_dir=tmp_path,
        artifacts=artifacts,
        warnings=[],
        pipeline_version="test-version",
    )

    snapshot = _snapshot_pipeline_result(
        result=result,
        uploaded_files={},
        metadata={"Fuente de metadatos": "PDF, matriz y catalogos JSON"},
    )
    review = build_publication_review_state(
        snapshot["summary"],
        career_confirmed=True,
        faculty_confirmed=True,
    )

    assert review.ready is False
    assert snapshot["artifacts"]["consolidated_excel"]["name"] == "tributacion_final.xlsx"
    assert snapshot["artifacts"]["consolidated_excel"]["bytes"]


def _write_artifacts(
    tmp_path: Path,
    *,
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
    pd.DataFrame(
        [
            {
                "SEMESTRE": "1",
                "SEMESTRE_PDF": "1",
                "ASIGNATURA_MATRIZ": "A",
                "ASIGNATURA_PDF": "A",
                "TIPO_MATCH": "EXACTO",
                "SCORE": "1",
            }
        ]
    ).to_csv(matching, index=False)
    pd.DataFrame(
        [
            {
                "CARRERA": "Informatica",
                "CARRERA_BASE": "Informatica",
                "ASIGNATURA": "A",
                "CODIGO_OFICIAL": "INF101",
                "ESTADO_CODIGO": "MATCH_OK",
            }
        ]
    ).to_csv(codes, index=False)

    return {
        "consolidated_excel": consolidated,
        "matching_matriz_pdf_csv": matching,
        "matching_codigos_csv": codes,
    }
