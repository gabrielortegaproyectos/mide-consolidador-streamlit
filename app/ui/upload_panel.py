from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from app.services.delivery_package import build_delivery_package, trace_file
from app.services.google_sheets_client import (
    GoogleSheetsClient,
    PublicationMetadata,
    PublicationResult as PipelinePublicationResult,
)
from app.services.google_sheets_config import get_google_sheets_config_status
from app.services.input_validation import InputValidationResult, validate_excel_input
from app.services.pipeline_runner import (
    PipelineInputs,
    PipelineResult,
    UploadedPipelineError,
    cleanup_pipeline_result,
    run_uploaded_pipeline,
)
from app.services.privacy import (
    generic_processing_error,
    public_error_message,
    upload_size_error,
)
from app.services.publication_decision import (
    ACTION_APPEND,
    ACTION_CANCEL,
    ACTION_REPLACE,
)
from app.services.validation_summary import ValidationSummary, build_validation_summary
from app.ui.publication_review_panel import (
    PUBLICATION_DECISION_STATE_KEY,
    render_publication_result_summary,
    render_publication_review_panel,
    reset_publication_review_state,
)
from app.ui.validation_panel import render_technical_logs, render_validation_summary


RUN_RESULT_STATE_KEY = "pipeline_run_result"


def render_upload_panel() -> None:
    st.subheader("Procesar carrera")
    st.caption("Carga un PDF y una matriz Excel para generar el consolidado y sus diagnosticos.")

    left, right = st.columns(2)
    with left:
        pdf_file = st.file_uploader("PDF de plan de estudio", type=["pdf"])
    with right:
        matrix_file = st.file_uploader("Matriz Excel de tributacion", type=["xlsx"])

    files_ready = pdf_file is not None and matrix_file is not None
    upload_errors = _upload_size_errors(pdf_file, matrix_file)

    run_clicked = st.button(
        "Procesar carrera",
        type="primary",
        disabled=not files_ready or bool(upload_errors),
        use_container_width=True,
    )

    for upload_error in upload_errors:
        st.error(upload_error)

    if run_clicked and files_ready:
        _run_pipeline_from_uploads(
            pdf_file=pdf_file,
            matrix_file=matrix_file,
        )

    if RUN_RESULT_STATE_KEY in st.session_state:
        _render_run_result(st.session_state[RUN_RESULT_STATE_KEY])


def _write_uploaded_matrix(uploaded_file, output_dir: Path) -> Path:
    filename = Path(uploaded_file.name or "matriz.xlsx").name
    matrix_path = output_dir / filename
    matrix_path.write_bytes(uploaded_file.getbuffer())
    return matrix_path


def _write_uploaded_file(uploaded_file, output_dir: Path, fallback_name: str) -> Path:
    filename = Path(uploaded_file.name or fallback_name).name
    output_path = output_dir / filename
    output_path.write_bytes(uploaded_file.getbuffer())
    return output_path


def _render_validation_result(result: InputValidationResult) -> None:
    if result.is_valid:
        st.success("Matriz validada. La estructura base es compatible.")
        return

    for message in result.errors:
        st.error(message.title)
        st.write(message.explanation)
        st.info(message.action)
        if message.technical_detail:
            with st.expander("Detalle tecnico"):
                st.code(message.technical_detail)


def _run_pipeline_from_uploads(
    *,
    pdf_file,
    matrix_file,
) -> None:
    with st.spinner("Validando y procesando ETL..."):
        progress = _ProgressMessages()
        with tempfile.TemporaryDirectory(prefix="mide-upload-") as upload_dir:
            upload_root = Path(upload_dir)
            pdf_path = _write_uploaded_file(pdf_file, upload_root, "plan.pdf")
            matrix_path = _write_uploaded_file(matrix_file, upload_root, "matriz.xlsx")
            progress.add(f"PDF `{Path(pdf_path).name}` recibido.")
            progress.add(f"Matriz `{Path(matrix_path).name}` recibida.")
            uploaded_files = {
                "PDF plan de estudio": trace_file(pdf_path),
                "Matriz Excel tributacion": trace_file(matrix_path),
            }
            progress.add("Validando estructura de la matriz.")
            validation = validate_excel_input(matrix_path)
            if not validation.is_valid:
                progress.add("Validacion detenida: la matriz requiere correccion.")
                _render_validation_result(validation)
                return
            progress.add("Matriz validada. La estructura base es compatible.")

            result: PipelineResult | None = None
            try:
                progress.add("Procesando PDF y matriz con el ETL MIDE.")
                result = run_uploaded_pipeline(
                    PipelineInputs(
                        pdf_path=pdf_path,
                        matrix_path=matrix_path,
                    )
                )
                progress.add("PDF procesado y datos de horas extraidos.")
                progress.add("Matriz procesada y consolidado construido.")
            except UploadedPipelineError as exc:
                progress.add("Procesamiento detenido por un error controlado.")
                st.error("No fue posible procesar los insumos.")
                st.info(public_error_message(str(exc)))
                return
            except Exception:
                progress.add("Procesamiento detenido por un error inesperado.")
                st.error("No fue posible procesar los insumos.")
                st.info(generic_processing_error())
                return

            try:
                progress.add("Preparando previsualizacion y descarga del consolidado.")
                reset_publication_review_state()
                st.session_state[RUN_RESULT_STATE_KEY] = _snapshot_pipeline_result(
                    result=result,
                    uploaded_files=uploaded_files,
                    metadata={
                        "Fuente de metadatos": "PDF, matriz y catalogos JSON",
                    },
                )
            except Exception:
                progress.add("No fue posible preparar la descarga.")
                st.error("No fue posible preparar la descarga.")
                st.info(generic_processing_error())
                return
            finally:
                cleanup_pipeline_result(result)
            progress.add("Consolidado listo para revisar y descargar.")


def _snapshot_pipeline_result(
    *,
    result: PipelineResult,
    uploaded_files: dict,
    metadata: dict[str, str],
) -> dict[str, object]:
    summary = build_validation_summary(result.artifacts)
    artifacts = {
        key: {
            "name": Path(path).name,
            "bytes": Path(path).read_bytes(),
        }
        for key, path in result.artifacts.items()
        if Path(path).exists() and Path(path).is_file()
    }
    package = build_delivery_package(
        artifacts=artifacts,
        summary=summary,
        uploaded_files=uploaded_files,
        metadata=metadata,
        pipeline_version=result.pipeline_version,
        warnings=result.warnings,
    )
    return {
        "summary": summary,
        "warnings": result.warnings,
        "pipeline_version": result.pipeline_version,
        "artifacts": artifacts,
        "uploaded_files": uploaded_files,
        "metadata": metadata,
        "consolidated_preview": _build_consolidated_preview(artifacts),
        "zip_bytes": package.zip_bytes,
        "validation_summary_md": package.validation_summary_md,
    }


def _build_consolidated_preview(
    artifacts: dict[str, dict[str, bytes | str]],
    *,
    max_rows: int = 10,
) -> pd.DataFrame:
    artifact = artifacts.get("consolidated_excel")
    if not artifact:
        return pd.DataFrame()
    data = artifact.get("bytes")
    if not isinstance(data, bytes):
        return pd.DataFrame()
    try:
        return pd.read_excel(BytesIO(data), nrows=max_rows)
    except Exception:
        return pd.DataFrame()


def _upload_size_errors(*uploaded_files) -> list[str]:
    errors: list[str] = []
    for uploaded_file in uploaded_files:
        if uploaded_file is None:
            continue
        size = int(getattr(uploaded_file, "size", 0) or 0)
        filename = str(getattr(uploaded_file, "name", "archivo"))
        error = upload_size_error(filename, size)
        if error is not None:
            errors.append(error)
    return errors


def _render_run_result(result: dict[str, object]) -> None:
    st.divider()
    st.success("Insumos validados y consolidado generado.")
    summary = result["summary"]
    render_validation_summary(summary)

    artifacts = result.get("artifacts", {})
    preview = result.get("consolidated_preview")
    if isinstance(preview, pd.DataFrame) and not preview.empty:
        st.markdown("**Previsualizacion del consolidado**")
        st.dataframe(preview, hide_index=True, use_container_width=True)

    render_technical_logs(summary)

    warnings = result.get("warnings", [])
    if warnings:
        with st.expander("Advertencias del pipeline"):
            for warning in warnings:
                st.warning(str(warning))

    consolidated = artifacts.get("consolidated_excel") if isinstance(artifacts, dict) else None
    if consolidated:
        st.subheader("Descarga local del consolidado")
        st.caption(
            "Esta accion solo descarga el Excel generado en esta sesion. "
            "No modifica Google Sheets."
        )
        st.download_button(
            "Descargar consolidado Excel",
            data=consolidated["bytes"],
            file_name=consolidated["name"],
            mime=_mime_type(str(consolidated["name"])),
            use_container_width=True,
            key="download-consolidated-excel",
        )

    _render_publication_section(
        result,
        pipeline_warnings=[str(warning) for warning in warnings],
    )

    st.caption(f"Version ETL: {result.get('pipeline_version', 'unknown')}")


def _render_publication_section(
    result: dict[str, object],
    *,
    pipeline_warnings: list[str],
) -> None:
    summary = result.get("summary")
    if not isinstance(summary, ValidationSummary):
        return

    google_sheets_status = get_google_sheets_config_status()
    if not google_sheets_status.enabled:
        st.info(
            "La publicacion online no esta configurada en este entorno. "
            "Puedes descargar el consolidado Excel localmente."
        )
        return

    st.subheader("Publicacion online en Google Sheets")
    st.caption(
        "Esta accion modifica BASE_ESTRUCTURAL y registra trazabilidad en "
        "LOG_PUBLICACIONES. No reemplaza la descarga local."
    )

    render_publication_review_panel(
        summary,
        pipeline_warnings=pipeline_warnings,
    )

    decision_state = st.session_state.get(PUBLICATION_DECISION_STATE_KEY, {})
    selected_action = str(decision_state.get("selected_action", "")).strip()
    button_label = _publication_button_label(selected_action)
    button_disabled = not _publication_action_is_available(decision_state)

    if selected_action == ACTION_CANCEL:
        st.warning(
            "La publicacion online quedara cancelada y BASE_ESTRUCTURAL no sera modificada."
        )

    if st.button(
        button_label,
        type="primary",
        use_container_width=True,
        disabled=button_disabled,
        key="publish-consolidated-google-sheets",
    ):
        result["publication_result"] = _execute_publication_action(
            result,
            decision_state=decision_state,
        )

    publication_result = result.get("publication_result")
    if isinstance(publication_result, PipelinePublicationResult):
        render_publication_result_summary(publication_result)


def _publication_button_label(selected_action: str) -> str:
    if selected_action == ACTION_APPEND:
        return "Publicar nueva carrera en Google Sheets"
    if selected_action == ACTION_REPLACE:
        return "Reemplazar carrera en Google Sheets"
    if selected_action == ACTION_CANCEL:
        return "Confirmar cancelacion de publicacion"
    return "Publicar online en Google Sheets"


def _publication_action_is_available(decision_state: dict[str, object]) -> bool:
    selected_action = str(decision_state.get("selected_action", "")).strip()
    if not selected_action:
        return False
    if selected_action == ACTION_CANCEL:
        return True
    return bool(decision_state.get("can_advance", False))


def _execute_publication_action(
    result: dict[str, object],
    *,
    decision_state: dict[str, object],
    client: GoogleSheetsClient | None = None,
) -> PipelinePublicationResult:
    summary = result.get("summary")
    if not isinstance(summary, ValidationSummary):
        return _build_publication_feedback_result(
            operation_type="unknown",
            result_status="failed",
            error_message="No fue posible cargar el resumen del consolidado para publicar.",
        )

    selected_action = str(decision_state.get("selected_action", "")).strip()
    if selected_action == ACTION_CANCEL:
        return _build_publication_feedback_result(
            operation_type="cancelled",
            result_status="cancelled",
            summary=summary,
            error_message="La publicacion online fue cancelada por el usuario.",
        )

    if not str(summary.career).strip() or not str(summary.faculty).strip():
        return _build_publication_feedback_result(
            operation_type=selected_action or "unknown",
            result_status="blocked",
            summary=summary,
            error_message="Completa FACULTAD y CARRERA antes de publicar online.",
        )

    if not decision_state.get("review_ready", False):
        return _build_publication_feedback_result(
            operation_type=selected_action or "unknown",
            result_status="blocked",
            summary=summary,
            error_message="La revision humana debe aprobarse antes de publicar online.",
        )

    if selected_action == ACTION_REPLACE and not decision_state.get(
        "replacement_confirmed",
        False,
    ):
        return _build_publication_feedback_result(
            operation_type=selected_action,
            result_status="blocked",
            summary=summary,
            error_message="Escribe exactamente REEMPLAZAR antes de reemplazar la carrera online.",
            rows_replaced=int(decision_state.get("rows_to_replace", 0) or 0),
        )

    if selected_action not in {ACTION_APPEND, ACTION_REPLACE}:
        return _build_publication_feedback_result(
            operation_type=selected_action or "unknown",
            result_status="blocked",
            summary=summary,
            error_message="Selecciona append, replace o cancel antes de continuar.",
        )

    consolidated_df = _load_consolidated_dataframe_from_result(result)
    if consolidated_df.empty:
        return _build_publication_feedback_result(
            operation_type=selected_action,
            result_status="failed",
            summary=summary,
            error_message="No fue posible cargar el Excel consolidado generado para publicar online.",
        )

    metadata = _build_publication_metadata(
        result,
        summary=summary,
        operation_type=selected_action,
    )
    active_client = client or GoogleSheetsClient()
    try:
        if selected_action == ACTION_APPEND:
            return active_client.append_consolidated_rows(consolidated_df, metadata)
        return active_client.replace_career_rows(consolidated_df, metadata)
    except Exception as exc:
        return _build_publication_feedback_result(
            operation_type=selected_action,
            result_status="failed",
            summary=summary,
            error_message=str(exc),
            rows_replaced=int(decision_state.get("rows_to_replace", 0) or 0)
            if selected_action == ACTION_REPLACE
            else 0,
        )


def _build_publication_metadata(
    result: dict[str, object],
    *,
    summary,
    operation_type: str,
) -> PublicationMetadata:
    uploaded_files = result.get("uploaded_files")
    uploaded_files = uploaded_files if isinstance(uploaded_files, dict) else {}
    pdf_trace = uploaded_files.get("PDF plan de estudio")
    matrix_trace = uploaded_files.get("Matriz Excel tributacion")
    warnings = [str(warning) for warning in result.get("warnings", [])]
    warnings.extend(str(warning) for warning in summary.warnings)
    return PublicationMetadata(
        operation_type=operation_type,
        facultad=summary.faculty,
        carrera=summary.career,
        pipeline_version=str(result.get("pipeline_version", "")),
        source_pdf_name=getattr(pdf_trace, "name", ""),
        source_matrix_name=getattr(matrix_trace, "name", ""),
        source_pdf_trace=pdf_trace,
        source_matrix_trace=matrix_trace,
        validation_status=summary.status,
        warnings=warnings,
    )


def _load_consolidated_dataframe_from_result(result: dict[str, object]) -> pd.DataFrame:
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, dict):
        return pd.DataFrame()
    consolidated = artifacts.get("consolidated_excel")
    if not isinstance(consolidated, dict):
        return pd.DataFrame()
    data = consolidated.get("bytes")
    if not isinstance(data, bytes):
        return pd.DataFrame()
    return pd.read_excel(BytesIO(data)).fillna("")


def _build_publication_feedback_result(
    *,
    operation_type: str,
    result_status: str,
    error_message: str,
    summary=None,
    rows_replaced: int = 0,
) -> PipelinePublicationResult:
    published_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    return PipelinePublicationResult(
        success=result_status == "published",
        operation_type=operation_type,
        facultad="" if summary is None else summary.faculty,
        carrera="" if summary is None else summary.career,
        career_key="",
        rows_before=rows_replaced,
        rows_replaced=rows_replaced,
        rows_published=0,
        result_status=result_status,
        published_at=published_at,
        error_message=error_message,
    )


class _ProgressMessages:
    def __init__(self) -> None:
        self._messages: list[str] = []
        self._placeholder = st.empty()

    def add(self, message: str) -> None:
        self._messages.append(message)
        self._placeholder.markdown(
            "\n".join(f"- {item}" for item in self._messages)
        )


def _artifact_label(key: str) -> str:
    labels = {
        "consolidated_excel": "Consolidado Excel",
        "horas_pdf_csv": "Horas extraidas PDF",
        "matching_matriz_pdf_csv": "Diagnostico matriz/PDF",
        "matching_codigos_csv": "Diagnostico codigos",
        "validation_summary": "Resumen de validacion",
    }
    return labels.get(key, key)


def _mime_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if suffix == ".csv":
        return "text/csv"
    if suffix == ".md":
        return "text/markdown"
    return "application/octet-stream"
