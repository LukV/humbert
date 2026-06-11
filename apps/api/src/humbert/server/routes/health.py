"""``GET /api/healthz`` — named checks for the SPA topbar and diagnostics."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from humbert import engine
from humbert.server.deps import StateDep

router = APIRouter()


@router.get("/healthz")
def healthz(state: StateDep) -> JSONResponse:
    """Health for both the SPA topbar and the CLI/diagnostics — named checks.

    Lightweight by design (fast file reads, no dbt subprocess): the active
    connection is configured, the warehouse file is present, and the semantic
    layer parses with metrics. ``down`` means nothing can be asked; ``degraded``
    means the warehouse is there but the metrics aren't readable.
    """
    active = state.active_project()
    if active is None:
        return JSONResponse(
            {
                "status": "down",
                "project": None,
                "checks": [{"name": "connection", "ok": False, "detail": "No active connection"}],
            }
        )
    name, project = active
    checks: list[dict[str, object]] = [{"name": "connection", "ok": True, "detail": name}]

    warehouse = engine.warehouse_path(project)
    warehouse_ok = warehouse.exists()
    checks.append(
        {
            "name": "warehouse",
            "ok": warehouse_ok,
            # Name the resolved file so a profile/path mismatch is visible
            # here (the warehouse points where profiles.yml says it does).
            "detail": (
                f"ready ({warehouse.name})"
                if warehouse_ok
                else f"not found at {warehouse.name} — run `humbert connect --build`"
            ),
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
