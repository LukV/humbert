"""The runtime served by ``humbert start``.

A small FastAPI app, assembled here and nowhere else: the routes live one
concern per module under ``routes/`` (with their request models beside them),
the shared state in ``state.py`` (injected via ``deps.StateDep``), and the
Cell→JSON mapping the SPA reads in ``wire.py``. This module only registers the
pieces and serves the built SPA from ``apps/web/dist``, with ``data-skin`` and
``lang`` injected into the HTML shell from config — so the right skin and
language are present on first paint, no flash.

Every API failure serialises as ``{"error": message}`` (see ``errors.py``);
the exception handlers registered here keep that one shape, whether a route
raised ``APIError`` or the request didn't validate.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from humbert.config import Config
from humbert.server.errors import APIError
from humbert.server.routes.ask import router as ask_router
from humbert.server.routes.cells import router as cells_router
from humbert.server.routes.health import router as health_router
from humbert.server.routes.misc import router as misc_router
from humbert.server.routes.theme import router as theme_router
from humbert.server.state import AppState


def web_dist() -> Path:
    """Where the built frontend lives. Override with HUMBERT_WEB_DIST."""
    override = os.environ.get("HUMBERT_WEB_DIST")
    if override:
        return Path(override)
    # apps/api/src/humbert/server -> apps/web/dist
    return Path(__file__).resolve().parents[4] / "web" / "dist"


_HTML_TAG = re.compile(r"<html\b[^>]*>", re.IGNORECASE)


def inject_shell(html: str, *, skin: str, locale: str) -> str:
    """Set ``lang`` and ``data-skin`` on the opening <html> tag from config."""
    return _HTML_TAG.sub(f'<html lang="{locale}" data-skin="{skin}">', html, count=1)


def create_app(config: Config, dist: Path | None = None) -> FastAPI:
    dist = dist or web_dist()
    app = FastAPI(title="Humbert", docs_url="/docs", redoc_url=None)
    app.state.app_state = AppState(config=config, dist=dist)

    @app.exception_handler(APIError)
    async def _api_error(_request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse({"error": exc.message}, status_code=exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        return JSONResponse({"error": f"Invalid request — {detail}"}, status_code=422)

    for router in (ask_router, cells_router, health_router, misc_router, theme_router):
        app.include_router(router, prefix="/api")

    _mount_static(app, dist)
    _serve_spa(app, config, dist)
    return app


def _mount_static(app: FastAPI, dist: Path) -> None:
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    # Skins may ship fonts (e.g. a theme's `custom_css` at `/fonts/...`). The SPA
    # catch-all below would otherwise answer these with the HTML shell.
    fonts = dist / "fonts"
    if fonts.is_dir():
        app.mount("/fonts", StaticFiles(directory=fonts), name="fonts")


def _serve_spa(app: FastAPI, config: Config, dist: Path) -> None:
    """The catch-all that serves the SPA shell for every non-API route.

    The shell (index.html + injected skin/lang) is cached on the file's mtime,
    so a rebuilt frontend is picked up without restarting the server but the
    file isn't re-read and re-substituted on every navigation.
    """
    settings = config.settings
    index = dist / "index.html"
    cached: dict[float, str] = {}

    def shell() -> str | None:
        if not index.is_file():
            return None
        mtime = index.stat().st_mtime
        if mtime not in cached:
            cached.clear()
            cached[mtime] = inject_shell(
                index.read_text(), skin=settings.theme, locale=settings.locale
            )
        return cached[mtime]

    @app.get("/", response_class=HTMLResponse)
    @app.get("/{_path:path}", response_class=HTMLResponse)
    def spa(_path: str = "") -> HTMLResponse:
        # An unknown /api/* path is a real 404 — never serve it the SPA shell, or
        # an external poller (or a typo'd endpoint) reads a 200 and thinks it's up.
        if _path == "api" or _path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        html = shell()
        if html is None:
            return HTMLResponse(
                "<h1>Humbert</h1><p>Frontend not built. Run <code>npm run build</code> "
                "in <code>apps/web</code>.</p>",
                status_code=200,
            )
        # The shell must never outlive its hashed bundles in a browser cache;
        # the bundles themselves stay cacheable by their hashes.
        return HTMLResponse(html, headers={"Cache-Control": "no-cache, must-revalidate"})
