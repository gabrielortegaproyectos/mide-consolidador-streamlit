from __future__ import annotations

import tempfile
from pathlib import Path

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

    meta_left, meta_right = st.columns(2)
    with meta_left:
        career = st.text_input("Carrera")
        faculty = st.text_input("Facultad")
        school = st.text_input("Escuela")
    with meta_right:
        degree = st.text_input("Grado")
        cycle_type = st.selectbox(
            "Tipo de ciclo",
            ["No especificado", "Semestral", "Anual", "Otro"],
        )

    files_ready = pdf_file is not None and matrix_file is not None
    metadata_ready = bool(career.strip())

    validate_col, run_col = st.columns([1, 1])
    with validate_col:
        validate_clicked = st.button(
            "Validar insumos",
            disabled=matrix_file is None,
            use_container_width=True,
        )
    with run_col:
        run_clicked = st.button(
            "Procesar carrera",
            type="primary",
            disabled=not files_ready or not metadata_ready,
            use_container_width=True,
        )

    if not validate_clicked and not run_clicked:
        current_state = "listo" if RUN_RESULT_STATE_KEY in st.session_state else "pendiente"
        _render_flow_status(current_state)

    if validate_clicked and matrix_file is not None:
        with tempfile.TemporaryDirectory(prefix="mide-validate-") as tmp_dir:
            matrix_path = _write_uploaded_matrix(matrix_file, Path(tmp_dir))
            _render_flow_status("validando")
            validation = validate_excel_input(matrix_path)
            _render_validation_result(validation)

    if run_clicked and files_ready:
        _run_pipeline_from_uploads(
            pdf_file=pdf_file,
            matrix_file=matrix_file,
            career=career,
            faculty=faculty,
            school=school,
            degree=degree,
            cycle_type=cycle_type,
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
    career: str,
    faculty: str,
    school: str,
    degree: str,
    cycle_type: str,
) -> None:
    with st.spinner("Procesando ETL..."):
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

            try:
                result = run_uploaded_pipeline(
                    PipelineInputs(
                        pdf_path=pdf_path,
                        matrix_path=matrix_path,
                        career=career,
                        faculty=faculty,
                        school=school,
                        degree=degree,
                        cycle_type=cycle_type,
                    )
                )
            except UploadedPipelineError as exc:
                _render_flow_status("requiere_correccion")
                st.error("No fue posible procesar los insumos.")
                st.info(str(exc))
                return

            st.session_state[RUN_RESULT_STATE_KEY] = _snapshot_pipeline_result(
                result=result,
                uploaded_files=uploaded_files,
                metadata={
                    "Carrera": career,
                    "Facultad": faculty,
                    "Escuela": school,
                    "Grado": degree,
                    "Tipo de ciclo": cycle_type,
                },
            )
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
        "zip_bytes": package.zip_bytes,
        "validation_summary_md": package.validation_summary_md,
    }


def _render_run_result(result: dict[str, object]) -> None:
    st.divider()
    render_validation_summary(result["summary"])

    warnings = result.get("warnings", [])
    if warnings:
        with st.expander("Advertencias del pipeline"):
            for warning in warnings:
                st.warning(str(warning))

    st.markdown("**Descargas**")
    st.download_button(
        "Descargar paquete final",
        data=result["zip_bytes"],
        file_name="mide_resultados.zip",
        mime="application/zip",
        use_container_width=True,
    )

    artifacts = result.get("artifacts", {})
    if artifacts:
        with st.expander("Archivos individuales"):
            st.download_button(
                "Resumen de validacion",
                data=result["validation_summary_md"],
                file_name="resumen_validacion.md",
                mime="text/markdown",
                use_container_width=True,
                key="download-validation-summary",
            )
            for key, artifact in artifacts.items():
                st.download_button(
                    _artifact_label(str(key)),
                    data=artifact["bytes"],
                    file_name=artifact["name"],
                    mime=_mime_type(str(artifact["name"])),
                    use_container_width=True,
                    key=f"download-{key}",
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

