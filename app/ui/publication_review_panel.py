from __future__ import annotations

import streamlit as st

from app.services.google_sheets_config import get_google_sheets_config_status
from app.services.publication_review import (
    STATUS_LABELS,
    build_publication_review_state,
)
from app.services.validation_summary import (
    NEEDS_REVIEW,
    READY,
    READY_WITH_WARNINGS,
    ValidationSummary,
)


PUBLICATION_REVIEW_READY_STATE_KEY = "publication_review_ready"
_CAREER_CONFIRMATION_KEY = "publication_review_career_confirmed"
_FACULTY_CONFIRMATION_KEY = "publication_review_faculty_confirmed"
_WARNINGS_CONFIRMATION_KEY = "publication_review_warnings_confirmed"


def render_publication_review_panel(
    summary: ValidationSummary,
    *,
    pipeline_warnings: list[str] | None = None,
) -> None:
    pipeline_warnings = pipeline_warnings or []
    google_sheets_status = get_google_sheets_config_status()

    st.subheader("Revision antes de publicar online")
    _render_validation_status(summary)
    _render_detected_metadata(summary)

    career_confirmed = st.checkbox(
        "Confirmo que la carrera detectada es correcta.",
        key=_CAREER_CONFIRMATION_KEY,
    )
    faculty_confirmed = st.checkbox(
        "Confirmo que la facultad detectada es correcta.",
        key=_FACULTY_CONFIRMATION_KEY,
    )

    review_state = build_publication_review_state(
        summary,
        pipeline_warnings=pipeline_warnings,
        career_confirmed=career_confirmed,
        faculty_confirmed=faculty_confirmed,
        warnings_confirmed=bool(st.session_state.get(_WARNINGS_CONFIRMATION_KEY, False)),
    )

    if review_state.warnings:
        with st.expander("Advertencias del pipeline", expanded=True):
            for warning in review_state.warnings:
                st.warning(warning)
        warnings_confirmed = st.checkbox(
            "Revise las advertencias del pipeline.",
            key=_WARNINGS_CONFIRMATION_KEY,
        )
        review_state = build_publication_review_state(
            summary,
            pipeline_warnings=pipeline_warnings,
            career_confirmed=career_confirmed,
            faculty_confirmed=faculty_confirmed,
            warnings_confirmed=warnings_confirmed,
        )
    else:
        st.caption("Sin advertencias del pipeline para esta corrida.")
        st.session_state[_WARNINGS_CONFIRMATION_KEY] = False

    st.session_state[PUBLICATION_REVIEW_READY_STATE_KEY] = review_state.ready

    if review_state.ready:
        st.success(
            "Revision humana completada. La publicacion online podra continuar en pasos posteriores."
        )
    else:
        if (
            summary.status == NEEDS_REVIEW
            or not summary.career
            or not summary.faculty
        ):
            st.error("La publicacion online sigue bloqueada.")
        else:
            st.warning("Completa la revision humana antes de continuar.")
        for reason in review_state.blocking_reasons:
            st.write(f"- {reason}")

    if google_sheets_status.enabled:
        st.caption(
            "La integracion Google Sheets esta disponible, pero esta etapa aun no escribe online."
        )
    else:
        st.info(
            "La publicacion online no esta configurada. Puedes descargar el consolidado localmente."
        )


def reset_publication_review_state() -> None:
    for key in [
        PUBLICATION_REVIEW_READY_STATE_KEY,
        _CAREER_CONFIRMATION_KEY,
        _FACULTY_CONFIRMATION_KEY,
        _WARNINGS_CONFIRMATION_KEY,
    ]:
        st.session_state.pop(key, None)
    st.session_state[PUBLICATION_REVIEW_READY_STATE_KEY] = False


def _render_validation_status(summary: ValidationSummary) -> None:
    label = STATUS_LABELS.get(summary.status, summary.status)
    st.markdown(f"**Estado de validacion:** {label}")
    if summary.status == READY:
        st.success(label)
    elif summary.status == READY_WITH_WARNINGS:
        st.warning(label)
    else:
        st.error(label)


def _render_detected_metadata(summary: ValidationSummary) -> None:
    st.markdown(f"**Carrera detectada:** {_value_or_fallback(summary.career)}")
    st.markdown(f"**Facultad detectada:** {_value_or_fallback(summary.faculty)}")
    st.markdown(f"**Escuela detectada:** {_value_or_fallback(summary.school)}")
    st.markdown(f"**Grado detectado:** {_value_or_fallback(summary.degree)}")

    col_rows, col_subjects, col_semesters = st.columns(3)
    col_rows.metric("Numero de filas", summary.total_rows)
    col_subjects.metric("Numero de asignaturas", summary.subject_count)
    col_semesters.metric(
        "Semestres detectados",
        summary.max_semester if summary.max_semester is not None else "Sin datos",
    )

    finalization = (
        ", ".join(summary.finalization_labels)
        if summary.finalization_labels
        else "No aplica"
    )
    st.markdown(f"**Finalizacion detectada:** {finalization}")


def _value_or_fallback(value: str) -> str:
    text = str(value).strip()
    if text:
        return text
    return "No detectada"
