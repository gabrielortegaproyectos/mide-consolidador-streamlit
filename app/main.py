from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ui.branding import apply_branding, render_color_band, render_header
from app.ui.upload_panel import render_upload_panel


st.set_page_config(
    page_title="MIDE Consolidador",
    page_icon="MIDE",
    layout="wide",
)


def main() -> None:
    apply_branding()
    render_header()
    st.caption(
        "Ejecuta el ETL MIDE con el PDF del plan de estudio y la matriz Excel "
        "de tributacion. Al final recibiras el consolidado, diagnosticos y "
        "resumen de validacion."
    )
    st.info(
        "El Manual esta disponible como pagina independiente en la navegacion "
        "lateral de Streamlit."
    )

    render_upload_panel()
    render_color_band()


if __name__ == "__main__":
    main()
