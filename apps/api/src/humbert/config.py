"""Persistence and configuration for ``~/.humbert/``.

One global ``config.json`` holds connections (each a dbt project), the active
connection, the LLM config, and settings. Per-connection caches live under
``projects/<name>/``. The base directory is ``~/.humbert/`` on POSIX and
``%LOCALAPPDATA%\\humbert`` on Windows; set ``HUMBERT_HOME`` to override it
(used by the tests).

See docs/architecture/001-stack-decisions.md for the layout.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Locale = Literal["en", "nl"]


def humbert_home() -> Path:
    """The base directory for all Humbert state."""
    override = os.environ.get("HUMBERT_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "humbert"
    return Path.home() / ".humbert"


def config_path() -> Path:
    return humbert_home() / "config.json"


def project_dir(name: str) -> Path:
    return humbert_home() / "projects" / name


class Settings(BaseModel):
    max_result_rows: int = 1000
    statement_timeout_seconds: int = 30
    theme: str = "humbert"
    # The app name is branding that travels with the skin, but is config, not a token.
    app_name: str = "Humbert"
    locale: Locale = "en"
    telemetry_enabled: bool = True
    # The empty-state chips — one per chart shape for the bundled cheese source.
    # Static for v0; vocabulary-derived suggestions are a later refinement.
    suggestions: list[str] = Field(
        default_factory=lambda: [
            "Which countries produce the most cheese?",
            "How has cheese production evolved over the years?",
            "How much cheese did Germany produce in 2020?",
            "Do countries that make more cheese also make more kinds of it?",
        ]
    )


class LLM(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-opus-4-8"
    api_key_env: str = "ANTHROPIC_API_KEY"


class Connection(BaseModel):
    """A dbt + MetricFlow source Humbert is attached to."""

    type: Literal["dbt"] = "dbt"
    project_dir: str
    active_pack: str | None = None
    # The dbt layer(s) Tier 2 may query and that introspection surfaces.
    exposed_schemas: list[str] = Field(default_factory=lambda: ["marts"])
    warehouse_path: str | None = None
    built_at: str | None = None
    # Health summary recorded by `connect`'s validation pass, shown by `status`.
    model_count: int | None = None
    metric_count: int | None = None
    unavailable_count: int | None = None
    # Metrics the public-only guard refused to expose (not classified `open`).
    withheld_count: int | None = None


class Config(BaseModel):
    connections: dict[str, Connection] = Field(default_factory=dict)
    active_connection: str | None = None
    llm: LLM = Field(default_factory=LLM)
    settings: Settings = Field(default_factory=Settings)

    @property
    def active(self) -> Connection | None:
        if self.active_connection is None:
            return None
        return self.connections.get(self.active_connection)


def load_config() -> Config:
    """Load ``config.json``, or return defaults if it does not exist yet."""
    path = config_path()
    if not path.exists():
        return Config()
    return Config.model_validate_json(path.read_text())


def save_config(config: Config) -> None:
    """Write ``config.json``, creating the home directory if needed."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2) + "\n")
