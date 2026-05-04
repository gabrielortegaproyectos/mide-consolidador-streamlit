from __future__ import annotations

import streamlit as st

from services.validation_summary import expected_excel_fields
from ui.upload_panel import render_upload_panel


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
        "Carga asistida para ejecutar el ETL MIDE y obtener consolidados, "
        "diagnosticos y resumen de validacion."
    )

    render_manual()
    render_upload_panel()

    st.info(
        "Bootstrap inicial: la integracion con el pipeline ETL se implementara "
        "cuando quede estable el contrato publico de `mide-tributacion-curricular`."
    )


if __name__ == "__main__":
    main()
