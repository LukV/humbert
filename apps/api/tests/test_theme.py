"""Theme loading and the CSS-var mapping the SPA consumes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from humbert import theme
from humbert.theme import ThemeConfig, load_theme, theme_to_css_vars


def test_defaults_match_the_built_in_skin() -> None:
    vars_ = theme_to_css_vars(ThemeConfig())
    assert vars_["--accent"] == "#4A2D4F"
    assert vars_["--font-body"].startswith('"DM Sans"')


def test_palette_falls_back_to_six_colours_when_unset() -> None:
    assert len(ThemeConfig().colors.resolved_palette()) == 6


def test_load_theme_prefers_the_project_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HUMBERT_HOME", str(tmp_path))
    proj = tmp_path / "projects" / "cheese"
    proj.mkdir(parents=True)
    (proj / "theme.json").write_text(
        json.dumps({"app_name": "proef", "colors": {"primary": "#2B979D"}})
    )
    loaded = load_theme("cheese")
    assert loaded.app_name == "proef"
    assert theme_to_css_vars(loaded)["--accent"] == "#2B979D"


def test_load_theme_uses_the_fallback_when_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HUMBERT_HOME", str(tmp_path))
    loaded = load_theme("cheese", fallback=ThemeConfig(app_name="Custom", locale="nl"))
    assert loaded.app_name == "Custom"
    assert loaded.locale == "nl"
    assert theme_to_css_vars(loaded)["--accent"] == "#4A2D4F"  # default colours


def test_lighten_hex_moves_toward_white_and_passes_malformed_through() -> None:
    assert theme._lighten_hex("#000000", 0.5) == "#7f7f7f"
    assert theme._lighten_hex("#fff", 0.5) == "#fff"
