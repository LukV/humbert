"""The runtime served by ``humbert start``.

A small FastAPI app: the notebook read/ask/delete API the SPA drives, a
`GET /api/bootstrap` for skin / locale / app name, and the built SPA served from
``apps/web/dist`` with ``data-skin`` and ``lang`` injected into the HTML shell
from config — so the right skin and language are present on first paint, no flash.

The ask route runs the same loop as ``humbert ask`` (discover the vocabulary →
plan/run/narrate → persist a cell), but streams it as Server-Sent Events: a
``stage`` event per phase so the UI can show progress over the slow model calls,
then a final ``cell`` event (or a quiet ``error``). It needs the same runtime the
CLI does: the API key in the server's env and the ``dbt`` extra installed. A
no-Tier-1 result is a calm refused cell, not an error; only a missing key or an
engine failure comes back as a quiet error the UI can show.

The cells handed to the SPA are reshaped by :mod:`humbert.webapi` into the nested
form the frontend renders; the persistence model stays Humbert's own.
"""

from __future__ import annotations

import json
import os
import queue
import re
import threading
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from humbert import engine, notebook, orchestrator, semantic, webapi
from humbert.config import Config

# Orchestrator stage keys → the frontend's stage vocabulary (see locales).
_STAGE_MAP = {
    "planning": "thinking",
    "replanning": "correcting",
    "running": "executing",
    "narrating": "narrating",
}


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


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class AskRequest(BaseModel):
    question: str
    parent_cell_id: str | None = None


class CellPatch(BaseModel):
    title: str


class Feedback(BaseModel):
    cell_id: str
    rating: str


def create_app(config: Config, dist: Path | None = None) -> FastAPI:
    dist = dist or web_dist()
    settings = config.settings
    app = FastAPI(title="Humbert", docs_url=None, redoc_url=None)

    # Discovering the vocabulary shells out to dbt/mf, so memoise it per project
    # for the life of the server — it doesn't change while the process runs.
    vocab_cache: dict[str, semantic.Vocabulary] = {}

    def active_project() -> tuple[str, Path] | None:
        """The active connection's (name, dbt project dir), or None if unset."""
        connection = config.active
        if connection is None or config.active_connection is None:
            return None
        return config.active_connection, Path(connection.project_dir)

    def vocabulary_for(project: Path) -> semantic.Vocabulary:
        key = str(project)
        if key not in vocab_cache:
            vocab_cache[key] = semantic.discover_vocabulary(project)
        return vocab_cache[key]

    @app.get("/api/bootstrap")
    def bootstrap() -> JSONResponse:
        return JSONResponse(
            {
                "skin": settings.theme,
                "locale": settings.locale,
                "app_name": settings.app_name,
            }
        )

    @app.get("/api/theme")
    def theme() -> JSONResponse:
        """App name, locale, and any theme overrides the SPA applies on load."""
        return JSONResponse(
            {
                "app_name": settings.app_name,
                "locale": settings.locale,
                "logo_path": None,
                "custom_css": None,
                "css_vars": {},
            }
        )

    @app.get("/api/notebook")
    def get_notebook() -> Response:
        active = active_project()
        if active is None:
            return _no_connection()
        name, _project = active
        book = notebook.load_notebook(name)
        return JSONResponse([webapi.wire_cell(c) for c in book.cells])

    @app.get("/api/suggestions")
    def suggestions() -> JSONResponse:
        """The empty-state chips — one per chart shape, from config (static for v0)."""
        return JSONResponse({"suggestions": settings.suggestions, "generating": False})

    @app.get("/api/schema")
    def schema() -> JSONResponse:
        """A stub so the SPA's schema probe resolves cleanly; gates the (unbuilt)
        pack browser, which is off in this build."""
        return JSONResponse({"schema": {"tables": []}})

    @app.post("/api/ask")
    def ask(request: AskRequest) -> Response:
        active = active_project()
        if active is None:
            return _no_connection()
        name, project = active

        question = request.question.strip()
        if not question:
            return JSONResponse({"error": "Ask a question first."}, status_code=400)

        try:
            vocabulary = vocabulary_for(project)
            model = orchestrator.build_model(config.llm)
        except orchestrator.OrchestratorError as err:
            # No API key, or an unsupported provider — a setup problem, not a bad answer.
            return JSONResponse({"error": str(err)}, status_code=400)
        except engine.EngineError as err:
            return JSONResponse({"error": str(err)}, status_code=502)

        # A follow-up carries the parent cell's structured query so the planner can
        # refine it ("add Italy") rather than re-planning blind. Only a cell with a
        # resolved selection is usable context; anything else is a fresh question.
        parent_id, prior_question, prior_selection = _prior_cell(name, request.parent_cell_id)

        def event_stream() -> Iterator[str]:
            # The orchestrator is synchronous and blocking, so run it on a worker
            # thread and let its on_stage callback push frames onto a queue this
            # generator drains — stages stream as they happen, not all at the end.
            events: queue.Queue[tuple[str, dict[str, Any]] | None] = queue.Queue()

            def run() -> None:
                try:
                    answer = orchestrator.ask(
                        question,
                        project_dir=project,
                        vocabulary=vocabulary,
                        model=model,
                        on_stage=lambda s: events.put(("stage", {"stage": _STAGE_MAP.get(s, s)})),
                        prior_question=prior_question,
                        prior_selection=prior_selection,
                    )
                    cell = notebook.record(
                        name,
                        answer,
                        vocabulary=vocabulary,
                        model=config.llm.model,
                        created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
                        parent_id=parent_id,
                    )
                    events.put(("cell", webapi.wire_cell(cell)))
                except engine.EngineError as err:
                    events.put(("error", {"message": str(err)}))
                except Exception as err:  # noqa: BLE001 - any failure becomes a quiet UI error
                    events.put(("error", {"message": str(err)}))
                finally:
                    events.put(None)

            threading.Thread(target=run, daemon=True).start()
            while True:
                item = events.get()
                if item is None:
                    break
                event, data = item
                yield _sse(event, data)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.patch("/api/cells/{cell_id}")
    def patch_cell(cell_id: int, patch: CellPatch) -> Response:
        active = active_project()
        if active is None:
            return _no_connection()
        name, _project = active
        cell = notebook.set_title(name, cell_id, patch.title)
        if cell is None:
            raise HTTPException(status_code=404, detail="No such cell")
        return JSONResponse(webapi.wire_cell(cell))

    @app.delete("/api/cells/{cell_id}")
    def delete_cell_alias(cell_id: int) -> Response:
        active = active_project()
        if active is None:
            return _no_connection()
        name, _project = active
        return JSONResponse({"deleted": notebook.delete(name, cell_id)})

    @app.post("/api/feedback")
    def feedback(body: Feedback) -> Response:
        """Append a thumbs up/down to a per-connection JSONL. The file is the
        truth; the UI fires and forgets."""
        active = active_project()
        if active is None:
            return _no_connection()
        name, _project = active
        path = notebook.notebook_path(name).with_name("feedback.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "cell_id": body.cell_id,
            "rating": body.rating,
            "at": datetime.now().isoformat(timespec="seconds"),
        }
        with path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
        return JSONResponse({"ok": True})

    @app.get("/api/health")
    def health() -> JSONResponse:
        """A compact, pollable signal the SPA topbar reads: is the stack up?"""
        active = active_project()
        if active is None:
            return JSONResponse({"ok": False})
        name, project = active
        warehouse_ok = engine.warehouse_path(project).exists()
        try:
            metrics_ok = len(engine.metric_names(project)) > 0
        except engine.EngineError:
            metrics_ok = False
        return JSONResponse(
            {"ok": warehouse_ok and metrics_ok, "connection_name": name, "database": name}
        )

    @app.get("/api/healthz")
    def healthz() -> JSONResponse:
        """The detailed health view (named checks), kept for the CLI/diagnostics.

        Lightweight by design (fast file reads, no dbt subprocess): the active
        connection is configured, the warehouse file is present, and the semantic
        layer parses with metrics. ``down`` means nothing can be asked; ``degraded``
        means the warehouse is there but the metrics aren't readable.
        """
        active = active_project()
        if active is None:
            return JSONResponse(
                {
                    "status": "down",
                    "project": None,
                    "checks": [
                        {"name": "connection", "ok": False, "detail": "No active connection"}
                    ],
                }
            )
        name, project = active
        checks: list[dict[str, object]] = [{"name": "connection", "ok": True, "detail": name}]

        warehouse_ok = engine.warehouse_path(project).exists()
        checks.append(
            {
                "name": "warehouse",
                "ok": warehouse_ok,
                "detail": "ready" if warehouse_ok else "not built — run `humbert connect --build`",
            }
        )

        try:
            metrics = engine.metric_names(project)
            metrics_ok = len(metrics) > 0
            detail = f"{len(metrics)} metric{'' if len(metrics) == 1 else 's'}"
        except engine.EngineError:
            metrics_ok = False
            detail = "semantic layer unreadable"
        checks.append({"name": "metrics", "ok": metrics_ok, "detail": detail})

        status = "down" if not warehouse_ok else "ok" if metrics_ok else "degraded"
        return JSONResponse({"status": status, "project": name, "checks": checks})

    @app.delete("/api/notebook/cells/{cell_id}")
    def delete_cell(cell_id: int) -> Response:
        active = active_project()
        if active is None:
            return _no_connection()
        name, _project = active
        deleted = notebook.delete(name, cell_id)
        return JSONResponse({"deleted": deleted})

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", response_class=HTMLResponse)
    @app.get("/{_path:path}", response_class=HTMLResponse)
    def spa(_path: str = "") -> HTMLResponse:
        # An unknown /api/* path is a real 404 — never serve it the SPA shell, or
        # an external poller (or a typo'd endpoint) reads a 200 and thinks it's up.
        if _path == "api" or _path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
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


def _prior_cell(
    name: str, parent_cell_id: str | None
) -> tuple[int | None, str | None, semantic.Selection | None]:
    """Resolve a follow-up's parent into (id, question, selection) for the planner.

    Returns all-None when there's no parent, the id doesn't parse or exist, or the
    parent has no resolved selection (a refused cell can't be refined).
    """
    if not parent_cell_id:
        return None, None, None
    try:
        cell_id = int(parent_cell_id)
    except ValueError:
        return None, None, None
    parent = notebook.load_notebook(name).cell(cell_id)
    if parent is None or parent.selection is None:
        return None, None, None
    return cell_id, parent.question, parent.selection


def _no_connection() -> JSONResponse:
    return JSONResponse(
        {"error": "No active connection. Run `humbert connect <dbt-project>` first."},
        status_code=400,
    )
