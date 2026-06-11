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
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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


def _read_yaml(path: Path) -> dict[str, object]:
    """Best-effort YAML read; ``{}`` if the file is missing or isn't a mapping."""
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def warehouse_path(project_dir: Path) -> Path:
    """The DuckDB file the dbt build writes, resolved from the pack's profile.

    profiles.yml owns the warehouse location (`outputs.<target>.path`), so we read
    it from there rather than assuming a filename — a pack scaffolded by `dbt init`
    writes `dev.duckdb`, the examples write `warehouse.duckdb`, others may differ.
    The profile is chosen by `dbt_project.yml`'s `profile:` key; the target by the
    profile's `target:` (or the sole output if there's just one). Relative paths
    resolve against the project dir, where the engine runs dbt. Falls back to the
    conventional `warehouse.duckdb` when the profile can't be read.
    """
    fallback = project_dir / "warehouse.duckdb"

    profile_name = _read_yaml(project_dir / "dbt_project.yml").get("profile")
    if not isinstance(profile_name, str):
        return fallback
    profile = _read_yaml(project_dir / "profiles.yml").get(profile_name)
    if not isinstance(profile, dict):
        return fallback

    outputs = profile.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        return fallback
    target = profile.get("target")
    output = outputs.get(target) if isinstance(target, str) else None
    if not isinstance(output, dict):
        # No usable target: a single-output profile has only one answer.
        if len(outputs) != 1:
            return fallback
        output = next(iter(outputs.values()))

    path = output.get("path") if isinstance(output, dict) else None
    if not isinstance(path, str) or not path:
        return fallback
    resolved = Path(path).expanduser()
    return resolved if resolved.is_absolute() else project_dir / resolved


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


# --- dbt artifacts ----------------------------------------------------------
#
# The slices of dbt's generated JSON the engine reads, as Pydantic models with
# everything else ignored — the shape assumptions are explicit, and the readers
# below stay a few lines each. Parsed artifacts are cached by mtime: a single
# vocabulary build consults the same manifest several times, and the files grow
# to megabytes on real projects.


class _ManifestNode(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    resource_type: str = ""
    name: str = ""
    schema_name: str = Field(default="", alias="schema")
    config: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def classification(self) -> str | None:
        # dbt puts model meta under config.meta; the top-level key is the
        # older layout — read both so either authoring style classifies.
        meta = self.config.get("meta") or self.meta
        value = meta.get("classification") if isinstance(meta, dict) else None
        return value if isinstance(value, str) else None


class _Manifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nodes: dict[str, _ManifestNode] = Field(default_factory=dict)

    def models(self) -> list[_ManifestNode]:
        return [n for n in self.nodes.values() if n.resource_type == "model" and n.name]


class _Named(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""


class _SemanticDimension(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    type: str = ""
    type_params: dict[str, Any] | None = None

    @property
    def grain(self) -> str | None:
        value = (self.type_params or {}).get("time_granularity")
        return value if isinstance(value, str) else None


class _NodeRelation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    alias: str = ""


class _SemanticModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    defaults: dict[str, Any] | None = None
    dimensions: list[_SemanticDimension] = Field(default_factory=list)
    measures: list[_Named] = Field(default_factory=list)
    node_relation: _NodeRelation | None = None


class _MetricTypeParams(BaseModel):
    model_config = ConfigDict(extra="ignore")

    measure: _Named | None = None
    input_measures: list[_Named] = Field(default_factory=list)


class _Metric(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    type_params: _MetricTypeParams | None = None


class _SemanticManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    semantic_models: list[_SemanticModel] = Field(default_factory=list)
    metrics: list[_Metric] = Field(default_factory=list)


_artifact_cache: dict[Path, tuple[float, BaseModel]] = {}


def _load_artifact[A: BaseModel](path: Path, schema: type[A]) -> A:
    if not path.is_file():
        raise EngineError(f"Expected dbt artifact not found: {path}. Did the build run?")
    mtime = path.stat().st_mtime
    hit = _artifact_cache.get(path)
    if hit is not None and hit[0] == mtime and isinstance(hit[1], schema):
        return hit[1]
    try:
        parsed = schema.model_validate_json(path.read_text())
    except ValidationError as err:
        raise EngineError(f"Malformed dbt artifact: {path}") from err
    _artifact_cache[path] = (mtime, parsed)
    return parsed


def _manifest(project_dir: Path) -> _Manifest:
    return _load_artifact(project_dir / "target" / "manifest.json", _Manifest)


def _semantic_manifest(project_dir: Path) -> _SemanticManifest:
    return _load_artifact(project_dir / "target" / "semantic_manifest.json", _SemanticManifest)


def artifact_mtimes(project_dir: Path) -> tuple[float, float] | None:
    """The (manifest, semantic manifest) mtimes, or ``None`` before a build —
    the key the semantic module uses to know when a discovered vocabulary is
    stale. A rebuild rewrites the artifacts, so the mtimes move with the data."""
    manifest = project_dir / "target" / "manifest.json"
    semantic_manifest = project_dir / "target" / "semantic_manifest.json"
    if not (manifest.is_file() and semantic_manifest.is_file()):
        return None
    return manifest.stat().st_mtime, semantic_manifest.stat().st_mtime


def _models_in_schemas(project_dir: Path, exposed_schemas: list[str]) -> list[str]:
    """Model names whose materialised schema is one of the exposed layers."""
    wanted = {s.lower() for s in exposed_schemas}
    return [n.name for n in _manifest(project_dir).models() if n.schema_name.lower() in wanted]


def metric_names(project_dir: Path) -> list[str]:
    return [m.name for m in _semantic_manifest(project_dir).metrics if m.name]


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
    out: dict[str, DimensionMeta] = {}
    agg_grain: str | None = None
    for model in _semantic_manifest(project_dir).semantic_models:
        agg_time = (model.defaults or {}).get("agg_time_dimension")
        for dim in model.dimensions:
            if not dim.name:
                continue
            kind: DimensionKind = "time" if dim.type == "time" else "categorical"
            grain = dim.grain if kind == "time" else None
            out[dim.name] = DimensionMeta(kind=kind, grain=grain)
            if dim.name == agg_time:
                agg_grain = grain
    out["metric_time"] = DimensionMeta(kind="time", grain=agg_grain)
    return out


# --- Classification — the public-only guard's inputs ----------------------
#
# The guard's *policy* (default-deny) lives in the semantic module. Here we only
# read the facts: each model's `meta.classification`, and which model(s) a metric
# reads (so the policy can ask "are they all open?").


def classifications(project_dir: Path) -> dict[str, str | None]:
    """Each model's ``meta.classification`` (``None`` when unset)."""
    return {n.name: n.classification for n in _manifest(project_dir).models()}


def metric_source_models(project_dir: Path) -> dict[str, list[str]]:
    """Each metric's underlying dbt model(s), traced measure → semantic model.

    A metric reads measures; each measure belongs to a semantic model whose
    ``node_relation`` names the dbt model it's built on. That model carries the
    classification the guard checks.
    """
    manifest = _semantic_manifest(project_dir)
    measure_to_model = {
        measure.name: model.node_relation.alias
        for model in manifest.semantic_models
        if model.node_relation is not None and model.node_relation.alias
        for measure in model.measures
        if measure.name
    }

    out: dict[str, list[str]] = {}
    for metric in manifest.metrics:
        if not metric.name:
            continue
        params = metric.type_params or _MetricTypeParams()
        measures = {m.name for m in params.input_measures if m.name}
        if params.measure is not None and params.measure.name:
            measures.add(params.measure.name)
        out[metric.name] = sorted({measure_to_model[m] for m in measures if m in measure_to_model})
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
    rows (mf writes a file), ``--explain`` for the SQL. They run in series, not
    concurrently — both open the DuckDB warehouse, and DuckDB allows one
    writing process at a time (a concurrent pair fails on the file lock).
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
