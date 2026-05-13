from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from app.services.pipeline_runner import (
    PipelineInputs,
    UploadedPipelineError,
    cleanup_pipeline_result,
    run_uploaded_pipeline,
)
from tributacion.exceptions import PipelineInputFileError
from tributacion.types import PipelineArtifacts, PipelineResult as EtlPipelineResult


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test")
    return path


def _etl_result(output_xlsx: Path) -> EtlPipelineResult:
    return EtlPipelineResult(
        dataframe=pd.DataFrame({"ok": [1]}),
        artifacts=PipelineArtifacts(
            consolidated_excel=output_xlsx,
            horas_pdf_csv=output_xlsx.with_name("tributacion_final_horas_pdf.csv"),
            matching_matriz_pdf_csv=output_xlsx.with_name("tributacion_final_matching.csv"),
            matching_codigos_csv=output_xlsx.with_name(
                "tributacion_final_subject_codes_matching.csv"
            ),
        ),
        warnings=["Advertencia de prueba"],
        pipeline_version="66ca6b9",
    )


def test_run_uploaded_pipeline_calls_public_etl_contract(tmp_path: Path) -> None:
    pdf_path = _touch(tmp_path / "uploads" / "plan.pdf")
    matrix_path = _touch(tmp_path / "uploads" / "matriz.xlsx")
    output_root = tmp_path / "runs"

    with patch("app.services.pipeline_runner.run_pipeline_result") as mock_run:
        mock_run.side_effect = lambda **kwargs: _etl_result(kwargs["output_xlsx"])

        result = run_uploaded_pipeline(
            PipelineInputs(
                pdf_path=pdf_path,
                matrix_path=matrix_path,
                career="Ingenieria en Informatica",
                faculty="Ingenieria",
                school="Escuela de Informatica",
                degree="Pregrado",
                cycle_type="Semestral",
                output_root=output_root,
            )
        )

    mock_run.assert_called_once()
    call = mock_run.call_args.kwargs
    assert call["pdf_path"] == pdf_path
    assert call["matrix_xlsx"] == matrix_path
    assert call["sheet_name"] == "Asignaturas - RA"
    assert call["meta"] == {
        "CARRERA": "Ingenieria en Informatica",
        "FACULTAD": "Ingenieria",
        "ESCUELA": "Escuela de Informatica",
        "GRADO": "Pregrado",
        "TIPO_CICLO": "Semestral",
    }
    assert result.output_dir.parent == output_root
    assert result.pipeline_version == "66ca6b9"
    assert result.warnings == ["Advertencia de prueba"]
    assert set(result.artifacts) == {
        "consolidated_excel",
        "horas_pdf_csv",
        "matching_matriz_pdf_csv",
        "matching_codigos_csv",
    }

    cleanup_pipeline_result(result)
    assert not result.output_dir.exists()


def test_run_uploaded_pipeline_omits_blank_optional_metadata(tmp_path: Path) -> None:
    pdf_path = _touch(tmp_path / "plan.pdf")
    matrix_path = _touch(tmp_path / "matriz.xlsx")

    with patch("app.services.pipeline_runner.run_pipeline_result") as mock_run:
        mock_run.side_effect = lambda **kwargs: _etl_result(kwargs["output_xlsx"])

        run_uploaded_pipeline(
            PipelineInputs(
                pdf_path=pdf_path,
                matrix_path=matrix_path,
                career="  Enfermeria  ",
                faculty="",
                school=None,
                degree="  ",
                cycle_type="No especificado",
                output_root=tmp_path,
            )
        )

    assert mock_run.call_args.kwargs["meta"] == {"CARRERA": "Enfermeria"}


def test_run_uploaded_pipeline_cleans_output_dir_on_controlled_error(
    tmp_path: Path,
) -> None:
    pdf_path = _touch(tmp_path / "plan.pdf")
    matrix_path = _touch(tmp_path / "matriz.xlsx")
    output_root = tmp_path / "runs"

    with patch("app.services.pipeline_runner.run_pipeline_result") as mock_run:
        mock_run.side_effect = PipelineInputFileError("PDF no encontrado")

        with pytest.raises(UploadedPipelineError, match="PDF no encontrado"):
            run_uploaded_pipeline(
                PipelineInputs(
                    pdf_path=pdf_path,
                    matrix_path=matrix_path,
                    career="Ingenieria",
                    output_root=output_root,
                )
            )

    assert output_root.exists()
    assert list(output_root.iterdir()) == []


def test_run_uploaded_pipeline_cleans_output_dir_on_unexpected_error(
    tmp_path: Path,
) -> None:
    pdf_path = _touch(tmp_path / "plan.pdf")
    matrix_path = _touch(tmp_path / "matriz.xlsx")
    output_root = tmp_path / "runs"

    with patch("app.services.pipeline_runner.run_pipeline_result") as mock_run:
        mock_run.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            run_uploaded_pipeline(
                PipelineInputs(
                    pdf_path=pdf_path,
                    matrix_path=matrix_path,
                    career="Ingenieria",
                    output_root=output_root,
                )
            )

    assert output_root.exists()
    assert list(output_root.iterdir()) == []
