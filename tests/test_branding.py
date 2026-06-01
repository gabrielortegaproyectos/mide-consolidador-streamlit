from __future__ import annotations

from app.ui import branding


def test_logo_asset_is_versioned() -> None:
    assert branding.LOGO_PATH.exists()
    assert branding.LOGO_PATH.name == "logo_ubo.webp"


def test_branding_palette_uses_mide_reference_colors() -> None:
    assert branding.UBO_BLUE == "#16446b"
    assert branding.MIDE_BLUE == "#4a5a86"
    assert branding.PANEL_BLUE == "#2f5a78"
    assert branding.MIDE_TEAL == "#3f9f91"


def test_apply_branding_includes_contrast_styles_for_tabs_metrics_and_inputs(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_markdown(content: str, *, unsafe_allow_html: bool) -> None:
        captured["content"] = content
        captured["unsafe"] = unsafe_allow_html

    monkeypatch.setattr(branding.st, "markdown", fake_markdown)

    branding.apply_branding()

    css = str(captured["content"])
    assert captured["unsafe"] is True
    assert '[data-testid="stTabs"] button[aria-selected="true"]' in css
    assert 'div[data-testid="stMetricValue"]' in css
    assert '[data-testid="stWidgetLabel"] *' in css
    assert "#0f172a" in css
