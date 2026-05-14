from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ui.branding import apply_branding, render_color_band, render_header
from app.ui.manual import render_manual_content
from app.ui.upload_panel import render_upload_panel


st.set_page_config(
    page_title="MIDE Consolidador",
    page_icon="MIDE",
    layout="wide",
)


def main() -> None:
    apply_branding()
    render_header()
    process_tab, manual_tab = st.tabs(["Procesar carrera", "Manual"])
    with process_tab:
        st.caption(
            "Ejecuta el ETL MIDE con el PDF del plan de estudio y la matriz Excel "
            "de tributacion. Al final podras revisar una previsualizacion y "
            "descargar el consolidado."
        )
        render_upload_panel()
    with manual_tab:
        st.subheader("Manual de uso")
        render_manual_content()

    render_color_band()


if __name__ == "__main__":
    main()
