"""Engine helpers — artifact reading and the introspect sort.

The subprocess parts (`parse`, `mf validate-configs`) are stubbed; the manifest
readers and the fatal/degraded logic are real.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from humbert import engine


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def _write_artifacts(
    project: Path,
    *,
    models: dict[str, str],
    metrics: list[str],
) -> None:
    target = project / "target"
    target.mkdir(parents=True, exist_ok=True)
    nodes = {
        f"model.cheese.{name}": {"resource_type": "model", "name": name, "schema": schema}
        for name, schema in models.items()
    }
    (target / "manifest.json").write_text(json.dumps({"nodes": nodes}))
    (target / "semantic_manifest.json").write_text(
        json.dumps({"metrics": [{"name": m} for m in metrics]})
    )


def test_is_dbt_project(tmp_path: Path) -> None:
    assert not engine.is_dbt_project(tmp_path)
    (tmp_path / "dbt_project.yml").write_text("name: x\n")
    assert engine.is_dbt_project(tmp_path)


def test_warehouse_path(tmp_path: Path) -> None:
    assert engine.warehouse_path(tmp_path) == tmp_path / "warehouse.duckdb"


def test_ensure_available_reports_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _exe: None)
    with pytest.raises(engine.EngineError, match="not found on PATH"):
        engine.ensure_available()


def test_models_in_schemas_filters_by_layer(tmp_path: Path) -> None:
    _write_artifacts(
        tmp_path,
        models={"stg_cheese": "staging", "fct_cheese": "marts", "dim_country": "marts"},
        metrics=[],
    )
    models = engine._models_in_schemas(tmp_path, ["marts"])
    assert sorted(models) == ["dim_country", "fct_cheese"]


def test_metric_names(tmp_path: Path) -> None:
    _write_artifacts(tmp_path, models={}, metrics=["total_production", "avg_production"])
    assert engine.metric_names(tmp_path) == ["total_production", "avg_production"]


def test_introspect_no_models_in_exposed_schema_is_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine, "parse", lambda p: None)
    _write_artifacts(tmp_path, models={"stg_cheese": "staging"}, metrics=["total_production"])
    with pytest.raises(engine.EngineError, match="No models found in exposed schema"):
        engine.introspect(tmp_path, ["marts"])


def test_introspect_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, "parse", lambda p: None)
    monkeypatch.setattr(engine, "_validate_configs", lambda p: [])
    _write_artifacts(
        tmp_path,
        models={"fct_cheese": "marts", "dim_country": "marts"},
        metrics=["total_production"],
    )
    health = engine.introspect(tmp_path, ["marts"])
    assert health.model_count == 2
    assert health.metric_count == 1
    assert health.unavailable_count == 0
    assert health.metrics == ["total_production"]


def test_introspect_degraded_counts_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine, "parse", lambda p: None)
    monkeypatch.setattr(
        engine,
        "_validate_configs",
        lambda p: [engine.Issue(severity="degraded", message="metric x unsatisfiable")],
    )
    _write_artifacts(tmp_path, models={"fct_cheese": "marts"}, metrics=["x"])
    health = engine.introspect(tmp_path, ["marts"])
    assert health.unavailable_count == 1
    assert health.issues[0].severity == "degraded"


# --- Vocabulary discovery + run-path parsing ------------------------------


def test_dimensions_parses_bullet_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, "ensure_available", lambda: None)
    stdout = (
        "✔ 🌱 We've found 4 common dimensions for metrics ['total_production'].\n"
        "• cheese_record__country\n"
        "• cheese_record__product\n"
        "• cheese_record__production_date\n"
        "• metric_time\n"
    )
    monkeypatch.setattr(engine, "_run", lambda args, project_dir: _completed(stdout))
    assert engine.dimensions(tmp_path, "total_production") == [
        "cheese_record__country",
        "cheese_record__product",
        "cheese_record__production_date",
        "metric_time",
    ]


def test_dimensions_fatal_on_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, "ensure_available", lambda: None)
    monkeypatch.setattr(engine, "_run", lambda args, project_dir: _completed("boom", returncode=1))
    with pytest.raises(engine.EngineError, match="mf list dimensions"):
        engine.dimensions(tmp_path, "total_production")


def test_dimension_types_reads_kind_and_grain(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "semantic_manifest.json").write_text(
        json.dumps(
            {
                "semantic_models": [
                    {
                        "defaults": {"agg_time_dimension": "production_date"},
                        "dimensions": [
                            {"name": "country", "type": "categorical"},
                            {
                                "name": "production_date",
                                "type": "time",
                                "type_params": {"time_granularity": "day"},
                            },
                        ],
                    }
                ]
            }
        )
    )
    types = engine.dimension_types(tmp_path)
    assert types["country"].kind == "categorical"
    assert types["production_date"].kind == "time"
    assert types["production_date"].grain == "day"
    # metric_time is synthetic, with the agg-time dimension's grain.
    assert types["metric_time"].kind == "time"
    assert types["metric_time"].grain == "day"


def test_query_sql_extracts_after_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, "ensure_available", lambda: None)
    stdout = (
        "✔ Success 🦄 - query completed after 0.02 seconds\n"
        "🔎 SQL (remove --explain to see data or add --show-dataflow-plan ...):\n"
        "\n"
        "SELECT\n  country AS cheese_record__country\nFROM marts.fct_cheese_production\n"
    )
    monkeypatch.setattr(engine, "_run", lambda args, project_dir: _completed(stdout))
    sql = engine._query_sql(tmp_path, ["query", "--metrics", "total_production"])
    assert sql.startswith("SELECT")
    assert "FROM marts.fct_cheese_production" in sql
    assert "Success" not in sql


# --- classification reads (the guard's inputs) ----------------------------


def test_classifications_reads_meta(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "manifest.json").write_text(
        json.dumps(
            {
                "nodes": {
                    "model.cheese.fct": {
                        "resource_type": "model",
                        "name": "fct",
                        "config": {"meta": {"classification": "open"}},
                    },
                    "model.cheese.stg": {
                        "resource_type": "model",
                        "name": "stg",
                        "config": {"meta": {}},
                        "meta": {},
                    },
                }
            }
        )
    )
    classes = engine.classifications(tmp_path)
    assert classes["fct"] == "open"
    assert classes["stg"] is None  # unclassified


def test_metric_source_models_traces_measure_to_model(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "semantic_manifest.json").write_text(
        json.dumps(
            {
                "semantic_models": [
                    {
                        "node_relation": {"alias": "fct_cheese_production"},
                        "measures": [{"name": "production_tonnes"}],
                    }
                ],
                "metrics": [
                    {
                        "name": "total_production",
                        "type_params": {
                            "measure": {"name": "production_tonnes"},
                            "input_measures": [{"name": "production_tonnes"}],
                        },
                    }
                ],
            }
        )
    )
    assert engine.metric_source_models(tmp_path) == {"total_production": ["fct_cheese_production"]}
