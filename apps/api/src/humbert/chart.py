"""Pick the right chart spec for an answer's shape — deterministically.

A chart type is a property of the *data*, not a judgement call, so this is plain
code, not an LLM call: it reads the resolved ``Selection`` and the ``Result``'s
columns and emits a Vega-Lite spec (or ``None`` when no chart fits). The spec is
*correct but plain* — the right mark and encodings, no theme. Making it beautiful
(the FT/Observable styling, the project palette) is the Beautiful-defaults pitch.

The rules, from docs/product-design/002-product-forms.md:

- grouped by a **time** dimension → **line** (a trend)
- grouped by a **categorical** dimension, one measure → **bar** (a comparison)
- a **single value** (one row, one measure, no grouping) → **number**
- two measures over a dimension → **scatter** (a relationship between measures)
- otherwise, or nothing to plot → **no chart** (``None``) — a valid outcome

*Pie/share is deliberately absent*: telling a share from a comparison needs a
proportion signal the selection doesn't carry yet, so bar is the honest default.

A broad answer (hundreds of categories) would make an unreadable bar, so bars are
capped at the top ``_TOP_N`` by value — the figure stays composed and the narrative
carries the tail. The cell still stores its full rows; this only bounds the figure.
"""

from __future__ import annotations

from typing import Any

from humbert import semantic

_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"

# A bar with more marks than this is a wall, not a chart — show the top slice.
_TOP_N = 20

# More lines than this on one chart is spaghetti — the design prefers small
# multiples / narrative there, so a broad split falls through to no chart.
_MAX_SERIES = 6

# A scatter with fewer points than this tells no story (a single dot, a pair) —
# it falls through to no chart and the narrative carries the two figures.
_MIN_SCATTER_POINTS = 3


def chart_spec(
    selection: semantic.Selection,
    columns: list[str],
    rows: list[list[str]],
    vocabulary: semantic.Vocabulary,
) -> dict[str, Any] | None:
    """The Vega-Lite spec for this answer's shape, or ``None`` for no chart.

    One measure gives a number / bar / line by its grouping; two measures over a
    dimension give a scatter. Anything wider (three+ measures, multiple groupings)
    returns ``None`` rather than guess a layout.
    """
    if not rows or not columns:
        return None

    if len(selection.metrics) == 2:
        return _scatter(selection, columns, rows)
    if len(selection.metrics) != 1:
        return None

    value_field = _value_column(columns, selection.metrics)
    if value_field is None:
        return None
    groups = selection.group_by

    # One row, one measure, nothing grouped → a single number.
    if not groups and len(rows) == 1:
        value = parse_number(rows[0][columns.index(value_field)])
        return _number_spec(value_field, value)

    # One grouping → line if it's over time, bar otherwise.
    if len(groups) == 1:
        dim_field = _dimension_column(columns, value_field)
        if dim_field is None:
            return None
        data = rows_to_records(columns, rows, {value_field})
        if vocabulary.is_time_dimension(groups[0]):
            return _line_spec(dim_field, value_field, data)
        return _bar_spec(dim_field, value_field, _top_n(data, value_field))

    # Time + one categorical → a line per category (a comparison over time).
    if len(groups) == 2:
        return _time_series_by_category(selection, columns, rows, vocabulary, value_field)

    return None


def _scatter(
    selection: semantic.Selection, columns: list[str], rows: list[list[str]]
) -> dict[str, Any] | None:
    """Two measures over one grouping → a point per group, ``x`` vs ``y``.

    Needs both measures present and exactly one grouping to label the points; a
    two-measure answer with too few points (no grouping, or a filter down to one
    or two rows) tells no story, so it falls through to no chart and the narrative
    carries the two figures.
    """
    measures = [m for m in selection.metrics if m in columns]
    if len(measures) != 2 or len(selection.group_by) != 1:
        return None
    if len(rows) < _MIN_SCATTER_POINTS:
        return None
    x_field, y_field = measures
    label_field = next((c for c in columns if c not in measures), None)
    if label_field is None:
        return None
    data = rows_to_records(columns, rows, set(measures))
    return _scatter_spec(x_field, y_field, label_field, data)


def _time_series_by_category(
    selection: semantic.Selection,
    columns: list[str],
    rows: list[list[str]],
    vocabulary: semantic.Vocabulary,
    value_field: str,
) -> dict[str, Any] | None:
    """A two-grouping answer — one time, one categorical — as a line per category.

    The bivariate-over-time shape behind "compare cheese production between France
    and Germany". Only the small-comparison case renders combined; a broad split
    (many categories) would be spaghetti, so it falls through to no chart.
    """
    groups = selection.group_by
    time_groups = [g for g in groups if vocabulary.is_time_dimension(g)]
    cat_groups = [g for g in groups if not vocabulary.is_time_dimension(g)]
    if len(time_groups) != 1 or len(cat_groups) != 1:
        return None

    series_field = cat_groups[0] if cat_groups[0] in columns else None
    if series_field is None:
        return None
    time_field = next((c for c in columns if c not in (value_field, series_field)), None)
    if time_field is None:
        return None

    series_index = columns.index(series_field)
    if len({row[series_index] for row in rows}) > _MAX_SERIES:
        return None

    data = rows_to_records(columns, rows, {value_field})
    return _multi_line_spec(time_field, value_field, series_field, data)


def _value_column(columns: list[str], metrics: list[str]) -> str | None:
    """The result column carrying the measure, matched by metric name."""
    return next((m for m in metrics if m in columns), None)


def _top_n(data: list[dict[str, Any]], value_field: str) -> list[dict[str, Any]]:
    """The ``_TOP_N`` records with the largest measure — the bar stays readable."""
    numeric = [r for r in data if isinstance(r.get(value_field), int | float)]
    rest = [r for r in data if not isinstance(r.get(value_field), int | float)]
    numeric.sort(key=lambda r: r[value_field], reverse=True)
    return (numeric + rest)[:_TOP_N]


def _dimension_column(columns: list[str], value_field: str) -> str | None:
    """The grouping column — the one that isn't the measure."""
    return next((c for c in columns if c != value_field), None)


def rows_to_records(
    columns: list[str], rows: list[list[str]], measures: set[str]
) -> list[dict[str, Any]]:
    """Rows as records, with the measure columns coerced to numbers.

    Humbert stores result values as text, but Vega-Lite (and the SPA's tables)
    need numbers under quantitative encodings. This is the one place that
    coercion lives — ``server.wire`` reuses it for the wire shape.
    """
    return [
        {
            col: parse_number(cell) if col in measures else cell
            for col, cell in zip(columns, row, strict=False)
        }
        for row in rows
    ]


def parse_number(cell: str) -> Any:
    """Parse a cell to a number when it is one; leave it as text otherwise."""
    try:
        value = float(cell)
    except (TypeError, ValueError):
        return cell
    return int(value) if value.is_integer() else value


# Warm sequential ramp for ranked bars: light tan (smallest) → dark brown
# (largest). A sequence, not the series palette — and never the accent (§5).
_BAR_RAMP = ["#d8b88a", "#6b3f1d"]

# The FT/Observable muted series set (§5) — carries data, never the accent.
_SERIES = ["#6b8f8a", "#c2876e", "#b8a44c", "#8c7b6b", "#a3667e"]

_FONT = "DM Sans, system-ui, sans-serif"
_LABEL_INK = "#5e574d"  # readable warm grey for labels/titles (passes §7 contrast)
_HAIRLINE = "#d8d2c8"  # the single baseline / faint ticks


def _config() -> dict[str, Any]:
    """The Tufte-clean defaults every spec carries (§6): no fill, no gridlines,
    a single baseline, direct labels, the muted series palette, our type.

    The frontend layers dark-mode overrides on top of this same ``config`` block.
    """
    return {
        "background": "transparent",
        "font": _FONT,
        "view": {"stroke": None},
        "axis": {
            "grid": False,
            "domainColor": _HAIRLINE,
            "tickColor": _HAIRLINE,
            "labelColor": _LABEL_INK,
            "titleColor": _LABEL_INK,
            "labelFont": _FONT,
            "titleFont": _FONT,
            "labelFontSize": 11,
            "titleFontSize": 11,
            "titleFontWeight": 500,
            "labelPadding": 6,
            "titlePadding": 10,
        },
        # A horizontal y-title at the top-left reads better than a rotated one.
        "axisY": {
            "domain": False,
            "ticks": False,
            "titleAngle": 0,
            "titleAlign": "left",
            "titleAnchor": "start",
            "titleX": 0,
            "titleY": -8,
        },
        "range": {"category": _SERIES},
        "legend": {
            "labelFont": _FONT,
            "titleFont": _FONT,
            "labelColor": _LABEL_INK,
            "titleColor": _LABEL_INK,
        },
    }


def _label(field: str) -> str:
    """A human axis label from a metric/dimension name: ``total_production`` →
    ``total production``, ``cheese_record__country`` → ``country``."""
    return field.split("__")[-1].replace("_", " ")


def _bar_spec(dim_field: str, value_field: str, data: list[dict[str, Any]]) -> dict[str, Any]:
    # Horizontal, sorted by the measure: a ranking reads top-down. The value is
    # direct-labelled at the bar end (§6), so the x-axis is dropped entirely.
    return {
        "$schema": _SCHEMA,
        "width": "container",
        "data": {"values": data},
        "encoding": {
            "y": {
                "field": dim_field,
                "type": "nominal",
                "sort": "-x",
                "axis": {"title": None, "domain": False, "ticks": False, "labelPadding": 8},
            },
            "x": {"field": value_field, "type": "quantitative", "axis": None},
        },
        "layer": [
            {
                "mark": {"type": "bar", "height": {"band": 0.68}, "cornerRadiusEnd": 2},
                "encoding": {
                    "color": {
                        "field": value_field,
                        "type": "quantitative",
                        "scale": {"range": _BAR_RAMP},
                        "legend": None,
                    }
                },
            },
            {
                "mark": {"type": "text", "align": "left", "dx": 6, "color": _LABEL_INK},
                "encoding": {
                    "text": {"field": value_field, "type": "quantitative", "format": ",.0f"}
                },
            },
        ],
        "config": _config(),
    }


def _scatter_spec(
    x_field: str, y_field: str, label_field: str, data: list[dict[str, Any]]
) -> dict[str, Any]:
    # Uniform points (the dimension is the tooltip, not a colour key), humanised
    # axis titles, no gridlines.
    return {
        "$schema": _SCHEMA,
        "width": "container",
        "height": 300,
        "data": {"values": data},
        "mark": {"type": "point", "filled": True, "size": 90, "color": _SERIES[0], "opacity": 0.85},
        "encoding": {
            "x": {
                "field": x_field,
                "type": "quantitative",
                "title": _label(x_field),
                "axis": {"format": "~s"},
            },
            "y": {
                "field": y_field,
                "type": "quantitative",
                "title": _label(y_field),
                "axis": {"format": "~s"},
            },
            "tooltip": [
                {"field": label_field, "type": "nominal", "title": _label(label_field)},
                {"field": x_field, "type": "quantitative", "title": _label(x_field)},
                {"field": y_field, "type": "quantitative", "title": _label(y_field)},
            ],
        },
        "config": _config(),
    }


def _line_spec(dim_field: str, value_field: str, data: list[dict[str, Any]]) -> dict[str, Any]:
    # Humanised titles, abbreviated y ticks (12M, not 12,000,000), a single muted
    # series colour, no gridlines — the trend, not the graph paper.
    return {
        "$schema": _SCHEMA,
        "width": "container",
        "height": 280,
        "data": {"values": data},
        "mark": {"type": "line", "color": _SERIES[0], "strokeWidth": 2},
        "encoding": {
            "x": {
                "field": dim_field,
                "type": "temporal",
                "title": _label(dim_field),
                "axis": {"format": "%Y", "labelAngle": 0},
            },
            "y": {
                "field": value_field,
                "type": "quantitative",
                "title": _label(value_field),
                "axis": {"format": "~s"},
            },
        },
        "config": _config(),
    }


def _multi_line_spec(
    time_field: str, value_field: str, series_field: str, data: list[dict[str, Any]]
) -> dict[str, Any]:
    # A line per category, direct-labelled at its last point (§6: labels over a
    # legend), the series palette carrying the categories — never the accent.
    return {
        "$schema": _SCHEMA,
        "width": "container",
        "height": 300,
        "padding": {"left": 5, "top": 5, "right": 72, "bottom": 5},
        "data": {"values": data},
        "encoding": {
            "x": {
                "field": time_field,
                "type": "temporal",
                "title": _label(time_field),
                "axis": {"format": "%Y", "labelAngle": 0},
            },
            "y": {
                "field": value_field,
                "type": "quantitative",
                "title": _label(value_field),
                "axis": {"format": "~s"},
            },
            "color": {
                "field": series_field,
                "type": "nominal",
                "legend": None,
                "scale": {"range": _SERIES},
            },
        },
        # Rank each series' rows by time so the label layer can pick the last point.
        "transform": [
            {
                "window": [{"op": "rank", "as": "_rank"}],
                "sort": [{"field": time_field, "order": "descending"}],
                "groupby": [series_field],
            }
        ],
        "layer": [
            {"mark": {"type": "line", "strokeWidth": 2}},
            {
                "mark": {
                    "type": "text",
                    "align": "left",
                    "dx": 6,
                    "fontSize": 11,
                    "fontWeight": 500,
                },
                "encoding": {"text": {"field": series_field, "type": "nominal"}},
                "transform": [{"filter": "datum._rank === 1"}],
            },
        ],
        "config": _config(),
    }


def _number_spec(value_field: str, value: Any) -> dict[str, Any]:
    # The frontend renders this shape as styled HTML (big serif tabular numerals,
    # locale-formatted); this Vega fallback stays plain and transparent.
    return {
        "$schema": _SCHEMA,
        "data": {"values": [{value_field: value}]},
        "mark": {
            "type": "text",
            "fontSize": 48,
            "font": "Source Serif 4, serif",
            "fontWeight": 500,
            "align": "left",
            "color": "#1a1a1a",
        },
        "encoding": {"text": {"field": value_field, "type": "quantitative", "format": ",.0f"}},
        "config": {"background": "transparent", "view": {"stroke": None}},
    }
