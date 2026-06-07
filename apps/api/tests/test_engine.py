"""Engine helpers — artifact reading and the introspect sort.

The subprocess parts (`parse`, `mf validate-configs`) are stubbed; the manifest
readers and the fatal/degraded logic are real.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from humbert import engine


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
    assert engine._metric_names(tmp_path) == ["total_production", "avg_production"]


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
