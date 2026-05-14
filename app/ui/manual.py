from __future__ import annotations

import streamlit as st

from app.services.manual import (
    diagnostic_outputs,
    expected_excel_fields,
    file_policy_notes,
    input_requirements,
    warning_guide,
)


def render_manual_content() -> None:
    st.markdown(
        """
        Usa esta app para procesar una carrera por vez. Carga el PDF del plan de
        estudio, la matriz Excel de tributacion y completa los metadatos minimos
        antes de ejecutar el ETL.
        """
    )

    st.markdown("**Insumos esperados**")
    st.dataframe(input_requirements(), hide_index=True, use_container_width=True)

    st.markdown("**Campos del consolidado**")
    st.dataframe(expected_excel_fields(), hide_index=True, use_container_width=True)

    st.markdown("**Archivos de salida y diagnostico**")
    st.dataframe(diagnostic_outputs(), hide_index=True, use_container_width=True)

    st.markdown("**Advertencias comunes**")
    st.dataframe(warning_guide(), hide_index=True, use_container_width=True)

    st.markdown("**Politica de archivos cargados**")
    for note in file_policy_notes():
        st.write(f"- {note}")
