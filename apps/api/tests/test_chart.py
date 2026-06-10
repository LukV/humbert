"""The deterministic chart-spec chooser — type follows the data's shape."""

from __future__ import annotations

from humbert import chart, semantic


def _vocab() -> semantic.Vocabulary:
    dims = [
        semantic.DimensionInfo("cheese_record__country", "categorical"),
        semantic.DimensionInfo("metric_time", "time", grain="year"),
    ]
    return semantic.Vocabulary(
        metrics=[
            semantic.MetricInfo(name="total_production", dimensions=dims),
            semantic.MetricInfo(name="product_variety", dimensions=dims),
        ]
    )


def test_categorical_grouping_is_a_bar() -> None:
    selection = semantic.Selection(
        metrics=["total_production"], group_by=["cheese_record__country"]
    )
    spec = chart.chart_spec(
        selection,
        ["cheese_record__country", "total_production"],
        [["Germany", "100"], ["France", "80"]],
        _vocab(),
    )
    assert spec is not None
    # A horizontal, layered bar (bar + value labels), category on y, measure on x.
    assert spec["layer"][0]["mark"]["type"] == "bar"
    assert spec["encoding"]["y"]["field"] == "cheese_record__country"
    assert spec["encoding"]["x"]["field"] == "total_production"
    # The measure is coerced to a number for the inlined data.
    assert spec["data"]["values"][0]["total_production"] == 100


def test_time_grouping_is_a_line() -> None:
    selection = semantic.Selection(metrics=["total_production"], group_by=["metric_time"])
    spec = chart.chart_spec(
        selection,
        ["metric_time__year", "total_production"],
        [["2015-01-01", "10"], ["2016-01-01", "12"]],
        _vocab(),
    )
    assert spec is not None
    assert spec["mark"]["type"] == "line"
    assert spec["encoding"]["x"]["type"] == "temporal"
    assert spec["encoding"]["x"]["field"] == "metric_time__year"


def test_single_value_is_a_number() -> None:
    selection = semantic.Selection(metrics=["total_production"])
    spec = chart.chart_spec(selection, ["total_production"], [["12345"]], _vocab())
    assert spec is not None
    assert spec["mark"]["type"] == "text"
    assert spec["data"]["values"] == [{"total_production": 12345}]


def test_no_rows_is_no_chart() -> None:
    selection = semantic.Selection(
        metrics=["total_production"], group_by=["cheese_record__country"]
    )
    spec = chart.chart_spec(selection, ["cheese_record__country", "total_production"], [], _vocab())
    assert spec is None


def test_two_measures_over_a_dimension_is_a_scatter() -> None:
    selection = semantic.Selection(
        metrics=["total_production", "product_variety"],
        group_by=["cheese_record__country"],
    )
    spec = chart.chart_spec(
        selection,
        ["cheese_record__country", "total_production", "product_variety"],
        [["Germany", "100", "8"], ["France", "80", "12"], ["Italy", "60", "20"]],
        _vocab(),
    )
    assert spec is not None
    assert spec["mark"]["type"] == "point"
    assert spec["encoding"]["x"]["field"] == "total_production"
    assert spec["encoding"]["y"]["field"] == "product_variety"
    # Uniform points — the dimension is the tooltip, not a colour key.
    assert "color" not in spec["encoding"]
    assert spec["encoding"]["tooltip"][0]["field"] == "cheese_record__country"
    # Both measures coerced to numbers; the dimension stays a label.
    first = spec["data"]["values"][0]
    assert first == {
        "cheese_record__country": "Germany",
        "total_production": 100,
        "product_variety": 8,
    }


def test_two_measures_with_too_few_points_is_no_chart() -> None:
    """A two-measure answer filtered down to a point or two tells no story."""
    selection = semantic.Selection(
        metrics=["total_production", "product_variety"],
        group_by=["cheese_record__country"],
    )
    spec = chart.chart_spec(
        selection,
        ["cheese_record__country", "total_production", "product_variety"],
        [["France", "80", "12"]],
        _vocab(),
    )
    assert spec is None


def test_two_measures_without_a_grouping_is_no_chart() -> None:
    """A single (x, y) point tells no story — the narrative carries the figures."""
    selection = semantic.Selection(metrics=["total_production", "product_variety"])
    spec = chart.chart_spec(
        selection,
        ["total_production", "product_variety"],
        [["100", "8"]],
        _vocab(),
    )
    assert spec is None


def test_three_metrics_is_no_chart() -> None:
    selection = semantic.Selection(metrics=["a", "b", "c"])
    spec = chart.chart_spec(selection, ["a", "b", "c"], [["1", "2", "3"]], _vocab())
    assert spec is None


def test_bar_is_capped_and_sorted_by_value() -> None:
    """A broad answer renders the top slice, largest first — not a wall of bars."""
    selection = semantic.Selection(
        metrics=["total_production"], group_by=["cheese_record__country"]
    )
    rows = [[f"c{i}", str(i)] for i in range(50)]  # 50 categories, ascending value
    spec = chart.chart_spec(
        selection, ["cheese_record__country", "total_production"], rows, _vocab()
    )
    assert spec is not None
    values = spec["data"]["values"]
    assert len(values) == chart._TOP_N
    # Capped to the largest by value (49 is the biggest), descending.
    assert values[0]["total_production"] == 49
    assert spec["encoding"]["y"]["sort"] == "-x"


def test_time_plus_category_is_a_multi_line() -> None:
    """Time + one categorical → a line per category — the comparison-over-time shape."""
    selection = semantic.Selection(
        metrics=["total_production"], group_by=["metric_time", "cheese_record__country"]
    )
    spec = chart.chart_spec(
        selection,
        ["metric_time__year", "cheese_record__country", "total_production"],
        [
            ["2015-01-01", "France", "10"],
            ["2015-01-01", "Germany", "20"],
            ["2016-01-01", "France", "12"],
            ["2016-01-01", "Germany", "22"],
        ],
        _vocab(),
    )
    assert spec is not None
    assert spec["layer"][0]["mark"]["type"] == "line"
    assert spec["encoding"]["x"]["field"] == "metric_time__year"
    assert spec["encoding"]["color"]["field"] == "cheese_record__country"


def test_many_series_over_time_is_no_chart() -> None:
    """A broad split would be spaghetti — it falls through to narrative-only."""
    selection = semantic.Selection(
        metrics=["total_production"], group_by=["metric_time", "cheese_record__country"]
    )
    rows = [[f"201{y}-01-01", f"c{c}", str(c)] for y in range(2) for c in range(8)]
    spec = chart.chart_spec(
        selection,
        ["metric_time__year", "cheese_record__country", "total_production"],
        rows,
        _vocab(),
    )
    assert spec is None


def test_two_categoricals_is_no_chart() -> None:
    selection = semantic.Selection(
        metrics=["total_production"],
        group_by=["cheese_record__country", "cheese_record__product"],
    )
    spec = chart.chart_spec(
        selection,
        ["cheese_record__country", "cheese_record__product", "total_production"],
        [["Germany", "Gouda", "100"]],
        _vocab(),
    )
    assert spec is None


def test_non_numeric_measure_stays_text() -> None:
    """A value that won't parse as a number is left as-is, not dropped."""
    selection = semantic.Selection(
        metrics=["total_production"], group_by=["cheese_record__country"]
    )
    spec = chart.chart_spec(
        selection,
        ["cheese_record__country", "total_production"],
        [["Germany", "n/a"]],
        _vocab(),
    )
    assert spec is not None
    assert spec["data"]["values"][0]["total_production"] == "n/a"
