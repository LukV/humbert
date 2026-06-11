"""The seam between a stored ``Cell`` and the JSON shape the SPA renders.

The frontend reads a richer, nested cell — ``result`` / ``sql`` / ``chart`` /
``narrative`` / ``refusal`` / ``metadata`` — than the flat ``notebook.Cell`` we
persist. This module is the one place that mapping lives, so the persistence
model stays Humbert's own and the wire shape stays the frontend's.

The one subtlety is data typing: Humbert stores every result value as text, but
Vega-Lite needs *numbers* under a ``quantitative`` encoding. The measure columns
(the ones named in the selection's metrics) are coerced back to numbers via
``chart.rows_to_records`` — the same coercion the chart spec gets, so chart and
table can never disagree.
"""

from __future__ import annotations

from typing import Any

from humbert import chart, notebook


def _refusal_detail(cell: notebook.Cell) -> str:
    """A single human line for a no-Tier-1 cell: how it read it, what didn't fit."""
    parts = [cell.reading, *cell.problems]
    detail = "; ".join(p for p in parts if p)
    return detail or "No defined metric fit this question."


def wire_cell(cell: notebook.Cell) -> dict[str, Any]:
    """Serialize a stored cell into the nested shape the frontend renders."""
    answered = cell.status == "answered"
    measures = set(cell.selection.metrics) if cell.selection else set()
    data = chart.rows_to_records(cell.columns, cell.rows, measures)

    sql = (
        {
            "query": cell.sql,
            "generated_by": cell.model or "",
            "edited_by_user": cell.edited,
            "user_sql_override": None,
        }
        if answered and cell.sql
        else None
    )

    result = (
        {
            "columns": cell.columns,
            "column_types": ["" for _ in cell.columns],
            "row_count": cell.row_count,
            "data_hash": "",
            "data": data,
            "truncated": False,
            "execution_time_ms": round(cell.duration_seconds * 1000),
            "diagnostics": [],
        }
        if answered
        else None
    )

    chart_block = (
        {"spec": cell.chart, "auto_detected": True, "theme": "humbert"} if cell.chart else None
    )

    narrative = (
        {"text": cell.narrative, "data_references": []} if answered and cell.narrative else None
    )

    refusal = (
        None
        if answered
        else {
            "category": "no_valid_metric",
            "reason": {
                "code": "no_tier1",
                "detail": _refusal_detail(cell),
                "suggestion": None,
                "subject": None,
            },
            "detected_by": "planner",
        }
    )

    return {
        "id": str(cell.id),
        "created_at": cell.created_at,
        "cell_type": "analysis",
        "question": cell.question,
        "title": cell.title,
        "context": {
            "parent_cell_id": (str(cell.parent_id) if cell.parent_id is not None else None),
            "refinement_of": (str(cell.refinement_of) if cell.refinement_of is not None else None),
            "conversation_position": 0,
        },
        "sql": sql,
        "result": result,
        "chart": chart_block,
        "narrative": narrative,
        "refusal": refusal,
        "metadata": {
            "model": cell.model or "",
            "schema_version": "",
            "agent_steps": [],
            "retry_count": 0,
            "reasoning": cell.reading,
        },
    }
