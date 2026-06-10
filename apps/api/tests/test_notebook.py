"""The cell and its notebook — building from an answer, and faithful round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from humbert import notebook, orchestrator, semantic


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUMBERT_HOME", str(tmp_path))
    return tmp_path


def _vocab() -> semantic.Vocabulary:
    return semantic.Vocabulary(
        metrics=[
            semantic.MetricInfo(
                name="total_production",
                dimensions=[semantic.DimensionInfo("cheese_record__country", "categorical")],
            )
        ]
    )


def _answer() -> orchestrator.Answer:
    return orchestrator.Answer(
        question="which countries produce the most cheese?",
        reading="read cheese as total_production, by country",
        selection=semantic.Selection(
            metrics=["total_production"], group_by=["cheese_record__country"]
        ),
        columns=["cheese_record__country", "total_production"],
        rows=[["Germany", "100"], ["France", "80"]],
        compiled_sql="SELECT country, sum(kg) ...",
        narrative="Germany leads.",
        certainty="high",
    )


def test_record_appends_and_assigns_ids(home: Path) -> None:
    first = notebook.record(
        "cheese", _answer(), vocabulary=_vocab(), model="claude", created_at="2026-06-09 10:00"
    )
    second = notebook.record(
        "cheese", _answer(), vocabulary=_vocab(), model="claude", created_at="2026-06-09 10:01"
    )
    assert first.id == 1
    assert second.id == 2
    assert len(notebook.load_notebook("cheese").cells) == 2


def test_cell_from_answer_carries_the_chart_spec(home: Path) -> None:
    cell = notebook.record(
        "cheese", _answer(), vocabulary=_vocab(), model="claude", created_at="2026-06-09 10:00"
    )
    assert cell.status == "answered"
    assert cell.tier == 1
    assert cell.certainty == "high"
    assert cell.row_count == 2
    assert cell.chart is not None
    assert cell.chart["layer"][0]["mark"]["type"] == "bar"


def test_no_tier1_answer_becomes_a_cell(home: Path) -> None:
    miss = orchestrator.NoTier1Answer(
        question="how many visitors?",
        reading="read visitors",
        problems=['unknown metric "visitors"'],
    )
    cell = notebook.record(
        "cheese", miss, vocabulary=_vocab(), model="claude", created_at="2026-06-09 10:00"
    )
    assert cell.status == "no_tier1"
    assert cell.chart is None
    assert cell.problems == ['unknown metric "visitors"']


def test_notebook_round_trips_faithfully(home: Path) -> None:
    """A reloaded cell is identical to the stored one — the cut line."""
    saved = notebook.record(
        "cheese", _answer(), vocabulary=_vocab(), model="claude", created_at="2026-06-09 10:00"
    )
    reloaded = notebook.load_notebook("cheese").cell(saved.id)
    assert reloaded is not None
    assert reloaded == saved


def test_empty_notebook_when_none_exists(home: Path) -> None:
    assert notebook.load_notebook("cheese").cells == []


def test_delete_removes_a_cell(home: Path) -> None:
    first = notebook.record(
        "cheese", _answer(), vocabulary=_vocab(), model="claude", created_at="2026-06-09 10:00"
    )
    second = notebook.record(
        "cheese", _answer(), vocabulary=_vocab(), model="claude", created_at="2026-06-09 10:01"
    )
    assert notebook.delete("cheese", first.id) is True
    remaining = notebook.load_notebook("cheese").cells
    assert [c.id for c in remaining] == [second.id]


def test_delete_unknown_id_is_a_quiet_no_op(home: Path) -> None:
    notebook.record(
        "cheese", _answer(), vocabulary=_vocab(), model="claude", created_at="2026-06-09 10:00"
    )
    assert notebook.delete("cheese", 999) is False
    assert len(notebook.load_notebook("cheese").cells) == 1
