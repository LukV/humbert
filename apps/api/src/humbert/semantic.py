"""The semantic-layer module — the deterministic Tier-1 core.

Sits *above* the engine seam (engine owns every dbt/``mf`` call; this module
never names dbt). It speaks Humbert's own terms:

- ``Vocabulary`` — what metrics and dimensions exist, the "what can I ask?".
- ``Selection`` — the reproducible IR of a question (the unit block 2 freezes).
- ``resolve`` — propose-then-validate: exact-name check against the vocabulary,
  returning a ``ResolvedSelection`` or a structured ``Unresolved`` that names the
  gap (never an exception, never a refusal).
- ``run`` — compile a resolved selection and run it, returning rows + the
  compiled SQL.

No LLM, no Tier-2 fallback, no refusal typing — those are later blocks. Unknown
names fall through as data the caller can act on.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field, TypeAdapter

from humbert import engine


@dataclass
class DimensionInfo:
    """A dimension you can group or filter by, in MetricFlow dunder form."""

    name: str
    kind: engine.DimensionKind
    grain: str | None = None


@dataclass
class MetricInfo:
    name: str
    dimensions: list[DimensionInfo] = field(default_factory=list)


@dataclass
class Vocabulary:
    """What the connected source exposes. The 'what can I ask?' surface."""

    metrics: list[MetricInfo] = field(default_factory=list)

    def metric(self, name: str) -> MetricInfo | None:
        return next((m for m in self.metrics if m.name == name), None)

    def metric_names(self) -> set[str]:
        return {m.name for m in self.metrics}

    def common_dimensions(self, metric_names: list[str]) -> set[str]:
        """Dimension names available to *every* listed metric (MetricFlow's rule)."""
        sets = [
            {d.name for d in m.dimensions}
            for name in metric_names
            if (m := self.metric(name)) is not None
        ]
        if not sets:
            return set()
        return set.intersection(*sets)

    def is_time_dimension(self, name: str) -> bool:
        for m in self.metrics:
            for d in m.dimensions:
                if d.name == name:
                    return d.kind == "time"
        return False


class Selection(BaseModel):
    """The reproducible Tier-1 representation of a question.

    The core is ``metrics + group_by + where``; ``order_by / limit / time_grain``
    are thin pass-throughs to ``mf query`` flags. This is the object block 2
    freezes into a validated cell, so it is intentionally serialisable.
    """

    metrics: list[str]
    group_by: list[str] = Field(default_factory=list)
    where: list[str] = Field(default_factory=list)
    order_by: list[str] = Field(default_factory=list)
    limit: int | None = None
    time_grain: str | None = None


@dataclass
class ResolvedSelection:
    """A selection whose names all matched the vocabulary. Safe to compile."""

    selection: Selection


@dataclass
class Unresolved:
    """One or more names that didn't match the vocabulary, each named.

    Not an exception and not a refusal — data the caller acts on. Block 3 turns
    this into a typed refusal; for now it's reported as-is.
    """

    problems: list[str] = field(default_factory=list)


@dataclass
class Result:
    columns: list[str]
    rows: list[list[str]]
    compiled_sql: str


@dataclass
class Withheld:
    """A metric the public-only guard refused to expose, and why."""

    metric: str
    reason: str


@dataclass
class Pack:
    """The loaded pack: the exposed vocabulary plus what the guard withheld."""

    vocabulary: Vocabulary
    withheld: list[Withheld] = field(default_factory=list)


def classify_metrics(project_dir: Path) -> tuple[list[str], list[Withheld]]:
    """The public-only guard: split metrics into exposed vs withheld.

    Default-deny — a metric is exposed only if *every* model it reads is
    classified ``open``. An unclassified model counts as not-open, so forgetting
    to classify hides data rather than leaking it. A metric whose source model
    can't be resolved is withheld too: we can't confirm it's open.
    """
    classes = engine.classifications(project_dir)
    metric_models = engine.metric_source_models(project_dir)
    exposed: list[str] = []
    withheld: list[Withheld] = []
    for name in engine.metric_names(project_dir):
        models = metric_models.get(name) or []
        not_open = [m for m in models if classes.get(m) != "open"]
        if not models:
            withheld.append(
                Withheld(name, "no source model resolved — cannot confirm classification")
            )
        elif not_open:
            withheld.append(Withheld(name, f"reads non-open model(s): {', '.join(not_open)}"))
        else:
            exposed.append(name)
    return exposed, withheld


def load_pack(project_dir: Path) -> Pack:
    """Load the connected dbt project as a classified pack.

    Only ``open`` metrics make it into the vocabulary; the rest are recorded as
    withheld. Every downstream consumer (``vocab``, ``query``, block 2's tiers)
    reads the vocabulary and so inherits the guard for free.

    Discovery shells out to ``mf`` once per metric — seconds each — so the
    result is cached on disk in the project's ``target/``, keyed on the dbt
    artifacts' mtimes. A rebuild (``connect --build``, ``dbt build``) moves the
    key and the next load rediscovers; everything else reads the cache,
    including a fresh CLI process.
    """
    key = engine.artifact_mtimes(project_dir)
    if key is not None:
        cached = _read_pack_cache(project_dir, key)
        if cached is not None:
            return cached
    pack = _discover_pack(project_dir)
    if key is not None:
        _write_pack_cache(project_dir, key, pack)
    return pack


def _discover_pack(project_dir: Path) -> Pack:
    """The real discovery: classify every metric, list each one's dimensions."""
    types = engine.dimension_types(project_dir)
    exposed, withheld = classify_metrics(project_dir)
    metrics: list[MetricInfo] = []
    for name in exposed:
        dims: list[DimensionInfo] = []
        for dunder in engine.dimensions(project_dir, name):
            short = dunder.split("__")[-1]
            meta = types.get(dunder) or types.get(short)
            if meta is None:
                dims.append(DimensionInfo(name=dunder, kind="categorical"))
            else:
                dims.append(DimensionInfo(name=dunder, kind=meta.kind, grain=meta.grain))
        metrics.append(MetricInfo(name=name, dimensions=dims))
    return Pack(vocabulary=Vocabulary(metrics=metrics), withheld=withheld)


_PACK_ADAPTER: TypeAdapter[Pack] = TypeAdapter(Pack)


def _pack_cache_path(project_dir: Path) -> Path:
    return project_dir / "target" / "humbert_pack.json"


def _read_pack_cache(project_dir: Path, key: tuple[float, float]) -> Pack | None:
    """The cached pack if it matches the artifacts' mtimes; None on any miss.

    A malformed or stale cache is never an error — discovery just runs again.
    """
    try:
        raw = json.loads(_pack_cache_path(project_dir).read_text())
        if isinstance(raw, dict) and raw.get("key") == list(key):
            return _PACK_ADAPTER.validate_python(raw["pack"])
    except (OSError, ValueError, KeyError):
        pass
    return None


def _write_pack_cache(project_dir: Path, key: tuple[float, float], pack: Pack) -> None:
    try:
        payload = {"key": list(key), "pack": _PACK_ADAPTER.dump_python(pack)}
        _pack_cache_path(project_dir).write_text(json.dumps(payload, indent=2) + "\n")
    except OSError:
        pass  # the cache is an optimisation; failing to write it must not fail the load


PACK_README = """\
# Pack

This folder is a Humbert pack — the governed slice of data Humbert reads from.
The pack is the semantic model: the metrics and dimensions Humbert can answer
questions about, defined in dbt + MetricFlow.

## What's here

- `context/` — working material for whoever builds and maintains the pack:
  database dumps, data dictionaries, source notes. Humbert doesn't read this when
  answering questions; it lives here so the knowledge stays with the pack instead
  of in someone's head.

More folders join as the pack grows:

- `domain/` — the dbt semantic models, with their labels, aliases, and the
  `open` classification that decides what Humbert may expose. *(coming)*
- `introspection/` — cached schema and profiling. *(coming)*
- `tests/` — the evaluation set that keeps answers honest. *(coming)*

## Next

Add a dbt project here, then point Humbert at this folder:

    humbert connect <this-folder>
"""

CONTEXT_README = """\
# Context

Working material for whoever builds and maintains this pack. Humbert doesn't read
it when answering questions — it's here for design time.

Put anything that helps you model the data well, and remember why it's shaped the
way it is:

- database dumps and schema exports
- data dictionaries and codebooks
- source notes: where the data comes from, how it's collected, what's missing
- known pitfalls and caveats

Keep it human, and keep it close to the work. When the pack changes, update the
notes here too.
"""


def scaffold_pack(path: Path) -> list[Path]:
    """Scaffold a pack overlay at ``path``: a ``context/`` folder for design-time
    documents (db dumps, data dictionaries, source notes) and READMEs that explain
    the layout. Idempotent — existing files are left untouched, and the list of
    paths actually created is returned.
    """
    context = path / "context"
    files = {path / "README.md": PACK_README, context / "README.md": CONTEXT_README}
    created: list[Path] = []
    for directory in (path, context):
        if not directory.exists():
            directory.mkdir(parents=True)
            created.append(directory)
    for file, body in files.items():
        if not file.exists():
            file.write_text(body)
            created.append(file)
    return created


def discover_vocabulary(project_dir: Path) -> Vocabulary:
    """The exposed vocabulary — the pack with the guard already applied."""
    return load_pack(project_dir).vocabulary


def resolve(selection: Selection, vocabulary: Vocabulary) -> ResolvedSelection | Unresolved:
    """Propose-then-validate: every name checked by exact match before compiling.

    ``where`` is *not* validated — MetricFlow filter expressions are passed
    through (a malformed one surfaces later as an engine error, by design).
    All gaps are collected so the caller sees them at once.
    """
    problems: list[str] = []

    known_metrics = vocabulary.metric_names()
    for name in selection.metrics:
        if name not in known_metrics:
            problems.append(f'unknown metric "{name}"')

    # Dimensions are validated against what the *selected, known* metrics share.
    valid_metrics = [m for m in selection.metrics if m in known_metrics]
    available_dims = vocabulary.common_dimensions(valid_metrics) if valid_metrics else set()
    for dim in selection.group_by:
        if dim not in available_dims:
            scope = ", ".join(valid_metrics) or "the selection"
            problems.append(f'unknown dimension "{dim}" for {scope}')

    # Order-by items must be a queried metric or a grouped dimension.
    queryable = set(selection.metrics) | set(selection.group_by)
    for item in selection.order_by:
        bare = item[1:] if item.startswith("-") else item
        if bare not in queryable:
            problems.append(f'cannot order by "{bare}" — not a queried metric or dimension')

    if problems:
        return Unresolved(problems=problems)
    return ResolvedSelection(selection=selection)


def run(resolved: ResolvedSelection, vocabulary: Vocabulary, project_dir: Path) -> Result:
    """Compile a resolved selection and run it through the engine."""
    selection = resolved.selection
    group_by = _apply_grain(selection, vocabulary)
    out = engine.query(
        project_dir,
        metrics=selection.metrics,
        group_by=group_by,
        where=selection.where,
        order_by=selection.order_by,
        limit=selection.limit,
    )
    return Result(columns=out.columns, rows=out.rows, compiled_sql=out.compiled_sql)


def _apply_grain(selection: Selection, vocabulary: Vocabulary) -> list[str]:
    """Suffix any grouped time dimension with the requested grain (``…__year``)."""
    if not selection.time_grain:
        return selection.group_by
    grain = selection.time_grain
    return [
        f"{dim}__{grain}" if vocabulary.is_time_dimension(dim) else dim
        for dim in selection.group_by
    ]
