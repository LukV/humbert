"""``POST /api/ask`` — the streaming plan → run → narrate route.

Runs the same loop as ``humbert ask`` (discover the vocabulary → plan/run/
narrate → persist a cell), but streams it as Server-Sent Events: a ``stage``
event per phase so the UI can show progress over the slow model calls, then a
final ``cell`` event (or a quiet ``error``). A no-Tier-1 result is a calm
refused cell, not an error.

Setup problems — no connection, no API key, an unreadable engine — fail
*before* the stream starts, as plain JSON errors: the SPA shows those in its
header banner, not inside a cell.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from humbert import engine, notebook, orchestrator, semantic
from humbert.server.deps import ConnectionDep, StateDep
from humbert.server.errors import APIError
from humbert.server.sse import sse
from humbert.server.wire import wire_cell

router = APIRouter()

# Orchestrator stage keys → the frontend's stage vocabulary (see locales).
_STAGE_MAP: dict[orchestrator.Stage, str] = {
    "planning": "thinking",
    "replanning": "correcting",
    "running": "executing",
    "narrating": "narrating",
}


class AskRequest(BaseModel):
    question: str
    parent_cell_id: int | None = None


@router.post("/ask")
def ask(request: AskRequest, active: ConnectionDep, state: StateDep) -> Response:
    name, project = active

    question = request.question.strip()
    if not question:
        raise APIError(400, "Ask a question first.")

    try:
        # Build the model first: it's a cheap env-var check, so a missing key
        # fails in milliseconds rather than after the (slow) vocabulary build.
        model = orchestrator.build_model(state.config.llm)
        vocabulary = semantic.discover_vocabulary(project)
    except orchestrator.OrchestratorError as err:
        # No API key, or an unsupported provider — a setup problem, not a bad answer.
        raise APIError(400, str(err)) from err
    except engine.EngineError as err:
        raise APIError(502, str(err)) from err

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
                    on_stage=lambda s: events.put(("stage", {"stage": _STAGE_MAP[s]})),
                    prior_question=prior_question,
                    prior_selection=prior_selection,
                )
                cell = notebook.record(
                    name,
                    answer,
                    vocabulary=vocabulary,
                    model=state.config.llm.model,
                    parent_id=parent_id,
                )
                events.put(("cell", wire_cell(cell)))
            except Exception as err:  # noqa: BLE001 - any failure becomes a quiet UI error
                events.put(("error", {"message": str(err)}))
            finally:
                events.put(None)

        # Deliberately not cancelled if the client disconnects: the (paid)
        # answer still completes and persists; the notebook shows it on reload.
        threading.Thread(target=run, daemon=True).start()
        while True:
            item = events.get()
            if item is None:
                break
            event, data = item
            yield sse(event, data)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _prior_cell(
    name: str, parent_cell_id: int | None
) -> tuple[int | None, str | None, semantic.Selection | None]:
    """Resolve a follow-up's parent into (id, question, selection) for the planner.

    Returns all-None when there's no parent, the id doesn't exist, or the parent
    has no resolved selection (a refused cell can't be refined).
    """
    if parent_cell_id is None:
        return None, None, None
    parent = notebook.load_notebook(name).cell(parent_cell_id)
    if parent is None or parent.selection is None:
        return None, None, None
    return parent.id, parent.question, parent.selection
