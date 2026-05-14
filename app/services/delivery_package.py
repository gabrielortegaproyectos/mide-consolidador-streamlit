from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.services.validation_summary import (
    NEEDS_REVIEW,
    READY,
    READY_WITH_WARNINGS,
    ValidationSummary,
)


STATUS_LABELS = {
    READY: "Listo para descargar",
    READY_WITH_WARNINGS: "Descargar con advertencias",
    NEEDS_REVIEW: "Requiere correccion",
}


@dataclass(frozen=True)
class UploadedFileTrace:
    name: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class DeliveryPackage:
    zip_bytes: bytes
    validation_summary_md: str


def trace_file(path: Path) -> UploadedFileTrace:
    data = Path(path).read_bytes()
    return UploadedFileTrace(
        name=Path(path).name,
        sha256=sha256(data).hexdigest(),
        size_bytes=len(data),
    )


def build_delivery_package(
    *,
    artifacts: dict[str, dict[str, bytes | str]],
    summary: ValidationSummary,
    uploaded_files: dict[str, UploadedFileTrace],
    metadata: dict[str, str],
    pipeline_version: str,
    warnings: list[str],
    generated_at: datetime | None = None,
) -> DeliveryPackage:
    generated_at = generated_at or datetime.now().astimezone()
    summary_md = build_validation_summary_markdown(
        summary=summary,
        uploaded_files=uploaded_files,
        metadata=metadata,
        pipeline_version=pipeline_version,
        warnings=warnings,
        generated_at=generated_at,
    )
    return DeliveryPackage(
        zip_bytes=_build_zip_bytes(artifacts, summary_md),
        validation_summary_md=summary_md,
    )


def build_validation_summary_markdown(
    *,
    summary: ValidationSummary,
    uploaded_files: dict[str, UploadedFileTrace],
    metadata: dict[str, str],
    pipeline_version: str,
    warnings: list[str],
    generated_at: datetime,
) -> str:
    lines = [
        "# Resumen de validacion MIDE",
        "",
        "## Estado",
        "",
        f"- Estado final: {STATUS_LABELS.get(summary.status, summary.status)}",
        f"- Fecha/hora de corrida: {generated_at.isoformat(timespec='seconds')}",
        f"- Version ETL: {pipeline_version}",
        f"- Filas generadas: {summary.total_rows}",
        f"- Columnas generadas: {summary.total_columns}",
        f"- Tasa de match matriz/PDF: {_format_match_rate(summary.match_rate)}",
        "",
        "## Metadatos de ejecucion",
        "",
        *_metadata_lines(metadata),
        "",
        "## Archivos subidos",
        "",
        *_uploaded_file_lines(uploaded_files),
        "",
        "## Conteos de matching matriz/PDF",
        "",
        *_count_lines(summary.match_counts),
        "",
        "## Conteos de codigos de asignatura",
        "",
        *_count_lines(summary.code_counts),
        "",
        "## Advertencias y limitaciones",
        "",
        *_warning_lines(summary.warnings, warnings),
        "",
        "## Asignaturas problematicas",
        "",
        *_problematic_subject_lines(summary),
        "",
    ]
    return "\n".join(lines)


def _build_zip_bytes(
    artifacts: dict[str, dict[str, bytes | str]],
    summary_md: str,
) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for artifact in artifacts.values():
            name = str(artifact["name"])
            if name == "resumen_validacion.md":
                continue
            data = artifact["bytes"]
            archive.writestr(name, data)
        archive.writestr("resumen_validacion.md", summary_md)
    return buffer.getvalue()


def _metadata_lines(metadata: dict[str, str]) -> list[str]:
    rows = [f"- {key}: {value}" for key, value in metadata.items() if value]
    return rows or ["- Sin metadatos adicionales registrados."]


def _uploaded_file_lines(uploaded_files: dict[str, UploadedFileTrace]) -> list[str]:
    if not uploaded_files:
        return ["- Sin archivos registrados."]
    return [
        f"- {label}: {trace.name} | sha256={trace.sha256} | bytes={trace.size_bytes}"
        for label, trace in uploaded_files.items()
    ]


def _count_lines(counts: dict[str, int]) -> list[str]:
    if not counts:
        return ["- Sin datos."]
    return [f"- {state}: {count}" for state, count in counts.items()]


def _warning_lines(summary_warnings: list[str], pipeline_warnings: list[str]) -> list[str]:
    warnings = [*summary_warnings, *pipeline_warnings]
    if not warnings:
        return ["- Sin advertencias registradas."]
    return [f"- {warning}" for warning in warnings]


def _problematic_subject_lines(summary: ValidationSummary) -> list[str]:
    if summary.problematic_subjects.empty:
        return ["- Sin asignaturas problematicas registradas."]
    return [
        "- {subject} | {problem} | {detail}".format(
            subject=row.get("Asignatura", ""),
            problem=row.get("Problema", ""),
            detail=row.get("Detalle", ""),
        )
        for _, row in summary.problematic_subjects.iterrows()
    ]


def _format_match_rate(value: float | None) -> str:
    if value is None:
        return "Sin datos"
    return f"{value:.0%}"
