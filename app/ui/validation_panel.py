from __future__ import annotations

import streamlit as st

from app.services.validation_summary import (
    NEEDS_REVIEW,
    READY,
    READY_WITH_WARNINGS,
    ValidationSummary,
)


STATUS_LABELS = {
    READY: "Listo para descargar",
    READY_WITH_WARNINGS: "Descargar con advertencias",
    NEEDS_REVIEW: "Requiere revision",
}


def render_validation_summary(summary: ValidationSummary) -> None:
    st.subheader("Resumen de validacion")

    if summary.status == READY:
        st.success(STATUS_LABELS[summary.status])
    elif summary.status == READY_WITH_WARNINGS:
        st.warning(STATUS_LABELS[summary.status])
    else:
        st.error(STATUS_LABELS[summary.status])

    col_rows, col_match, col_codes = st.columns(3)
    col_rows.metric("Filas generadas", summary.total_rows)
    col_match.metric("Columnas", summary.total_columns)
    col_codes.metric("Match matriz/PDF", _format_match_rate(summary.match_rate))

    if summary.match_counts:
        st.markdown("**Matching matriz/PDF**")
        st.dataframe(_counts_table(summary.match_counts), hide_index=True, use_container_width=True)

    if summary.code_counts:
        st.markdown("**Codigos de asignatura**")
        st.dataframe(_counts_table(summary.code_counts), hide_index=True, use_container_width=True)

    if summary.main_columns:
        st.markdown("**Columnas principales**")
        st.dataframe(
            [{"Columna": column} for column in summary.main_columns],
            hide_index=True,
            use_container_width=True,
        )

    if summary.warnings:
        for warning in summary.warnings:
            st.warning(warning)

    if not summary.problematic_subjects.empty:
        st.markdown("**Asignaturas problematicas**")
        st.dataframe(summary.problematic_subjects, hide_index=True, use_container_width=True)


def _format_match_rate(value: float | None) -> str:
    if value is None:
        return "Sin datos"
    return f"{value:.0%}"


def _counts_table(counts: dict[str, int]) -> list[dict[str, int | str]]:
    return [{"Estado": state, "Cantidad": count} for state, count in counts.items()]
