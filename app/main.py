from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.validation_summary import expected_excel_fields
from app.ui.upload_panel import render_upload_panel


st.set_page_config(
    page_title="MIDE Consolidador",
    page_icon="MIDE",
    layout="wide",
)


def render_manual() -> None:
    fields = expected_excel_fields()

    with st.expander("Manual rapido y campos esperados", expanded=False):
        st.markdown(
            """
            Esta app procesa una carrera por vez. Necesita el PDF de plan de
            estudio y la matriz Excel de tributacion curricular.

            La hoja esperada de la matriz es `Asignaturas - RA`. Desde esa hoja
            se leen campos curriculares y de tributacion que luego se cruzan con
            la informacion extraida del PDF.
            """
        )
        st.dataframe(fields, hide_index=True, use_container_width=True)


def main() -> None:
    st.title("MIDE Consolidador Curricular")
    st.caption(
        "Ejecuta el ETL MIDE con el PDF del plan de estudio y la matriz Excel "
        "de tributacion. Al final recibiras el consolidado, diagnosticos y "
        "resumen de validacion."
    )

    render_manual()
    render_upload_panel()


if __name__ == "__main__":
    main()
