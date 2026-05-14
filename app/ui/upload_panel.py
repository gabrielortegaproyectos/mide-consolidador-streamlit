from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from app.services.delivery_package import build_delivery_package, trace_file
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
from app.services.validation_summary import build_validation_summary
from app.ui.validation_panel import render_validation_summary


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

    if not run_clicked:
        current_state = "listo" if RUN_RESULT_STATE_KEY in st.session_state else "pendiente"
        _render_flow_status(current_state)

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
        _render_flow_status("procesando")
        with tempfile.TemporaryDirectory(prefix="mide-upload-") as upload_dir:
            upload_root = Path(upload_dir)
            pdf_path = _write_uploaded_file(pdf_file, upload_root, "plan.pdf")
            matrix_path = _write_uploaded_file(matrix_file, upload_root, "matriz.xlsx")
            uploaded_files = {
                "PDF plan de estudio": trace_file(pdf_path),
                "Matriz Excel tributacion": trace_file(matrix_path),
            }
            validation = validate_excel_input(matrix_path)
            if not validation.is_valid:
                _render_flow_status("requiere_correccion")
                _render_validation_result(validation)
                return
            st.success("Insumos validados. La estructura base de la matriz es compatible.")

            result: PipelineResult | None = None
            try:
                result = run_uploaded_pipeline(
                    PipelineInputs(
                        pdf_path=pdf_path,
                        matrix_path=matrix_path,
                    )
                )
            except UploadedPipelineError as exc:
                _render_flow_status("requiere_correccion")
                st.error("No fue posible procesar los insumos.")
                st.info(public_error_message(str(exc)))
                return
            except Exception:
                _render_flow_status("requiere_correccion")
                st.error("No fue posible procesar los insumos.")
                st.info(generic_processing_error())
                return

            try:
                st.session_state[RUN_RESULT_STATE_KEY] = _snapshot_pipeline_result(
                    result=result,
                    uploaded_files=uploaded_files,
                    metadata={
                        "Fuente de metadatos": "PDF, matriz y catalogos JSON",
                    },
                )
            except Exception:
                _render_flow_status("requiere_correccion")
                st.error("No fue posible preparar la descarga.")
                st.info(generic_processing_error())
                return
            finally:
                cleanup_pipeline_result(result)
            _render_flow_status("listo")


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
    render_validation_summary(result["summary"])

    warnings = result.get("warnings", [])
    if warnings:
        with st.expander("Advertencias del pipeline"):
            for warning in warnings:
                st.warning(str(warning))

    artifacts = result.get("artifacts", {})
    preview = result.get("consolidated_preview")
    if isinstance(preview, pd.DataFrame) and not preview.empty:
        st.markdown("**Previsualizacion del consolidado**")
        st.dataframe(preview, hide_index=True, use_container_width=True)

    consolidated = artifacts.get("consolidated_excel") if isinstance(artifacts, dict) else None
    if consolidated:
        st.markdown("**Descarga**")
        st.download_button(
            "Descargar consolidado Excel",
            data=consolidated["bytes"],
            file_name=consolidated["name"],
            mime=_mime_type(str(consolidated["name"])),
            use_container_width=True,
            key="download-consolidated-excel",
        )

    st.caption(f"Version ETL: {result.get('pipeline_version', 'unknown')}")


def _render_flow_status(active_state: str) -> None:
    states = [
        ("pendiente", "Pendiente"),
        ("validando", "Validando"),
        ("procesando", "Procesando"),
        ("listo", "Listo"),
        ("requiere_correccion", "Requiere correccion"),
    ]
    cols = st.columns(len(states))
    for col, (state, label) in zip(cols, states, strict=True):
        if state == active_state:
            col.success(label)
        else:
            col.info(label)


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

