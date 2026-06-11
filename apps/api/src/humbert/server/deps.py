"""FastAPI dependencies — the app state, and the guard most routes share."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request

from humbert.server.errors import no_connection
from humbert.server.state import AppState


def get_app_state(request: Request) -> AppState:
    state: AppState = request.app.state.app_state
    return state


StateDep = Annotated[AppState, Depends(get_app_state)]


def require_connection(state: StateDep) -> tuple[str, Path]:
    """The active connection's (name, dbt project dir), or the 400 the SPA shows."""
    active = state.active_project()
    if active is None:
        raise no_connection()
    return active


ConnectionDep = Annotated[tuple[str, Path], Depends(require_connection)]
