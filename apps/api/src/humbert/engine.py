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

import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Severity = Literal["fatal", "degraded"]
DimensionKind = Literal["categorical", "time"]

# mf decorates its output with ANSI colour codes; strip them before parsing.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


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


def metric_names(project_dir: Path) -> list[str]:
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

    metrics = metric_names(project_dir)
    issues = _validate_configs(project_dir)
    unavailable = sum(1 for issue in issues if issue.severity == "degraded")

    return Health(
        model_count=len(models),
        metric_count=len(metrics),
        unavailable_count=unavailable,
        metrics=metrics,
        issues=issues,
    )


# --- Vocabulary discovery -------------------------------------------------
#
# Two reads feed the semantic module's `Vocabulary`: the authoritative list of
# dimension names per metric (from `mf list`, which knows the join graph), and
# their type/grain (from the semantic manifest, which the CLI text doesn't show).


@dataclass
class DimensionMeta:
    """A dimension's kind and (for time dimensions) its grain."""

    kind: DimensionKind
    grain: str | None = None


def dimensions(project_dir: Path, metric: str) -> list[str]:
    """Dimension names available to a metric, in MetricFlow's dunder form.

    Authoritative because ``mf`` resolves the join graph — we don't reconstruct
    it from the manifest. Parses the ``• name`` lines out of the CLI output.
    """
    ensure_available()
    result = _run(["mf", "list", "dimensions", "--metrics", metric], project_dir)
    if result.returncode != 0:
        raise EngineError(
            f"`mf list dimensions` failed for {metric}:\n{result.stdout}\n{result.stderr}".strip()
        )
    names: list[str] = []
    for raw in result.stdout.splitlines():
        line = _ANSI.sub("", raw).strip()
        if line.startswith("•"):
            name = line[1:].strip().split()[0] if line[1:].strip() else ""
            if name:
                names.append(name)
    return names


def dimension_types(project_dir: Path) -> dict[str, DimensionMeta]:
    """Map each dimension (by its short name) to its kind and grain.

    Keyed by the bare dimension name (``country``) so a dunder name
    (``cheese_record__country``) resolves by its suffix. ``metric_time`` is
    added explicitly — it's synthetic, with the grain of the agg-time dimension.
    """
    manifest = _read_json(project_dir / "target" / "semantic_manifest.json")
    out: dict[str, DimensionMeta] = {}
    agg_grain: str | None = None
    semantic_models = manifest.get("semantic_models", [])
    if isinstance(semantic_models, list):
        for model in semantic_models:
            if not isinstance(model, dict):
                continue
            agg_time = (model.get("defaults") or {}).get("agg_time_dimension")
            for dim in model.get("dimensions", []) or []:
                if not isinstance(dim, dict) or not isinstance(dim.get("name"), str):
                    continue
                kind: DimensionKind = "time" if dim.get("type") == "time" else "categorical"
                grain = None
                if kind == "time":
                    grain = (dim.get("type_params") or {}).get("time_granularity")
                out[dim["name"]] = DimensionMeta(kind=kind, grain=grain)
                if dim["name"] == agg_time:
                    agg_grain = grain
    out["metric_time"] = DimensionMeta(kind="time", grain=agg_grain)
    return out


# --- Compile + run --------------------------------------------------------


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[str]]
    compiled_sql: str


def query(
    project_dir: Path,
    *,
    metrics: list[str],
    group_by: list[str],
    where: list[str],
    order_by: list[str],
    limit: int | None,
) -> QueryResult:
    """Run a resolved selection through ``mf query`` — rows + compiled SQL.

    The caller is responsible for having validated names against the vocabulary;
    this is the mechanical compile-and-run. Two invocations: ``--csv`` for the
    rows (mf writes a file), ``--explain`` for the SQL.
    """
    ensure_available()
    flags: list[str] = ["query", "--metrics", ",".join(metrics)]
    if group_by:
        flags += ["--group-by", ",".join(group_by)]
    for expr in where:
        flags += ["--where", expr]
    if order_by:
        flags += ["--order", ",".join(order_by)]
    if limit is not None:
        flags += ["--limit", str(limit)]

    columns, rows = _query_rows(project_dir, flags)
    compiled_sql = _query_sql(project_dir, flags)
    return QueryResult(columns=columns, rows=rows, compiled_sql=compiled_sql)


def _query_rows(project_dir: Path, flags: list[str]) -> tuple[list[str], list[list[str]]]:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as handle:
        out_path = Path(handle.name)
    try:
        result = _run(["mf", *flags, "--csv", str(out_path)], project_dir)
        if result.returncode != 0:
            raise EngineError(f"`mf query` failed:\n{result.stdout}\n{result.stderr}".strip())
        with out_path.open(newline="") as fh:
            reader = csv.reader(fh)
            table = list(reader)
    finally:
        out_path.unlink(missing_ok=True)
    if not table:
        return [], []
    return table[0], table[1:]


def _query_sql(project_dir: Path, flags: list[str]) -> str:
    result = _run(["mf", *flags, "--explain"], project_dir)
    if result.returncode != 0:
        raise EngineError(f"`mf query --explain` failed:\n{result.stdout}\n{result.stderr}".strip())
    lines = [_ANSI.sub("", raw) for raw in result.stdout.splitlines()]
    for i, line in enumerate(lines):
        if "SQL" in line and "--explain" in line:
            return "\n".join(lines[i + 1 :]).strip()
    # No marker found — return the cleaned output rather than nothing.
    return "\n".join(lines).strip()
