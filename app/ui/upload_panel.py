from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from app.services.input_validation import InputValidationResult, validate_excel_input


def render_upload_panel() -> None:
    st.subheader("Procesar carrera")

    left, right = st.columns(2)
    with left:
        st.file_uploader("PDF de plan de estudio", type=["pdf"])
    with right:
        matrix_file = st.file_uploader("Matriz Excel de tributacion", type=["xlsx"])

    st.text_input("Carrera")
    st.text_input("Facultad")
    st.text_input("Escuela")
    st.text_input("Grado")
    st.selectbox(
        "Tipo de ciclo",
        ["No especificado", "Semestral", "Anual", "Otro"],
    )

    if st.button("Validar insumos", type="primary", disabled=matrix_file is None):
        with tempfile.TemporaryDirectory(prefix="mide-validate-") as tmp_dir:
            matrix_path = _write_uploaded_matrix(matrix_file, Path(tmp_dir))
            validation = validate_excel_input(matrix_path)
            _render_validation_result(validation)


def _write_uploaded_matrix(uploaded_file, output_dir: Path) -> Path:
    filename = Path(uploaded_file.name or "matriz.xlsx").name
    matrix_path = output_dir / filename
    matrix_path.write_bytes(uploaded_file.getbuffer())
    return matrix_path


def _render_validation_result(result: InputValidationResult) -> None:
    if result.is_valid:
        st.success("Matriz validada. La estructura base es compatible.")
        return

    for message in result.errors:
        st.error(message.title)
        st.write(message.detail)
        if message.recommendation:
            st.info(message.recommendation)

