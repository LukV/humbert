"""`connect` orchestration, with the engine faked so no real dbt run is needed.

The engine's own subprocess calls are exercised manually against examples/cheese
once the seed exists — see the pitch. Here we verify the command's logic:
fatal vs success, recording, active-connection, and the --build / staleness path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from humbert import config, engine, semantic
from humbert.cli import app

runner = CliRunner()


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUMBERT_HOME", str(tmp_path / "home"))
    return tmp_path


def _all_open(monkeypatch: pytest.MonkeyPatch, *metrics: str) -> None:
    """Stub the guard so every metric is exposed (nothing withheld)."""
    monkeypatch.setattr(semantic, "classify_metrics", lambda p: (list(metrics), []))


def _make_dbt_project(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "dbt_project.yml").write_text("name: cheese\n")
    return path


def test_connect_rejects_non_dbt_dir(home: Path) -> None:
    plain = home / "not_dbt"
    plain.mkdir()
    result = runner.invoke(app, ["connect", str(plain)])
    assert result.exit_code == 1
    assert "not a dbt project" in result.stderr


def test_connect_records_and_activates(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _make_dbt_project(home / "cheese")
    built: list[Path] = []
    monkeypatch.setattr(engine, "build", lambda p: built.append(p))
    monkeypatch.setattr(
        engine,
        "introspect",
        lambda p, schemas: engine.Health(
            model_count=4, metric_count=2, unavailable_count=0, metrics=["total_production"]
        ),
    )
    _all_open(monkeypatch, "total_production")

    result = runner.invoke(app, ["connect", str(project), "--schema", "marts,gold"])
    assert result.exit_code == 0, result.stderr
    assert built == [project]  # warehouse missing → built

    cfg = config.load_config()
    assert cfg.active_connection == "cheese"
    conn = cfg.active
    assert conn is not None
    assert conn.project_dir == str(project)
    assert conn.exposed_schemas == ["marts", "gold"]
    assert conn.metric_count == 2
    assert conn.withheld_count == 0


def test_connect_skips_build_when_warehouse_exists(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _make_dbt_project(home / "cheese")
    (project / "warehouse.duckdb").write_text("")  # pretend it's built
    built: list[Path] = []
    monkeypatch.setattr(engine, "build", lambda p: built.append(p))
    monkeypatch.setattr(
        engine,
        "introspect",
        lambda p, schemas: engine.Health(4, 2, 0, ["total_production"]),
    )
    _all_open(monkeypatch, "total_production")

    result = runner.invoke(app, ["connect", str(project)])
    assert result.exit_code == 0, result.stderr
    assert built == []  # warehouse present, no --build → skipped


def test_connect_build_flag_forces_rebuild(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _make_dbt_project(home / "cheese")
    (project / "warehouse.duckdb").write_text("")
    built: list[Path] = []
    monkeypatch.setattr(engine, "build", lambda p: built.append(p))
    monkeypatch.setattr(engine, "introspect", lambda p, schemas: engine.Health(4, 2, 0))
    _all_open(monkeypatch, "total_production")

    result = runner.invoke(app, ["connect", str(project), "--build"])
    assert result.exit_code == 0, result.stderr
    assert built == [project]


def test_connect_surfaces_fatal_engine_error(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _make_dbt_project(home / "cheese")

    def boom(p: Path, schemas: list[str]) -> engine.Health:
        raise engine.EngineError("No models found in exposed schema(s) ['marts'].")

    monkeypatch.setattr(engine, "build", lambda p: None)
    monkeypatch.setattr(engine, "introspect", boom)

    result = runner.invoke(app, ["connect", str(project)])
    assert result.exit_code == 1
    assert "No models found" in result.stderr
    # Nothing recorded on failure.
    assert config.load_config().active_connection is None


def test_connect_records_withheld_metrics(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _make_dbt_project(home / "cheese")
    monkeypatch.setattr(engine, "build", lambda p: None)
    monkeypatch.setattr(engine, "introspect", lambda p, schemas: engine.Health(4, 1, 0))
    monkeypatch.setattr(
        semantic,
        "classify_metrics",
        lambda p: ([], [semantic.Withheld("total_production", "reads non-open model(s): fct")]),
    )

    result = runner.invoke(app, ["connect", str(project)])
    assert result.exit_code == 0, result.stderr
    assert "1 withheld" in result.stdout
    assert "All metrics withheld" in result.stdout
    conn = config.load_config().active
    assert conn is not None
    assert conn.withheld_count == 1
