"""The semantic module — resolve/IR/vocabulary logic, engine stubbed.

No dbt or mf here: the engine reads/run are faked so this runs in lean CI. The
real compile-and-run path is covered by test_semantic_integration.py (skipped
without the dbt extra).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from humbert import engine, semantic


def _cheese_vocab() -> semantic.Vocabulary:
    return semantic.Vocabulary(
        metrics=[
            semantic.MetricInfo(
                name="total_production",
                dimensions=[
                    semantic.DimensionInfo("cheese_record__country", "categorical"),
                    semantic.DimensionInfo("cheese_record__product", "categorical"),
                    semantic.DimensionInfo("metric_time", "time", grain="day"),
                ],
            )
        ]
    )


# --- discover_vocabulary --------------------------------------------------


def _stub_open(monkeypatch: pytest.MonkeyPatch, metric: str = "total_production") -> None:
    """Stub the engine reads so `metric` traces to a single open model."""
    monkeypatch.setattr(engine, "metric_names", lambda p: [metric])
    monkeypatch.setattr(engine, "classifications", lambda p: {"fct": "open"})
    monkeypatch.setattr(engine, "metric_source_models", lambda p: {metric: ["fct"]})


def test_discover_vocabulary_enriches_kind_and_grain(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_open(monkeypatch)
    monkeypatch.setattr(
        engine,
        "dimensions",
        lambda p, m: ["cheese_record__country", "metric_time"],
    )
    monkeypatch.setattr(
        engine,
        "dimension_types",
        lambda p: {
            "country": engine.DimensionMeta(kind="categorical"),
            "metric_time": engine.DimensionMeta(kind="time", grain="day"),
        },
    )
    vocab = semantic.discover_vocabulary(Path("/x"))
    metric = vocab.metric("total_production")
    assert metric is not None
    by_name = {d.name: d for d in metric.dimensions}
    assert by_name["cheese_record__country"].kind == "categorical"
    assert by_name["metric_time"].kind == "time"
    assert by_name["metric_time"].grain == "day"


# --- the public-only guard ------------------------------------------------


def test_classify_exposes_open_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, "metric_names", lambda p: ["total_production"])
    monkeypatch.setattr(engine, "classifications", lambda p: {"fct": "open"})
    monkeypatch.setattr(engine, "metric_source_models", lambda p: {"total_production": ["fct"]})
    exposed, withheld = semantic.classify_metrics(Path("/x"))
    assert exposed == ["total_production"]
    assert withheld == []


def test_classify_withholds_non_open_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, "metric_names", lambda p: ["secret_metric"])
    monkeypatch.setattr(engine, "classifications", lambda p: {"fct_secret": "internal"})
    monkeypatch.setattr(engine, "metric_source_models", lambda p: {"secret_metric": ["fct_secret"]})
    exposed, withheld = semantic.classify_metrics(Path("/x"))
    assert exposed == []
    assert withheld[0].metric == "secret_metric"
    assert "fct_secret" in withheld[0].reason


def test_classify_default_deny_on_unclassified(monkeypatch: pytest.MonkeyPatch) -> None:
    # An unclassified model (None) is treated as not-open — withheld.
    monkeypatch.setattr(engine, "metric_names", lambda p: ["m"])
    monkeypatch.setattr(engine, "classifications", lambda p: {"fct": None})
    monkeypatch.setattr(engine, "metric_source_models", lambda p: {"m": ["fct"]})
    exposed, withheld = semantic.classify_metrics(Path("/x"))
    assert exposed == []
    assert len(withheld) == 1


def test_classify_withholds_when_no_source_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, "metric_names", lambda p: ["m"])
    monkeypatch.setattr(engine, "classifications", lambda p: {})
    monkeypatch.setattr(engine, "metric_source_models", lambda p: {"m": []})
    exposed, withheld = semantic.classify_metrics(Path("/x"))
    assert exposed == []
    assert "cannot confirm" in withheld[0].reason


def test_load_pack_excludes_withheld_from_vocabulary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, "metric_names", lambda p: ["open_m", "secret_m"])
    monkeypatch.setattr(engine, "classifications", lambda p: {"ok": "open", "no": "internal"})
    monkeypatch.setattr(
        engine, "metric_source_models", lambda p: {"open_m": ["ok"], "secret_m": ["no"]}
    )
    monkeypatch.setattr(engine, "dimension_types", lambda p: {})
    monkeypatch.setattr(engine, "dimensions", lambda p, m: ["cheese_record__country"])
    pack = semantic.load_pack(Path("/x"))
    assert pack.vocabulary.metric_names() == {"open_m"}
    assert [w.metric for w in pack.withheld] == ["secret_m"]


# --- resolve --------------------------------------------------------------


def test_resolve_happy_path() -> None:
    selection = semantic.Selection(
        metrics=["total_production"],
        group_by=["cheese_record__country"],
        order_by=["-total_production"],
    )
    resolved = semantic.resolve(selection, _cheese_vocab())
    assert isinstance(resolved, semantic.ResolvedSelection)
    assert resolved.selection.metrics == ["total_production"]


def test_resolve_unknown_metric() -> None:
    resolved = semantic.resolve(semantic.Selection(metrics=["visitors"]), _cheese_vocab())
    assert isinstance(resolved, semantic.Unresolved)
    assert any("visitors" in p for p in resolved.problems)


def test_resolve_unknown_dimension() -> None:
    selection = semantic.Selection(metrics=["total_production"], group_by=["cheese_record__region"])
    resolved = semantic.resolve(selection, _cheese_vocab())
    assert isinstance(resolved, semantic.Unresolved)
    assert any("cheese_record__region" in p for p in resolved.problems)


def test_resolve_bad_order_by() -> None:
    selection = semantic.Selection(metrics=["total_production"], order_by=["-nonsense"])
    resolved = semantic.resolve(selection, _cheese_vocab())
    assert isinstance(resolved, semantic.Unresolved)
    assert any("nonsense" in p for p in resolved.problems)


def test_resolve_collects_all_gaps() -> None:
    selection = semantic.Selection(metrics=["visitors"], group_by=["cheese_record__region"])
    resolved = semantic.resolve(selection, _cheese_vocab())
    assert isinstance(resolved, semantic.Unresolved)
    assert len(resolved.problems) == 2


def test_resolve_does_not_validate_where() -> None:
    # where is passed through, never checked against the vocabulary.
    selection = semantic.Selection(
        metrics=["total_production"], where=["{{ Dimension('anything') }} = 1"]
    )
    assert isinstance(semantic.resolve(selection, _cheese_vocab()), semantic.ResolvedSelection)


def test_common_dimensions_is_intersection() -> None:
    vocab = semantic.Vocabulary(
        metrics=[
            semantic.MetricInfo("a", [semantic.DimensionInfo("x", "categorical")]),
            semantic.MetricInfo(
                "b",
                [
                    semantic.DimensionInfo("x", "categorical"),
                    semantic.DimensionInfo("y", "categorical"),
                ],
            ),
        ]
    )
    assert vocab.common_dimensions(["a", "b"]) == {"x"}


# --- run ------------------------------------------------------------------


def test_run_passes_compiled_args_and_returns_result(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_query(project_dir: Path, **kwargs: object) -> engine.QueryResult:
        captured.update(kwargs)
        return engine.QueryResult(
            columns=["cheese_record__country", "total_production"],
            rows=[["Germany", "97767016.0"]],
            compiled_sql="SELECT 1",
        )

    monkeypatch.setattr(engine, "query", fake_query)
    selection = semantic.Selection(
        metrics=["total_production"], group_by=["cheese_record__country"], limit=5
    )
    result = semantic.run(semantic.ResolvedSelection(selection), _cheese_vocab(), Path("/x"))
    assert captured["metrics"] == ["total_production"]
    assert captured["limit"] == 5
    assert result.rows == [["Germany", "97767016.0"]]
    assert result.compiled_sql == "SELECT 1"


def test_run_applies_time_grain_to_time_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_query(project_dir: Path, **kwargs: object) -> engine.QueryResult:
        captured.update(kwargs)
        return engine.QueryResult(columns=[], rows=[], compiled_sql="")

    monkeypatch.setattr(engine, "query", fake_query)
    selection = semantic.Selection(
        metrics=["total_production"],
        group_by=["metric_time", "cheese_record__country"],
        time_grain="year",
    )
    semantic.run(semantic.ResolvedSelection(selection), _cheese_vocab(), Path("/x"))
    # The time dimension gets the grain suffix; the categorical one is untouched.
    assert captured["group_by"] == ["metric_time__year", "cheese_record__country"]
