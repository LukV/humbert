"""The two-call loop against a real model and the real cheese source.

Skipped in lean CI: it needs the dbt extra (``mf`` on PATH), a built cheese
warehouse, *and* a real ``ANTHROPIC_API_KEY`` — so it costs a model call and is a
local-only check. Run it after `humbert connect ../../examples/cheese`:

    ANTHROPIC_API_KEY=… uv run --extra dbt pytest tests/test_orchestrator_integration.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from humbert import orchestrator, semantic
from humbert.config import LLM

CHEESE = Path(__file__).resolve().parents[3] / "examples" / "cheese"

pytestmark = pytest.mark.skipif(
    shutil.which("mf") is None
    or not (CHEESE / "warehouse.duckdb").exists()
    or not os.environ.get("ANTHROPIC_API_KEY"),
    reason="needs the dbt extra, a built cheese warehouse, and ANTHROPIC_API_KEY",
)


def test_ask_ranks_germany_top_over_real_rows() -> None:
    """The acceptance check: plain question → correct narrated answer, end to end."""
    vocabulary = semantic.discover_vocabulary(CHEESE)
    model = orchestrator.build_model(LLM())

    answer = orchestrator.ask(
        "which countries produce the most cheese?",
        project_dir=CHEESE,
        vocabulary=vocabulary,
        model=model,
    )

    assert isinstance(answer, orchestrator.Answer)
    # The numbers come from the engine, so Germany leads the real rows.
    assert answer.rows[0][0] == "Germany"
    # And the narrative, written over those rows, names it.
    assert "Germany" in answer.narrative
    assert answer.compiled_sql.upper().startswith("SELECT")
    assert answer.tier == 1


def test_unanswerable_question_stops_plainly() -> None:
    """No defined metric for visitor counts → the plain Tier-1 boundary, not a guess."""
    vocabulary = semantic.discover_vocabulary(CHEESE)
    model = orchestrator.build_model(LLM())

    answer = orchestrator.ask(
        "how many museum visitors were there last year?",
        project_dir=CHEESE,
        vocabulary=vocabulary,
        model=model,
    )
    assert isinstance(answer, orchestrator.NoTier1Answer)
    assert answer.problems
