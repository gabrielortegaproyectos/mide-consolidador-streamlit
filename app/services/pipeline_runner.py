from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tributacion.exceptions import PipelineError
from tributacion.pipeline import run_pipeline_result


DEFAULT_SHEET_NAME = "Asignaturas - RA"


@dataclass(frozen=True)
class PipelineInputs:
    pdf_path: Path
    matrix_path: Path
    career: str
    sheet_name: str = DEFAULT_SHEET_NAME
    faculty: str | None = None
    school: str | None = None
    degree: str | None = None
    cycle_type: str | None = None
    output_root: Path | None = None


@dataclass(frozen=True)
class PipelineResult:
    output_dir: Path
    artifacts: dict[str, Path]
    warnings: list[str]
    pipeline_version: str


class UploadedPipelineError(RuntimeError):
    """Error controlado para que la UI lo muestre sin stack trace tecnico."""


def run_uploaded_pipeline(inputs: PipelineInputs) -> PipelineResult:
    """Ejecuta el ETL contra archivos de una sesion de carga.

    El runner solo conoce la API publica del ETL. No importa parsers internos ni
    escribe fuera de un directorio temporal salvo que el caller entregue
    explicitamente ``output_root``.
    """
    pdf_path = Path(inputs.pdf_path)
    matrix_path = Path(inputs.matrix_path)
    output_dir = _make_output_dir(inputs.output_root)
    output_xlsx = output_dir / "tributacion_final.xlsx"

    try:
        etl_result = run_pipeline_result(
            pdf_path=pdf_path,
            matrix_xlsx=matrix_path,
            output_xlsx=output_xlsx,
            sheet_name=inputs.sheet_name,
            meta=_build_etl_meta(inputs),
        )
    except PipelineError as exc:
        _cleanup_output_dir(output_dir)
        raise UploadedPipelineError(str(exc)) from exc
    except Exception:
        _cleanup_output_dir(output_dir)
        raise

    artifacts = {
        "consolidated_excel": etl_result.artifacts.consolidated_excel,
        "horas_pdf_csv": etl_result.artifacts.horas_pdf_csv,
        "matching_matriz_pdf_csv": etl_result.artifacts.matching_matriz_pdf_csv,
        "matching_codigos_csv": etl_result.artifacts.matching_codigos_csv,
    }
    if etl_result.artifacts.validation_summary is not None:
        artifacts["validation_summary"] = etl_result.artifacts.validation_summary

    return PipelineResult(
        output_dir=output_dir,
        artifacts=artifacts,
        warnings=list(etl_result.warnings),
        pipeline_version=etl_result.pipeline_version,
    )


def cleanup_pipeline_result(result: PipelineResult) -> None:
    """Elimina el directorio temporal asociado a una corrida."""
    _cleanup_output_dir(result.output_dir)


def _build_etl_meta(inputs: PipelineInputs) -> dict[str, str]:
    meta: dict[str, str] = {}
    _add_if_present(meta, "CARRERA", inputs.career)
    _add_if_present(meta, "FACULTAD", inputs.faculty)
    _add_if_present(meta, "ESCUELA", inputs.school)
    _add_if_present(meta, "GRADO", inputs.degree)
    _add_if_present(meta, "TIPO_CICLO", inputs.cycle_type)
    return meta


def _add_if_present(meta: dict[str, str], key: str, value: str | None) -> None:
    if value is None:
        return
    cleaned = value.strip()
    if cleaned and cleaned.lower() != "no especificado":
        meta[key] = cleaned


def _make_output_dir(output_root: Path | None) -> Path:
    if output_root is None:
        return Path(tempfile.mkdtemp(prefix="mide-etl-"))

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="mide-etl-", dir=output_root))


def _cleanup_output_dir(output_dir: Path) -> None:
    shutil.rmtree(output_dir, ignore_errors=True)

