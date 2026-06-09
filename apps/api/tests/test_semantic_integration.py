"""End-to-end semantic module against the real examples/cheese source.

Skipped in lean CI: it needs the dbt extra (``mf`` on PATH) and a built cheese
warehouse. Run it locally after `humbert connect ../../examples/cheese`:

    uv run --extra dbt pytest tests/test_semantic_integration.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from humbert import semantic

CHEESE = Path(__file__).resolve().parents[3] / "examples" / "cheese"

pytestmark = pytest.mark.skipif(
    shutil.which("mf") is None or not (CHEESE / "warehouse.duckdb").exists(),
    reason="needs the dbt extra and a built examples/cheese warehouse",
)


def test_vocabulary_exposes_total_production() -> None:
    vocab = semantic.discover_vocabulary(CHEESE)
    metric = vocab.metric("total_production")
    assert metric is not None
    names = {d.name for d in metric.dimensions}
    assert "cheese_record__country" in names
    assert "metric_time" in names


def test_pack_passes_its_own_guard() -> None:
    """The cheese marts are classified `open`, so nothing is withheld."""
    pack = semantic.load_pack(CHEESE)
    assert pack.withheld == []
    assert "total_production" in pack.vocabulary.metric_names()


def test_query_ranks_germany_top() -> None:
    """The acceptance check: real production reality, through the whole module."""
    vocab = semantic.discover_vocabulary(CHEESE)
    selection = semantic.Selection(
        metrics=["total_production"],
        group_by=["cheese_record__country"],
        order_by=["-total_production"],
        limit=5,
    )
    resolved = semantic.resolve(selection, vocab)
    assert isinstance(resolved, semantic.ResolvedSelection)

    result = semantic.run(resolved, vocab, CHEESE)
    assert result.columns == ["cheese_record__country", "total_production"]
    top_countries = [row[0] for row in result.rows]
    assert top_countries[0] == "Germany"
    assert "France" in top_countries
    assert result.compiled_sql.upper().startswith("SELECT")


def test_unresolved_selection_names_the_gap() -> None:
    vocab = semantic.discover_vocabulary(CHEESE)
    resolved = semantic.resolve(semantic.Selection(metrics=["visitors"]), vocab)
    assert isinstance(resolved, semantic.Unresolved)
    assert any("visitors" in p for p in resolved.problems)


def test_templated_where_filter_runs() -> None:
    """A `where` filter must use MetricFlow's template syntax, not raw SQL columns.

    Regression for the trend-with-filter case ("Germany since 2015"): a raw
    `cheese_record__country = 'Germany'` fails to bind when country isn't grouped;
    the `{{ Dimension(...) }}` / `{{ TimeDimension(...) }}` form is what works.
    """
    vocab = semantic.discover_vocabulary(CHEESE)
    selection = semantic.Selection(
        metrics=["total_production"],
        group_by=["metric_time"],
        where=[
            "{{ Dimension('cheese_record__country') }} = 'Germany' "
            "AND {{ TimeDimension('metric_time', 'year') }} >= '2015-01-01'"
        ],
        order_by=["metric_time"],
        time_grain="year",
    )
    resolved = semantic.resolve(selection, vocab)
    assert isinstance(resolved, semantic.ResolvedSelection)

    result = semantic.run(resolved, vocab, CHEESE)
    assert result.columns == ["metric_time__year", "total_production"]
    assert len(result.rows) == 9  # 2015 through 2023
