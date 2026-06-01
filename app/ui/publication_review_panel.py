from __future__ import annotations

import pandas as pd
import streamlit as st

from app.services.google_sheets_client import GoogleSheetsClient
from app.services.google_sheets_config import get_google_sheets_config_status
from app.services.publication_decision import (
    ACTION_LABELS,
    ACTION_OPTIONS,
    ACTION_REPLACE,
    CASE_INVALID_METADATA,
    CASE_LABELS,
    build_publication_decision_state,
    build_replacement_confirmation_state,
    detect_existing_publication,
    REPLACEMENT_CONFIRMATION_TOKEN,
)
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
PUBLICATION_DECISION_STATE_KEY = "publication_decision_state"
_CAREER_CONFIRMATION_KEY = "publication_review_career_confirmed"
_FACULTY_CONFIRMATION_KEY = "publication_review_faculty_confirmed"
_WARNINGS_CONFIRMATION_KEY = "publication_review_warnings_confirmed"
_PUBLICATION_ACTION_KEY = "publication_review_selected_action"
_REPLACEMENT_CONFIRMATION_INPUT_KEY = "publication_review_replace_confirmation_text"
_REPLACEMENT_CONFIRMED_KEY = "publication_review_replacement_confirmed"


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

    _render_online_detection_section(
        summary,
        review_ready=review_state.ready,
        google_sheets_enabled=google_sheets_status.enabled,
    )


def reset_publication_review_state() -> None:
    for key in [
        PUBLICATION_REVIEW_READY_STATE_KEY,
        PUBLICATION_DECISION_STATE_KEY,
        _CAREER_CONFIRMATION_KEY,
        _FACULTY_CONFIRMATION_KEY,
        _WARNINGS_CONFIRMATION_KEY,
        _PUBLICATION_ACTION_KEY,
        _REPLACEMENT_CONFIRMATION_INPUT_KEY,
        _REPLACEMENT_CONFIRMED_KEY,
    ]:
        st.session_state.pop(key, None)
    st.session_state[PUBLICATION_REVIEW_READY_STATE_KEY] = False
    st.session_state[PUBLICATION_DECISION_STATE_KEY] = build_publication_decision_state(
        None,
        enabled=False,
        review_ready=False,
    )


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


def _render_online_detection_section(
    summary: ValidationSummary,
    *,
    review_ready: bool,
    google_sheets_enabled: bool,
) -> None:
    st.subheader("Deteccion en base online")

    if not google_sheets_enabled:
        st.caption(
            "La deteccion online requiere secretos de Google Sheets. La descarga local sigue disponible."
        )
        st.session_state[PUBLICATION_DECISION_STATE_KEY] = build_publication_decision_state(
            None,
            enabled=False,
            review_ready=review_ready,
        )
        return

    invalid_detection = detect_existing_publication(summary, master_df=pd.DataFrame())
    if invalid_detection.case_type == CASE_INVALID_METADATA:
        _render_detection_result(
            summary,
            invalid_detection,
            review_ready=review_ready,
            enabled=True,
        )
        st.error(
            "La metadata detectada esta incompleta. Corrige FACULTAD y CARRERA antes de continuar."
        )
        return

    if not review_ready:
        st.info("Completa la revision humana antes de consultar BASE_ESTRUCTURAL.")
        st.session_state[PUBLICATION_DECISION_STATE_KEY] = build_publication_decision_state(
            None,
            enabled=True,
            review_ready=False,
        )
        return

    try:
        detection = detect_existing_publication(summary, client=GoogleSheetsClient())
    except Exception as exc:
        st.error("No fue posible consultar BASE_ESTRUCTURAL.")
        st.info(str(exc))
        st.session_state[PUBLICATION_DECISION_STATE_KEY] = build_publication_decision_state(
            None,
            enabled=True,
            review_ready=True,
            error_message=str(exc),
        )
        return

    _render_detection_result(
        summary,
        detection,
        review_ready=True,
        enabled=True,
    )


def _render_detection_result(
    summary: ValidationSummary,
    detection,
    *,
    review_ready: bool,
    enabled: bool,
) -> None:
    st.markdown(f"**Clasificacion:** {CASE_LABELS.get(detection.case_type, detection.case_type)}")
    st.markdown(
        f"**Accion sugerida:** {ACTION_LABELS.get(detection.suggested_action, detection.suggested_action)}"
    )
    col_replace, col_publish = st.columns(2)
    col_replace.metric("Filas actuales que se reemplazarian", detection.rows_to_replace)
    col_publish.metric("Filas nuevas a publicar", summary.total_rows)

    if detection.matches:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "carrera existente": match.existing_career,
                        "facultad existente": match.existing_faculty,
                        "filas actuales": match.current_rows,
                        "tipo de coincidencia": CASE_LABELS.get(
                            match.match_type,
                            match.match_type,
                        ),
                        "similitud": ""
                        if match.similarity is None
                        else f"{match.similarity:.2f}",
                        "ultima fecha de publicacion": match.last_published_at,
                        "usuario/publicador": match.publisher,
                        "accion sugerida": ACTION_LABELS.get(
                            match.suggested_action,
                            match.suggested_action,
                        ),
                    }
                    for match in detection.matches
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.caption("No se detectaron coincidencias en BASE_ESTRUCTURAL.")

    if detection.requires_manual_selection:
        st.warning(
            "Este caso requiere una decision manual explicita antes de cualquier publicacion futura."
        )

    selected_action = st.radio(
        "Decision para pasos posteriores",
        options=ACTION_OPTIONS,
        index=None,
        format_func=lambda action: ACTION_LABELS[action],
        key=_PUBLICATION_ACTION_KEY,
    )

    replacement_confirmation_text = ""
    if selected_action == ACTION_REPLACE:
        existing_match = detection.matches[0] if detection.matches else None
        st.error(
            "Advertencia: reemplazar una carrera existente es una operacion critica."
        )
        existing_col, new_col = st.columns(2)
        with existing_col:
            st.markdown("**Actual en BASE_ESTRUCTURAL**")
            st.markdown(
                f"**Facultad:** {_value_or_fallback(existing_match.existing_faculty if existing_match else '')}"
            )
            st.markdown(
                f"**Carrera:** {_value_or_fallback(existing_match.existing_career if existing_match else '')}"
            )
            st.metric("Filas actuales afectadas", detection.rows_to_replace)
        with new_col:
            st.markdown("**Nuevo consolidado**")
            st.markdown(f"**Facultad:** {_value_or_fallback(summary.faculty)}")
            st.markdown(f"**Carrera:** {_value_or_fallback(summary.career)}")
            st.metric("Filas nuevas", summary.total_rows)

        st.warning(
            "Esta accion reemplazara las filas actuales de la carrera seleccionada en la base online."
        )
        replacement_confirmation_text = st.text_input(
            "Escribe REEMPLAZAR para confirmar que deseas reemplazar esta carrera.",
            key=_REPLACEMENT_CONFIRMATION_INPUT_KEY,
        )
    else:
        st.session_state[_REPLACEMENT_CONFIRMATION_INPUT_KEY] = ""

    replacement_confirmation = build_replacement_confirmation_state(
        selected_action,
        confirmation_text=replacement_confirmation_text,
    )
    st.session_state[_REPLACEMENT_CONFIRMED_KEY] = replacement_confirmation["confirmed"]

    if selected_action == ACTION_REPLACE:
        if replacement_confirmation["confirmed"]:
            st.success("Confirmacion textual valida. El reemplazo ya no puede avanzar por un click accidental.")
        else:
            st.info(
                f"El reemplazo seguira bloqueado hasta escribir exactamente {REPLACEMENT_CONFIRMATION_TOKEN}."
            )

    st.session_state[PUBLICATION_DECISION_STATE_KEY] = build_publication_decision_state(
        detection,
        selected_action=selected_action,
        replacement_confirmation_text=replacement_confirmation_text,
        rows_to_publish=summary.total_rows,
        enabled=enabled,
        review_ready=review_ready,
    )
