from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.google_sheets_config import get_google_sheets_config_status
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
    google_sheets_status = get_google_sheets_config_status()
    process_tab, manual_tab = st.tabs(["Procesar carrera", "Manual"])
    with process_tab:
        _render_google_sheets_status(google_sheets_status)
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


def _render_google_sheets_status(status) -> None:
    if status.enabled:
        st.success(
            "Integracion Google Sheets configurada. La descarga local sigue "
            "activa y la publicacion online se implementara en pasos posteriores."
        )
        if status.service_account_email:
            st.caption(
                f"Service account configurada: {status.service_account_email}"
            )
        return
    st.info(
        "Integracion Google Sheets desactivada. Si faltan secrets, la app "
        "mantiene el flujo local de procesamiento y descarga."
    )


if __name__ == "__main__":
    main()
