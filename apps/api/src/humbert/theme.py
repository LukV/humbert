"""Theme (skin) configuration for branded Humbert deployments.

A skin is colours + fonts + a name, supplied by an optional ``theme.json`` that
sits with the connection it brands. The resolution chain is project-specific
first, then a global file, then defaults — so a deployment can theme one source
or all of them. The defaults match Humbert's built-in look, so a pack with no
``theme.json`` renders exactly as before.

``theme_to_css_vars`` turns a theme into the CSS custom properties the SPA already
consumes (``apps/web/src/App.tsx`` applies them over the light/dark tokens), and
the server hands the whole thing to the frontend via ``GET /api/theme``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from humbert.config import Locale, humbert_home, project_dir

logger = logging.getLogger("humbert.theme")


class ThemeColors(BaseModel):
    """Brand colours. Defaults are Humbert's built-in palette."""

    primary: str = "#4A2D4F"
    secondary: str = "#C2876E"
    accent: str = "#6B8F8A"
    palette: list[str] | None = None

    def resolved_palette(self) -> list[str]:
        """The chart palette, falling back to one derived from the brand colours."""
        if self.palette and len(self.palette) >= 3:
            return self.palette[:6]
        return [self.primary, self.secondary, self.accent, "#B8A44C", "#8C7B6B", "#A3667E"]


class ThemeFonts(BaseModel):
    """Typography. ``custom_css`` is a URL the SPA loads (e.g. ``@font-face`` rules)."""

    body: str = "DM Sans"
    editorial: str = "Source Serif 4"
    mono: str = "JetBrains Mono"
    custom_css: str | None = None


class ThemeConfig(BaseModel):
    """A deployment's visual identity. Loaded from ``theme.json`` or defaults."""

    app_name: str = "Humbert"
    logo_path: str | None = None
    locale: Locale = "en"
    colors: ThemeColors = Field(default_factory=ThemeColors)
    fonts: ThemeFonts = Field(default_factory=ThemeFonts)

    @field_validator("locale", mode="before")
    @classmethod
    def _known_locale(cls, value: object) -> object:
        # One unknown locale must not unbrand a deployment — keep the rest of
        # the theme and fall back to English.
        return value if value in ("en", "nl") else "en"


def load_theme(
    connection_name: str | None = None, *, fallback: ThemeConfig | None = None
) -> ThemeConfig:
    """Load a theme with a fallback chain.

    1. ``~/.humbert/projects/<connection>/theme.json`` (project-specific)
    2. ``~/.humbert/theme.json`` (global)
    3. ``fallback`` if given, else built-in defaults
    """
    if connection_name:
        theme = _load_from(project_dir(connection_name) / "theme.json")
        if theme is not None:
            return theme

    theme = _load_from(humbert_home() / "theme.json")
    if theme is not None:
        return theme

    return fallback or ThemeConfig()


def _load_from(path: Path) -> ThemeConfig | None:
    """Load a ``ThemeConfig`` from JSON, or ``None`` if missing or malformed."""
    if not path.is_file():
        return None
    try:
        return ThemeConfig.model_validate_json(path.read_text())
    except Exception as err:  # noqa: BLE001 - a bad theme must not take the app down
        logger.warning("Failed to load theme from %s: %s", path, err)
        return None


def theme_to_css_vars(theme: ThemeConfig) -> dict[str, str]:
    """The CSS custom properties the SPA sets on :root from a theme."""
    return {
        "--accent": theme.colors.primary,
        "--accent-light": _lighten_hex(theme.colors.primary, 0.15),
        "--font-body": f'"{theme.fonts.body}", system-ui, sans-serif',
        "--font-editorial": f'"{theme.fonts.editorial}", Georgia, serif',
        "--font-mono": f'"{theme.fonts.mono}", monospace',
        "--logo-fill": theme.colors.primary,
        "--chart-palette": ",".join(theme.colors.resolved_palette()),
    }


def _lighten_hex(hex_color: str, factor: float) -> str:
    """Lighten a ``#rrggbb`` colour toward white by ``factor`` (0–1)."""
    raw = hex_color.lstrip("#")
    if len(raw) != 6:
        return hex_color
    channels = (int(raw[i : i + 2], 16) for i in (0, 2, 4))
    lightened = (min(255, int(c + (255 - c) * factor)) for c in channels)
    return "#" + "".join(f"{c:02x}" for c in lightened)
