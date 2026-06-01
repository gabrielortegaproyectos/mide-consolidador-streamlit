from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.services.validation_summary import (
    NEEDS_REVIEW,
    READY,
    READY_WITH_WARNINGS,
    ValidationSummary,
)


STATUS_LABELS = {
    READY: "Listo",
    READY_WITH_WARNINGS: "Listo con advertencias",
    NEEDS_REVIEW: "Requiere revision",
}


@dataclass(frozen=True)
class PublicationReviewState:
    ready: bool
    status_label: str
    warnings: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    requires_warning_confirmation: bool = False


def build_publication_review_state(
    summary: ValidationSummary,
    *,
    pipeline_warnings: Sequence[str] = (),
    career_confirmed: bool = False,
    faculty_confirmed: bool = False,
    warnings_confirmed: bool = False,
) -> PublicationReviewState:
    warnings = merge_publication_warnings(summary, pipeline_warnings)
    blocking_reasons: list[str] = []

    if not summary.career:
        blocking_reasons.append(
            "La carrera detectada esta vacia. Revisa el consolidado antes de publicar online."
        )
    if not summary.faculty:
        blocking_reasons.append(
            "La facultad detectada esta vacia. Revisa el consolidado antes de publicar online."
        )
    if summary.status == NEEDS_REVIEW:
        blocking_reasons.append(
            "El estado de validacion requiere revision antes de habilitar la publicacion online."
        )
    if not career_confirmed:
        blocking_reasons.append("Debes confirmar la carrera detectada.")
    if not faculty_confirmed:
        blocking_reasons.append("Debes confirmar la facultad detectada.")
    if warnings and not warnings_confirmed:
        blocking_reasons.append(
            "Debes confirmar que revisaste las advertencias del pipeline."
        )

    return PublicationReviewState(
        ready=not blocking_reasons,
        status_label=STATUS_LABELS.get(summary.status, summary.status),
        warnings=warnings,
        blocking_reasons=blocking_reasons,
        requires_warning_confirmation=bool(warnings),
    )


def merge_publication_warnings(
    summary: ValidationSummary,
    pipeline_warnings: Sequence[str] = (),
) -> list[str]:
    warnings: list[str] = []
    for warning in [*summary.warnings, *pipeline_warnings]:
        text = str(warning).strip()
        if text and text not in warnings:
            warnings.append(text)
    return warnings
