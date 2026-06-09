"""CLI surface — init, status, --version — via Typer's test runner."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from humbert import __version__, config, orchestrator, semantic
from humbert.cli import app

runner = CliRunner()


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUMBERT_HOME", str(tmp_path))
    return tmp_path


def _activate(project_dir: str = "/x/cheese") -> None:
    cfg = config.Config()
    cfg.connections["cheese"] = config.Connection(project_dir=project_dir)
    cfg.active_connection = "cheese"
    config.save_config(cfg)


def _cheese_vocab() -> semantic.Vocabulary:
    return semantic.Vocabulary(
        metrics=[
            semantic.MetricInfo(
                name="total_production",
                dimensions=[semantic.DimensionInfo("cheese_record__country", "categorical")],
            )
        ]
    )


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


# --- vocab / query --------------------------------------------------------


def test_vocab_without_connection(home: Path) -> None:
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["vocab"])
    assert result.exit_code == 1
    assert "No active connection" in result.stderr


def test_vocab_lists_metrics_and_dimensions(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate()
    monkeypatch.setattr(semantic, "load_pack", lambda p: semantic.Pack(_cheese_vocab()))
    result = runner.invoke(app, ["vocab"])
    assert result.exit_code == 0
    assert "total_production" in result.stdout
    assert "cheese_record__country" in result.stdout


def test_vocab_reports_withheld(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate()
    monkeypatch.setattr(
        semantic,
        "load_pack",
        lambda p: semantic.Pack(
            _cheese_vocab(),
            withheld=[semantic.Withheld("secret_metric", "reads non-open model(s): fct_secret")],
        ),
    )
    result = runner.invoke(app, ["vocab"])
    assert result.exit_code == 0
    assert "Withheld by the public-only guard (1)" in result.stdout
    assert "secret_metric" in result.stdout


def test_query_reports_unresolved(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate()
    monkeypatch.setattr(semantic, "discover_vocabulary", lambda p: _cheese_vocab())
    result = runner.invoke(app, ["query", "--metric", "visitors"])
    assert result.exit_code == 1
    assert "did not resolve" in result.stderr
    assert "visitors" in result.stderr


def test_query_runs_and_prints_rows(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate()
    monkeypatch.setattr(semantic, "discover_vocabulary", lambda p: _cheese_vocab())
    monkeypatch.setattr(
        semantic,
        "run",
        lambda resolved, vocab, project: semantic.Result(
            columns=["cheese_record__country", "total_production"],
            rows=[["Germany", "97767016.0"]],
            compiled_sql="SELECT 1",
        ),
    )
    result = runner.invoke(
        app, ["query", "-m", "total_production", "--by", "cheese_record__country", "--sql"]
    )
    assert result.exit_code == 0
    assert "Germany" in result.stdout
    assert "SELECT 1" in result.stdout


# --- ask (the two-call loop, model + run stubbed) -------------------------


def _stub_ask_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wire ask's dependencies so the CLI test never needs a key or a model."""
    monkeypatch.setattr(semantic, "discover_vocabulary", lambda p: _cheese_vocab())
    monkeypatch.setattr(orchestrator, "build_model", lambda llm: object())


def test_ask_prints_narrative_reading_and_sql(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate()
    _stub_ask_deps(monkeypatch)
    answer = orchestrator.Answer(
        question="q",
        reading="read cheese as total_production, by country",
        selection=semantic.Selection(metrics=["total_production"]),
        columns=["cheese_record__country", "total_production"],
        rows=[["Germany", "100"]],
        compiled_sql="SELECT 1",
        narrative="Germany produces the most cheese.",
        certainty="high",
    )
    monkeypatch.setattr(orchestrator, "ask", lambda *a, **k: answer)

    result = runner.invoke(app, ["ask", "which countries produce the most cheese?"])
    assert result.exit_code == 0
    assert "Germany produces the most cheese." in result.stdout
    assert "reading: read cheese as total_production" in result.stdout
    assert "tier 1 · certainty high" in result.stdout
    assert "SELECT 1" in result.stdout  # SQL shown by default


def test_ask_no_sql_hides_query(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate()
    _stub_ask_deps(monkeypatch)
    answer = orchestrator.Answer(
        question="q",
        reading="r",
        selection=semantic.Selection(metrics=["total_production"]),
        columns=["c"],
        rows=[["x"]],
        compiled_sql="SELECT secret",
        narrative="n",
    )
    monkeypatch.setattr(orchestrator, "ask", lambda *a, **k: answer)

    result = runner.invoke(app, ["ask", "q", "--no-sql"])
    assert result.exit_code == 0
    assert "SELECT secret" not in result.stdout


def test_ask_no_tier1_stops_plainly(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate()
    _stub_ask_deps(monkeypatch)
    monkeypatch.setattr(
        orchestrator,
        "ask",
        lambda *a, **k: orchestrator.NoTier1Answer(
            question="q", reading="read visitors", problems=['unknown metric "visitors"']
        ),
    )
    result = runner.invoke(app, ["ask", "how many visitors?"])
    assert result.exit_code == 1
    assert "Couldn't map that to a defined metric" in result.stdout
    assert "visitors" in result.stdout


def test_ask_without_connection(home: Path) -> None:
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["ask", "anything"])
    assert result.exit_code == 1
    assert "No active connection" in result.stderr
