"""CLI surface — init, status, --version — via Typer's test runner."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from humbert import __version__, config
from humbert.cli import app

runner = CliRunner()


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUMBERT_HOME", str(tmp_path))
    return tmp_path


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_init_creates_config_and_cache(home: Path) -> None:
    result = runner.invoke(app, ["init", "cheese"])
    assert result.exit_code == 0
    assert (home / "config.json").exists()
    assert (home / "projects" / "cheese").is_dir()


def test_init_is_idempotent(home: Path) -> None:
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["init"]).exit_code == 0


def test_status_without_connection(home: Path) -> None:
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "No active connection" in result.stdout
    assert "humbert" in result.stdout  # the skin


def test_status_with_connection(home: Path) -> None:
    cfg = config.Config()
    cfg.connections["cheese"] = config.Connection(
        project_dir="./examples/cheese",
        warehouse_path="./examples/cheese/warehouse.duckdb",
        built_at="2026-06-07 14:02",
        model_count=4,
        metric_count=2,
        unavailable_count=0,
    )
    cfg.active_connection = "cheese"
    config.save_config(cfg)

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Connection:  cheese" in result.stdout
    assert "2 metrics" in result.stdout
    assert "0 unavailable" in result.stdout
    assert "warehouse.duckdb" in result.stdout
