"""Config persistence — paths, defaults, round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from humbert import config


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HUMBERT_HOME at a temp dir for the duration of a test."""
    monkeypatch.setenv("HUMBERT_HOME", str(tmp_path))
    return tmp_path


def test_humbert_home_respects_override(home: Path) -> None:
    assert config.humbert_home() == home
    assert config.config_path() == home / "config.json"
    assert config.project_dir("cheese") == home / "projects" / "cheese"


def test_humbert_home_without_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HUMBERT_HOME", raising=False)
    home = config.humbert_home()
    # POSIX => ~/.humbert; Windows => %LOCALAPPDATA%\humbert. Either ends in humbert.
    assert home.name == "humbert" or home.name == ".humbert"


def test_load_returns_defaults_when_missing(home: Path) -> None:
    cfg = config.load_config()
    assert cfg.connections == {}
    assert cfg.active_connection is None
    assert cfg.settings.locale == "en"
    assert cfg.settings.theme == "humbert"
    assert cfg.active is None


def test_save_then_load_round_trips(home: Path) -> None:
    cfg = config.Config()
    cfg.connections["cheese"] = config.Connection(
        project_dir="./examples/cheese",
        exposed_schemas=["marts", "gold"],
        metric_count=2,
        unavailable_count=0,
    )
    cfg.active_connection = "cheese"
    cfg.settings.locale = "nl"
    config.save_config(cfg)

    assert config.config_path().exists()
    loaded = config.load_config()
    assert loaded.active_connection == "cheese"
    assert loaded.settings.locale == "nl"
    active = loaded.active
    assert active is not None
    assert active.exposed_schemas == ["marts", "gold"]
    assert active.metric_count == 2


def test_connection_defaults_to_marts(home: Path) -> None:
    conn = config.Connection(project_dir="/x")
    assert conn.exposed_schemas == ["marts"]
    assert conn.type == "dbt"


def test_save_creates_home_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "nested" / "home"
    monkeypatch.setenv("HUMBERT_HOME", str(target))
    config.save_config(config.Config())
    assert (target / "config.json").exists()
