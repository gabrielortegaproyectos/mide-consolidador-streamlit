from __future__ import annotations

from pathlib import Path

import streamlit as st


LOGO_PATH = Path(__file__).resolve().parents[1] / "static" / "logo_ubo.webp"

UBO_BLUE = "#16446b"
MIDE_BLUE = "#4a5a86"
PANEL_BLUE = "#2f5a78"
MIDE_TEAL = "#3f9f91"
ACCENT_GREEN = "#00b050"
ACCENT_ORANGE = "#f26b21"
ACCENT_RED = "#ef2b16"
ACCENT_PURPLE = "#6f2da8"


def apply_branding() -> None:
    st.markdown(
        f"""
        <style>
            :root {{
                --ubo-blue: {UBO_BLUE};
                --mide-blue: {MIDE_BLUE};
                --panel-blue: {PANEL_BLUE};
                --mide-teal: {MIDE_TEAL};
                --accent-green: {ACCENT_GREEN};
                --accent-orange: {ACCENT_ORANGE};
                --accent-red: {ACCENT_RED};
                --accent-purple: {ACCENT_PURPLE};
            }}

            .stApp {{
                background: #ffffff;
                color: #1e293b;
            }}

            .block-container {{
                padding-top: 1.35rem;
                padding-bottom: 2.5rem;
                max-width: 1180px;
            }}

            h1, h2, h3 {{
                color: var(--mide-blue);
                letter-spacing: 0;
            }}

            [data-testid="stCaptionContainer"] {{
                color: #475569;
            }}

            .ubo-header {{
                display: flex;
                align-items: center;
                gap: 2rem;
                padding: 0.25rem 0 1.25rem;
                border-bottom: 1px solid #e5e7eb;
                margin-bottom: 1.2rem;
            }}

            .ubo-header img {{
                width: min(178px, 36vw);
                height: auto;
                object-fit: contain;
            }}

            .ubo-header__title {{
                color: var(--mide-blue);
                font-size: 1.65rem;
                font-weight: 700;
                line-height: 1.2;
                margin: 0;
            }}

            .ubo-header__subtitle {{
                color: #475569;
                font-size: 0.95rem;
                margin-top: 0.35rem;
            }}

            div[data-testid="stButton"] > button[kind="primary"] {{
                background-color: var(--mide-teal);
                border-color: var(--mide-teal);
                color: #ffffff;
                font-weight: 700;
            }}

            div[data-testid="stButton"] > button:not([kind="primary"]) {{
                border-color: var(--panel-blue);
                color: var(--panel-blue);
            }}

            div[data-testid="stDownloadButton"] > button {{
                background-color: var(--mide-teal);
                border-color: var(--mide-teal);
                color: #ffffff;
                font-weight: 700;
            }}

            div[data-testid="stMetric"] {{
                border-left: 4px solid var(--panel-blue);
                padding-left: 0.75rem;
            }}

            div[data-testid="stExpander"] summary {{
                color: var(--panel-blue);
                font-weight: 700;
            }}

            .ubo-color-band {{
                display: grid;
                grid-template-columns: 1fr 1fr 1fr 1fr 1fr;
                width: 100%;
                height: 10px;
                margin-top: 2rem;
            }}

            .ubo-color-band span:nth-child(1) {{ background: var(--accent-green); }}
            .ubo-color-band span:nth-child(2) {{ background: #1f57a6; }}
            .ubo-color-band span:nth-child(3) {{ background: var(--accent-orange); }}
            .ubo-color-band span:nth-child(4) {{ background: var(--accent-red); }}
            .ubo-color-band span:nth-child(5) {{ background: var(--accent-purple); }}

            @media (max-width: 720px) {{
                .ubo-header {{
                    align-items: flex-start;
                    gap: 1rem;
                    flex-direction: column;
                }}

                .ubo-header__title {{
                    font-size: 1.35rem;
                }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    left, right = st.columns([1, 4], vertical_alignment="center")
    with left:
        st.image(str(LOGO_PATH), width=178)
    with right:
        st.markdown(
            """
            <div class="ubo-header-copy">
                <h1 class="ubo-header__title">Mecanismo Integrado de Desarrollo Educativo (MIDE)</h1>
                <div class="ubo-header__subtitle">
                    Consolidador curricular para tributacion, diagnosticos y descarga auditable.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.divider()


def render_color_band() -> None:
    st.markdown(
        """
        <div class="ubo-color-band" aria-hidden="true">
            <span></span><span></span><span></span><span></span><span></span>
        </div>
        """,
        unsafe_allow_html=True,
    )
