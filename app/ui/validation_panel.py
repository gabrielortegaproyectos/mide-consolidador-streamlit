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
    st.subheader("Resumen de carrera")

    if summary.status == READY:
        st.success(STATUS_LABELS[summary.status])
    elif summary.status == READY_WITH_WARNINGS:
        st.warning(STATUS_LABELS[summary.status])
    else:
        st.error(STATUS_LABELS[summary.status])

    if summary.career:
        st.markdown(f"**Carrera detectada:** {summary.career}")
    _render_finalization_note(summary)

    col_subjects, col_semesters, col_rows, col_columns = st.columns(4)
    col_subjects.metric("Asignaturas", summary.subject_count)
    col_semesters.metric("Semestres detectados", summary.max_semester or "Sin datos")
    col_rows.metric("Filas del consolidado", summary.total_rows)
    col_columns.metric("Columnas", summary.total_columns)

    if summary.cycle_labels:
        st.caption(f"Ciclos detectados: {', '.join(summary.cycle_labels)}")

    has_technical_logs = _has_technical_logs(summary)
    if summary.problematic_subjects.empty and not summary.warnings:
        st.info("No se detectaron problemas relevantes para mostrar al usuario final.")
    else:
        st.warning("Hay observaciones tecnicas disponibles en logs.")

    if has_technical_logs:
        st.caption("Logs tecnicos disponibles al final del resultado.")

    with st.expander("Logs"):
        st.caption("Detalle para revision tecnica del cruce matriz/PDF, codigos y columnas.")

        tech_cols = st.columns(3)
        tech_cols[0].metric("Match matriz/PDF", _format_match_rate(summary.match_rate))
        tech_cols[1].metric("Estados matching", sum(summary.match_counts.values()))
        tech_cols[2].metric("Estados codigos", sum(summary.code_counts.values()))

        if summary.match_counts:
            st.markdown("**Matching matriz/PDF**")
            st.dataframe(
                _counts_table(summary.match_counts),
                hide_index=True,
                use_container_width=True,
            )

        if summary.code_counts:
            st.markdown("**Codigos de asignatura**")
            st.dataframe(
                _counts_table(summary.code_counts),
                hide_index=True,
                use_container_width=True,
            )

        if summary.main_columns:
            st.markdown("**Columnas principales**")
            st.dataframe(
                [{"Columna": column} for column in summary.main_columns],
                hide_index=True,
                use_container_width=True,
            )

        if summary.warnings:
            st.markdown("**Advertencias tecnicas**")
            for warning in summary.warnings:
                st.warning(warning)

        if not summary.problematic_subjects.empty:
            st.markdown("**Asignaturas para revision experta**")
            st.dataframe(
                summary.problematic_subjects,
                hide_index=True,
                use_container_width=True,
            )


def _format_match_rate(value: float | None) -> str:
    if value is None:
        return "Sin datos"
    return f"{value:.0%}"


def _counts_table(counts: dict[str, int]) -> list[dict[str, int | str]]:
    return [{"Estado": state, "Cantidad": count} for state, count in counts.items()]


def _has_technical_logs(summary: ValidationSummary) -> bool:
    return bool(
        summary.match_counts
        or summary.code_counts
        or summary.main_columns
        or summary.warnings
        or not summary.problematic_subjects.empty
    )


def _render_finalization_note(summary: ValidationSummary) -> None:
    if summary.finalization_count is None:
        return
    if summary.finalization_count > 1:
        labels = ", ".join(summary.finalization_labels)
        st.info(f"Se detectaron {summary.finalization_count} finalizaciones: {labels}.")
    elif summary.finalization_count == 1:
        st.info(f"Se detecto una finalizacion: {summary.finalization_labels[0]}.")
