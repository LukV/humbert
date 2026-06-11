"""The state every route shares, injected via :mod:`humbert.server.deps`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from humbert.config import Config


@dataclass(slots=True)
class AppState:
    """What ``create_app`` was given, reachable from any route as ``StateDep``."""

    config: Config
    dist: Path

    def active_project(self) -> tuple[str, Path] | None:
        """The active connection's (name, dbt project dir), or None if unset."""
        connection = self.config.active
        if connection is None or self.config.active_connection is None:
            return None
        return self.config.active_connection, Path(connection.project_dir)
