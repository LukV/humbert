"""The notebook's cells: list, rename, delete."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from humbert import notebook
from humbert.server.deps import ConnectionDep
from humbert.server.errors import APIError
from humbert.server.wire import wire_cell

router = APIRouter()


class CellPatch(BaseModel):
    title: str


@router.get("/notebook")
def get_notebook(active: ConnectionDep) -> JSONResponse:
    name, _project = active
    book = notebook.load_notebook(name)
    return JSONResponse([wire_cell(c) for c in book.cells])


@router.patch("/cells/{cell_id}")
def patch_cell(cell_id: int, patch: CellPatch, active: ConnectionDep) -> JSONResponse:
    name, _project = active
    cell = notebook.set_title(name, cell_id, patch.title)
    if cell is None:
        raise APIError(404, "No such cell")
    return JSONResponse(wire_cell(cell))


@router.delete("/cells/{cell_id}")
def delete_cell(cell_id: int, active: ConnectionDep) -> JSONResponse:
    name, _project = active
    return JSONResponse({"deleted": notebook.delete(name, cell_id)})
