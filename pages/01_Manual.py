from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ui.branding import apply_branding, render_color_band, render_header
from app.ui.manual import render_manual_content


st.set_page_config(
    page_title="Manual MIDE",
    page_icon="MIDE",
    layout="wide",
)


def main() -> None:
    apply_branding()
    render_header()
    st.subheader("Manual de uso")
    render_manual_content()
    render_color_band()


if __name__ == "__main__":
    main()
