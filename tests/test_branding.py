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
