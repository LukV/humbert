"""Suggestions, the schema stub, and feedback."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from humbert import notebook
from humbert.server.deps import ConnectionDep, StateDep

router = APIRouter()


class Feedback(BaseModel):
    cell_id: str
    rating: str


@router.get("/suggestions")
def suggestions(state: StateDep) -> JSONResponse:
    """The empty-state chips — one per chart shape, from config (static for v0)."""
    return JSONResponse({"suggestions": state.config.settings.suggestions, "generating": False})


@router.get("/schema")
def schema() -> JSONResponse:
    """A stub so the SPA's schema probe resolves cleanly."""
    return JSONResponse({"schema": {"tables": []}})


@router.post("/feedback")
def feedback(body: Feedback, active: ConnectionDep) -> JSONResponse:
    """Append a thumbs up/down to the connection's ``feedback.jsonl``. The file
    is the truth; the UI fires and forgets."""
    name, _project = active
    notebook.record_feedback(name, cell_id=body.cell_id, rating=body.rating)
    return JSONResponse({"ok": True})
