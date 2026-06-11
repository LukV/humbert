"""The cell — the reproducible unit — and the notebook that persists it.

A ``Cell`` is the record of one question and its answer: the verbatim question,
how it was read, the ``Selection`` and SQL behind it, the rows, a correct (plain)
chart spec, the narrative, and the metadata that says how the answer was reached.
A ``Notebook`` is an ordered list of cells, persisted as one ``notebook.json`` per
connection under ``projects/<name>/`` — the same per-connection cache the rest of
Humbert uses.

This layer maps an in-flight ``orchestrator.Answer`` into a stored ``Cell`` and
back; the orchestrator stays unaware that persistence exists. Editing a cell's
title or SQL (Refinement), freezing it (Validation), and rendering it in a browser
are later pitches — the fields are here, the doors aren't opened yet.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from humbert import chart, orchestrator, semantic
from humbert.config import project_dir

CellStatus = Literal["answered", "no_tier1"]

# The human-readable stamp cells carry (shown verbatim in the UI footer).
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"

# Mutations are load → modify → save on one JSON file, and the server runs each
# ask on its own thread — serialise them so two in-flight answers can't both
# claim the same id and silently drop a cell.
_write_lock = threading.Lock()


class Cell(BaseModel):
    """One question and its answer, stored so it re-renders faithfully."""

    id: int
    title: str
    created_at: str
    question: str
    reading: str = ""
    status: CellStatus

    # Query — the reproducible IR and the SQL it compiled to.
    selection: semantic.Selection | None = None
    sql: str = ""
    dialect: str = "duckdb"
    edited: bool = False  # set by the Refinement pitch when the SQL is hand-edited

    # Result.
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    row_count: int = 0
    duration_seconds: float = 0.0  # wall-clock of the query run, shown in the footer

    # The Vega-Lite spec for this answer's shape, or None when no chart fits.
    chart: dict[str, Any] | None = None

    # Narrative + how the answer was reached.
    narrative: str = ""
    model: str | None = None
    tier: int | None = None
    certainty: str | None = None

    # Context — carried for the Refinement pitch to wire; unused here.
    parent_id: int | None = None
    refinement_of: int | None = None

    # When status is "no_tier1": what the planner reached for that didn't resolve.
    problems: list[str] = Field(default_factory=list)


class Notebook(BaseModel):
    """An ordered list of cells for one connection."""

    cells: list[Cell] = Field(default_factory=list)

    def next_id(self) -> int:
        return max((c.id for c in self.cells), default=0) + 1

    def cell(self, cell_id: int) -> Cell | None:
        return next((c for c in self.cells if c.id == cell_id), None)


def notebook_path(connection_name: str) -> Path:
    return project_dir(connection_name) / "notebook.json"


def load_notebook(connection_name: str) -> Notebook:
    """Load the connection's notebook, or an empty one if none exists yet."""
    path = notebook_path(connection_name)
    if not path.exists():
        return Notebook()
    return Notebook.model_validate_json(path.read_text())


def save_notebook(connection_name: str, notebook: Notebook) -> None:
    path = notebook_path(connection_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(notebook.model_dump_json(indent=2) + "\n")


def record(
    connection_name: str,
    answer: orchestrator.Answer | orchestrator.NoTier1Answer,
    *,
    vocabulary: semantic.Vocabulary,
    model: str | None,
    created_at: str | None = None,
    parent_id: int | None = None,
) -> Cell:
    """Append an answer to the connection's notebook as a new cell, and persist it.

    ``created_at`` defaults to now; pass it only to pin a stamp (tests do).
    """
    with _write_lock:
        notebook = load_notebook(connection_name)
        cell = _cell_from_answer(
            answer,
            cell_id=notebook.next_id(),
            vocabulary=vocabulary,
            model=model,
            created_at=created_at or datetime.now().strftime(TIMESTAMP_FORMAT),
            parent_id=parent_id,
        )
        notebook.cells.append(cell)
        save_notebook(connection_name, notebook)
    return cell


def set_title(connection_name: str, cell_id: int, title: str) -> Cell | None:
    """Rename a cell. Returns the updated cell, or None if the id is unknown.

    An empty title means "fall back to the question" — the frontend renders
    ``title || question``, so we store the empty string verbatim.
    """
    with _write_lock:
        notebook = load_notebook(connection_name)
        cell = notebook.cell(cell_id)
        if cell is None:
            return None
        cell.title = title
        save_notebook(connection_name, notebook)
    return cell


def delete(connection_name: str, cell_id: int) -> bool:
    """Drop a cell from the connection's notebook. Idempotent.

    Returns whether a cell was removed — an unknown id is a quiet no-op, not an
    error, so a double-delete (or a stale UI) is harmless.
    """
    with _write_lock:
        notebook = load_notebook(connection_name)
        remaining = [c for c in notebook.cells if c.id != cell_id]
        if len(remaining) == len(notebook.cells):
            return False
        notebook.cells = remaining
        save_notebook(connection_name, notebook)
    return True


def record_feedback(connection_name: str, *, cell_id: str, rating: str) -> None:
    """Append a thumbs up/down to the connection's ``feedback.jsonl``.

    The file is the truth; the UI fires and forgets. Lives here with the rest
    of the per-connection persistence.
    """
    path = notebook_path(connection_name).with_name("feedback.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "cell_id": cell_id,
        "rating": rating,
        "at": datetime.now().isoformat(timespec="seconds"),
    }
    with path.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


def _cell_from_answer(
    answer: orchestrator.Answer | orchestrator.NoTier1Answer,
    *,
    cell_id: int,
    vocabulary: semantic.Vocabulary,
    model: str | None,
    created_at: str,
    parent_id: int | None = None,
) -> Cell:
    if isinstance(answer, orchestrator.NoTier1Answer):
        return Cell(
            id=cell_id,
            title=answer.question,
            created_at=created_at,
            question=answer.question,
            reading=answer.reading,
            status="no_tier1",
            problems=answer.problems,
            model=model,
            parent_id=parent_id,
        )

    spec = chart.chart_spec(answer.selection, answer.columns, answer.rows, vocabulary)
    return Cell(
        id=cell_id,
        title=answer.question,
        created_at=created_at,
        question=answer.question,
        reading=answer.reading,
        status="answered",
        selection=answer.selection,
        sql=answer.compiled_sql,
        columns=answer.columns,
        rows=answer.rows,
        row_count=len(answer.rows),
        duration_seconds=answer.duration_seconds,
        chart=spec,
        narrative=answer.narrative,
        model=model,
        tier=answer.tier,
        certainty=answer.certainty,
        parent_id=parent_id,
    )
