"""The dbt + MetricFlow seam — the *only* module that names dbt or ``mf``.

Everything above speaks Humbert's own terms (``Health``, ``Issue``, metric
names). We depend on the dbt/``mf`` *binaries* (via subprocess), never their
Python API, so the exit strategy in the ADR is a localised change here: swap
these subprocess calls, keep the rest of Humbert untouched.

The functions read dbt's generated artifacts (`target/manifest.json`,
`target/semantic_manifest.json`) for structured introspection, and run
`mf validate-configs` for the fatal/degraded sort.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Severity = Literal["fatal", "degraded"]


class EngineError(Exception):
    """A fatal problem attaching, building, or parsing a dbt project."""


@dataclass
class Issue:
    severity: Severity
    message: str
    metric: str | None = None


@dataclass
class Health:
    """What `connect` learned about a project. Recorded on the connection."""

    model_count: int
    metric_count: int
    unavailable_count: int
    metrics: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


def is_dbt_project(path: Path) -> bool:
    return (path / "dbt_project.yml").is_file()


def warehouse_path(project_dir: Path) -> Path:
    """By convention the example writes its DuckDB file here."""
    return project_dir / "warehouse.duckdb"


def ensure_available() -> None:
    """The engine shells out to dbt + mf; fail clearly if they're absent."""
    missing = [exe for exe in ("dbt", "mf") if shutil.which(exe) is None]
    if missing:
        raise EngineError(
            f"{', '.join(missing)} not found on PATH. "
            "Install the dbt engine with `uv sync --extra dbt`."
        )


def _run(args: list[str], project_dir: Path) -> subprocess.CompletedProcess[str]:
    # mf (and dbt without explicit flags) look up profiles via DBT_PROFILES_DIR;
    # the example keeps profiles.yml in the project dir, so point there.
    env = {**os.environ, "DBT_PROFILES_DIR": str(project_dir)}
    return subprocess.run(
        args,
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _dbt(args: list[str], project_dir: Path) -> subprocess.CompletedProcess[str]:
    # Self-contained: project and profiles both live in the project dir.
    return _run(
        ["dbt", *args, "--project-dir", str(project_dir), "--profiles-dir", str(project_dir)],
        project_dir,
    )


def build(project_dir: Path) -> None:
    """``dbt deps`` then ``dbt build`` (seeds + models + tests). Fatal on failure."""
    ensure_available()
    deps = _dbt(["deps"], project_dir)
    if deps.returncode != 0:
        raise EngineError(f"`dbt deps` failed:\n{deps.stdout}\n{deps.stderr}".strip())
    built = _dbt(["build"], project_dir)
    if built.returncode != 0:
        raise EngineError(f"`dbt build` failed:\n{built.stdout}\n{built.stderr}".strip())


def parse(project_dir: Path) -> None:
    """``dbt parse`` — produces the manifests. Fatal on failure."""
    ensure_available()
    result = _dbt(["parse"], project_dir)
    if result.returncode != 0:
        raise EngineError(f"`dbt parse` failed:\n{result.stdout}\n{result.stderr}".strip())


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise EngineError(f"Expected dbt artifact not found: {path}. Did the build run?")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise EngineError(f"Malformed dbt artifact: {path}")
    return data


def _models_in_schemas(project_dir: Path, exposed_schemas: list[str]) -> list[str]:
    """Model names whose materialised schema is one of the exposed layers."""
    manifest = _read_json(project_dir / "target" / "manifest.json")
    nodes = manifest.get("nodes", {})
    wanted = {s.lower() for s in exposed_schemas}
    models: list[str] = []
    if isinstance(nodes, dict):
        for node in nodes.values():
            if not isinstance(node, dict):
                continue
            if node.get("resource_type") != "model":
                continue
            schema = str(node.get("schema", "")).lower()
            if schema in wanted:
                name = node.get("name")
                if isinstance(name, str):
                    models.append(name)
    return models


def _metric_names(project_dir: Path) -> list[str]:
    manifest = _read_json(project_dir / "target" / "semantic_manifest.json")
    metrics = manifest.get("metrics", [])
    names: list[str] = []
    if isinstance(metrics, list):
        for metric in metrics:
            if isinstance(metric, dict) and isinstance(metric.get("name"), str):
                names.append(metric["name"])
    return names


def _validate_configs(project_dir: Path) -> list[Issue]:
    """Run ``mf validate-configs``; nonzero exit becomes a degraded issue.

    The project has already parsed by this point, so a validate-configs failure
    is degraded (some metric is unsatisfiable), not fatal. Per-metric attribution
    is best-effort — see the pitch's validation-pass-fidelity risk.
    """
    result = _run(["mf", "validate-configs"], project_dir)
    if result.returncode == 0:
        return []
    message = (result.stdout + "\n" + result.stderr).strip()
    return [Issue(severity="degraded", message=message)]


def introspect(project_dir: Path, exposed_schemas: list[str]) -> Health:
    """The validation pass: parse, read artifacts, sort issues fatal vs degraded."""
    parse(project_dir)  # fatal on parse failure

    models = _models_in_schemas(project_dir, exposed_schemas)
    if not models:
        # The "IM renamed/removed the exposed layer" case — fatal, with direction.
        raise EngineError(
            f"No models found in exposed schema(s) {exposed_schemas}. "
            "Did the marts layer get renamed? Re-run `connect --schema <layer>`."
        )

    metrics = _metric_names(project_dir)
    issues = _validate_configs(project_dir)
    unavailable = sum(1 for issue in issues if issue.severity == "degraded")

    return Health(
        model_count=len(models),
        metric_count=len(metrics),
        unavailable_count=unavailable,
        metrics=metrics,
        issues=issues,
    )
