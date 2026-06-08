---
project: humbert
type: pitch
status: shipped
block: setup
appetite: chunky
created: 2026-06-08
started: 2026-06-08
shipped_on: 2026-06-08
---
# Semantic-layer module — propose-then-validate, compile + run

## Problem

`connect` proved the dbt + MetricFlow source attaches and reported its health — *how many* metrics and models exist. But there is still no way to **ask** the source anything. The planner block 2 will build needs a vocabulary to read ("what metrics and dimensions exist?") and a way to hand back a proposed answer and have it checked before it touches the warehouse ("does this selection resolve, and what rows does it return?"). That is the semantic-layer module: the deterministic Tier-1 core the whole loop sits on, with no LLM and no UI yet. Until it exists, nothing downstream can be built, and there is no hand-runnable way to confirm a metric actually computes the right number against real data. This is product shape [[../../product-design/004-semantic-layer]] made into an in-process interface.

## Sketch

A module that sits *above* the existing `engine` seam (engine still owns every dbt/`mf` subprocess call; this module never names dbt) and speaks Humbert's own terms: a vocabulary, a selection, a result. Four pieces, plus two CLI commands to drive and validate it by hand.

### 1. Vocabulary discovery

Read the discovered metrics and, per metric, the dimensions you can group or filter by — each with its **type** (categorical / time) and, for time, its **grain** (day / month / year …). This extends `engine` with a `dimensions(metric)` read (via `mf list dimensions --metric …`, or the `semantic_manifest.json`), surfaced as a small `Vocabulary` value object: `metrics: list[MetricInfo]`, each with `name`, `dimensions: list[DimensionInfo]`. The module exposes it; the planner will later read it to know what's askable.

What `humbert vocab` prints against `examples/cheese`:

```
total_production
  cheese_record__country           categorical
  cheese_record__product           categorical
  cheese_record__production_date   time   grains: day
  metric_time                      time   grains: day
```

**Why we need it:** the floor of the module. `resolve()` has nothing to validate a selection *against* without it, and it's the only way you — or the block-2 planner — learn what's askable. Needed now and for every block after.

### 2. The `Selection` IR

A pydantic model — the reproducible Tier-1 representation of a question, the thing that later gets frozen into a validated cell:

```
Selection(
  metrics:   list[str]            # one or more defined metric names
  group_by:  list[str]            # dimension names (MetricFlow dunder form)
  where:     list[str]            # MetricFlow filter expressions
  order_by:  list[str]
  limit:     int | None
  time_grain: str | None          # applied to the time dimension
)
```

Dimension names mirror **MetricFlow's dunder convention** (`cheese_record__country`, `metric_time__year`) — we don't invent a friendlier alias layer here; that is the pack's `meta:` job later. The IR is what travels; everything else (rows, SQL) is derived from running it.

**Why we need it:** one typed object is both the thing `resolve()` validates and the thing the run-path compiles — without it those checks get re-implemented at every call site. It's also the **unit block 2 freezes into a validated cell** and re-plans on refinement ([[../../product-design/002-product-forms]]), so the shape is load-bearing downstream, not just here. The irreducible core is `metrics + group_by + where`; `order_by / limit / time_grain` are thin pass-throughs to `mf query` flags — included only because they're nearly free and the cut line's acceptance check needs `--order`. If they earn no use, drop them.

### 3. `resolve()` — propose-then-validate

Given a `Selection` and the `Vocabulary`, check every name by **exact match** before anything compiles. Resolves cleanly → a `ResolvedSelection`. A name that isn't in the vocabulary → a structured `Unresolved` that *names the gap* (`unknown metric "visitors"`, `unknown dimension "cheese_record__region" for metric total_production`) — **not** an exception and **not** a refusal. Unknown names don't become queries (block 3's concern); they fall through as data the caller can act on. No synonym matching, no fuzzy resolution — exact names only.

**Why we need it:** the named promise of the semantic layer ([[../../product-design/004-semantic-layer]]) — *propose-then-validate*. **Now** its payoff is modest: it turns an `mf` stack trace into one clean structured error a human reading `query` output can act on. Its real weight is **downstream**: it's the guardrail that stops a block-2 LLM's hallucinated metric name from ever compiling, and the structured `Unresolved` is exactly what block 3 turns into a typed refusal. This is the piece most worth scrutinising for "build now vs build with block 2" — see the KISS note in Risks.

### 4. compile + run

A `ResolvedSelection` compiles to MetricFlow query arguments and runs through the engine seam: `mf query --csv` for the rows, `mf query --explain` for the compiled SQL. Returns a `Result(rows, columns, compiled_sql)`. Nothing below the interface leaks — no warehouse handle, no raw dbt object.

**Why we need it:** without it `query` returns nothing — it's the piece that actually produces the rows and the SQL the cut line checks. The run-path (`mf query --csv` / `--explain`) is also exactly what block 2's narrator reads rows from and what a validated cell re-runs. Needed now.

### The two validation commands

So this is hand-testable before any LLM or UI exists (block 2):

- **`humbert vocab`** — print the discovered metrics and, under each, its dimensions with type and grain. The "what can I ask?" surface.
- **`humbert query --metric M [--by DIM …] [--where EXPR …] [--order …] [--limit N] [--grain G] [--sql]`** — build a `Selection` from flags, run it through the module, and print the returned rows as a table. Unknown names print the structured `Unresolved` (which name, which metric), not a traceback. `--sql` additionally prints the compiled SQL (off by default — the rows are the answer; the SQL is reached for).

Both run only with the `dbt` extra installed, like `connect`.

## Cut line

The vocabulary is exposed (`humbert vocab` lists metrics + dimensions); a hand-written `Selection` validates and runs against `examples/cheese` via `humbert query`, returning real rows plus (with `--sql`) the compiled SQL; an invalid selection reports a structured `Unresolved` naming the unknown metric or dimension. The **cheese acceptance check** passes: `humbert query --metric total_production --by cheese_record__country --order "-total_production"` ranks Germany / France / Italy / the Netherlands / Poland near the top, matching known production reality.

## Out of scope

- **The LLM planner** — turning a natural-language question into a `Selection`. That's block 2's two-call orchestration; this module is the deterministic thing the planner calls.
- **Synonym / fuzzy matching and a friendly alias layer** — exact names only. Aliases come from the pack's `meta:` (pack-scaffolding pitch).
- **Tier 2 — governed SQL fallback** — when no metric fits. Block 2.
- **Refusal typing** (`NO_VALID_METRIC`-style) — `resolve()` returns a structured `Unresolved`; turning that into a typed refusal with copy is block 3.
- **Narrative, certainty score, charts** — block 2 / block 3.
- **Any HTTP / UI surface** — validation is CLI-only here; the notebook calls the module in-process in block 2.
- **Caching the vocabulary** — read it live for now; an introspection cache is the pack-scaffolding pitch's concern.

## Risks / unknowns

- **MetricFlow dimension introspection fidelity.** `mf list dimensions --metric` must return names in the exact dunder form `mf query --group-by` accepts, with type/grain attached — or we read `semantic_manifest.json` directly. Confirm which is the reliable source (the CLI pitch already found the primary-entity dunder naming the surprising part: `cheese_record__country`, not `cheese_production__country`).
- **`mf query --explain` output shape.** Need to confirm it returns clean compiled SQL we can show, and that `--csv` rows parse predictably (header row, types). Both are the run-path's load-bearing assumptions.
- **Selection → mf-args mapping.** Filters (`--where`), ordering (`--order`), and time-grain flags must map cleanly from the IR to `mf query` flags. Where the mapping is awkward, lean on what `mf query` natively supports rather than post-processing rows in Python.
- **Test split.** Unit tests stub the engine subprocess (lean CI, no dbt) and exercise resolve/compile/IR logic; one local integration test runs the real cheese path under `--extra dbt`. Keep the boundary clean so CI never needs dbt (the deliberate choice from the CLI ship).
- **`--where` expression surface.** MetricFlow filter syntax is its own mini-language; we pass expressions through rather than parsing them. Risk: a malformed filter surfaces as an engine error, not a clean `Unresolved`. Acceptable for now — document it.
- **KISS check — are four pieces too many?** They are not four features; they are the four steps of one path: *what exists* (Vocabulary) → *what's asked* (Selection) → *does it exist?* (resolve) → *do it* (run). Drop any one and "propose-then-validate, compile + run" stops being true. The KISS risk lives **inside** pieces, not in their count: Selection's optional fields and `resolve()`'s error granularity. The minimal honest cut, if we want one, is to build `resolve()` thin now (exact-match, single structured error) and let block 2 enrich it when the LLM actually needs richer feedback — rather than dropping it, which would just push hallucinated-name handling into block 2 with no guard in between.

## Related

- [[../blocks/01-setup-and-bootstrap]] — the block; this is the third pitch, pack-scaffolding is the last.
- [[../../product-design/004-semantic-layer]] — the pack, Tier 1, propose-then-validate as product shape.
- [[../../product-design/009-orchestration]] — the plan → run → narrate contract this module's run-path serves.
- [[../../architecture/001-stack-decisions]] — the dbt-coupling seam this sits above; DuckDB engine.
- Prior pitch: [[shipped/cli]] — built the `engine` adapter (`build`, `introspect`, artifact reads) this extends.

---

## What actually happened

The propose-then-validate, compile-and-run path landed for a query. It's surfaced through two CLI commands: `humbert vocab` shows what you can compose — the metrics and their dimensions, with kind and grain — and `humbert query` takes the metric you want plus group (`--by`), order (`--order`), filter (`--where`), and limit (`--limit`); a `--sql` flag outputs the SQL MetricFlow generated. Names are validated against the vocabulary before anything runs — an unknown metric or dimension is reported by name, and nothing reaches the warehouse until the selection resolves. The module (`semantic.py`) sits above the `engine` seam and never names dbt; the engine grew the dimension reads and the `mf query` run-path. The cheese acceptance check passes (Germany on top). Built to the cut line as scoped — no LLM, no Tier-2, no refusal typing. Tests split lean CI (engine stubbed) from a local `--extra dbt` integration suite that skips when the engine isn't installed.
