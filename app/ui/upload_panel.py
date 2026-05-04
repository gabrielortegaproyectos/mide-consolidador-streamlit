from __future__ import annotations

import streamlit as st


def render_upload_panel() -> None:
    st.subheader("Procesar carrera")

    left, right = st.columns(2)
    with left:
        st.file_uploader("PDF de plan de estudio", type=["pdf"])
    with right:
        st.file_uploader("Matriz Excel de tributacion", type=["xlsx"])

    st.text_input("Carrera")
    st.text_input("Facultad")
    st.text_input("Escuela")
    st.text_input("Grado")
    st.selectbox(
        "Tipo de ciclo",
        ["No especificado", "Semestral", "Anual", "Otro"],
    )

    st.button("Validar insumos", type="primary", disabled=True)

