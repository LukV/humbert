"""The runtime served by ``humbert start``.

A small FastAPI app: a `GET /api/bootstrap` the frontend reads for skin / locale
/ app name, and the built SPA served from ``apps/web/dist`` with ``data-skin``
and ``lang`` injected into the HTML shell from config — so the right skin and
language are present on first paint, no flash. No notebook UI yet (block 2).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from humbert.config import Config


def web_dist() -> Path:
    """Where the built frontend lives. Override with HUMBERT_WEB_DIST."""
    override = os.environ.get("HUMBERT_WEB_DIST")
    if override:
        return Path(override)
    # apps/api/src/humbert/server.py -> apps/web/dist
    return Path(__file__).resolve().parents[3] / "web" / "dist"


_HTML_TAG = re.compile(r"<html\b[^>]*>", re.IGNORECASE)


def inject_shell(html: str, *, skin: str, locale: str) -> str:
    """Set ``lang`` and ``data-skin`` on the opening <html> tag from config."""
    return _HTML_TAG.sub(f'<html lang="{locale}" data-skin="{skin}">', html, count=1)


def create_app(config: Config, dist: Path | None = None) -> FastAPI:
    dist = dist or web_dist()
    settings = config.settings
    app = FastAPI(title="Humbert", docs_url=None, redoc_url=None)

    @app.get("/api/bootstrap")
    def bootstrap() -> JSONResponse:
        return JSONResponse(
            {
                "skin": settings.theme,
                "locale": settings.locale,
                "app_name": settings.app_name,
            }
        )

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", response_class=HTMLResponse)
    @app.get("/{_path:path}", response_class=HTMLResponse)
    def spa(_path: str = "") -> HTMLResponse:
        index = dist / "index.html"
        if not index.is_file():
            return HTMLResponse(
                "<h1>Humbert</h1><p>Frontend not built. Run <code>npm run build</code> "
                "in <code>apps/web</code>.</p>",
                status_code=200,
            )
        shell = inject_shell(index.read_text(), skin=settings.theme, locale=settings.locale)
        return HTMLResponse(shell)

    return app
