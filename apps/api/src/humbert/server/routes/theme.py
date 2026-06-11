"""``GET /api/bootstrap`` and ``GET /api/theme`` — skin, locale, branding."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from humbert.server.deps import StateDep
from humbert.theme import ThemeConfig, load_theme, theme_to_css_vars

router = APIRouter()


@router.get("/bootstrap")
def bootstrap(state: StateDep) -> JSONResponse:
    settings = state.config.settings
    return JSONResponse(
        {
            "skin": settings.theme,
            "locale": settings.locale,
            "app_name": settings.app_name,
        }
    )


@router.get("/theme")
def theme(state: StateDep) -> JSONResponse:
    """App name, locale, and the skin overrides the SPA applies on load.

    Branding comes from an optional ``theme.json`` beside the active
    connection (see :mod:`humbert.theme`); absent one, it falls back to the
    ``config.json`` settings, so the default skin is unchanged.
    """
    settings = state.config.settings
    base = ThemeConfig(app_name=settings.app_name, locale=settings.locale)
    loaded = load_theme(state.config.active_connection, fallback=base)
    return JSONResponse(
        {
            "app_name": loaded.app_name,
            "locale": loaded.locale,
            "logo_path": loaded.logo_path,
            "custom_css": loaded.fonts.custom_css,
            "css_vars": theme_to_css_vars(loaded),
        }
    )
