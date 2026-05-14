from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.manual import (
    diagnostic_outputs,
    expected_excel_fields,
    file_policy_notes,
    input_requirements,
    warning_guide,
)
from app.ui.branding import apply_branding, render_color_band, render_header
from app.ui.upload_panel import render_upload_panel


st.set_page_config(
    page_title="MIDE Consolidador",
    page_icon="MIDE",
    layout="wide",
)


def render_manual() -> None:
    fields = expected_excel_fields()

    with st.expander("Manual rapido", expanded=False):
        st.markdown(
            """
            Usa esta app para procesar una carrera por vez. Carga el PDF del
            plan de estudio, la matriz Excel de tributacion y completa los
            metadatos minimos antes de ejecutar el ETL.
            """
        )

        st.markdown("**Insumos esperados**")
        st.dataframe(input_requirements(), hide_index=True, use_container_width=True)

        st.markdown("**Campos del consolidado**")
        st.dataframe(fields, hide_index=True, use_container_width=True)

        st.markdown("**Archivos de salida y diagnostico**")
        st.dataframe(diagnostic_outputs(), hide_index=True, use_container_width=True)

        st.markdown("**Advertencias comunes**")
        st.dataframe(warning_guide(), hide_index=True, use_container_width=True)

        st.markdown("**Politica de archivos cargados**")
        for note in file_policy_notes():
            st.write(f"- {note}")


def main() -> None:
    apply_branding()
    render_header()
    st.caption(
        "Ejecuta el ETL MIDE con el PDF del plan de estudio y la matriz Excel "
        "de tributacion. Al final recibiras el consolidado, diagnosticos y "
        "resumen de validacion."
    )

    render_manual()
    render_upload_panel()
    render_color_band()


if __name__ == "__main__":
    main()
