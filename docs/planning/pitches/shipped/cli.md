---
project: humbert
type: pitch
status: shipped
block: setup
appetite: medium
created: 2026-06-07
started: 2026-06-07
shipped_on: 2026-06-07
---
# CLI — init / connect / start

## Problem

Bootstrap left a place for the entry point but no commands — `humbert` only prints its version. There is no way to stand up a project, point Humbert at data, or boot the runtime, so nothing downstream can be built or demonstrated. v0's first felt moment is the path **`init` → `connect` → `start`** working end to end against a real source. This pitch builds that path, and with it the first real contact with dbt + MetricFlow — which is where the deliberate, contained coupling from [[../../architecture/001-stack-decisions]] gets its seam.

## Sketch

Three commands, a contained dbt seam, the `~/.humbert/` persistence, and a small embedded example to connect to. The CLI is **Typer** (type-hint based, fits the 3.13 codebase).

### The commands

- **`humbert init [name]`** — scaffolds a project: creates `~/.humbert/` and `config.json` if missing, adds a project entry (with `settings.locale` defaulting to `en`), ensures the `projects/<name>/` cache dir. Idempotent.
- **`humbert connect <path-to-dbt-project> [--name N] [--schema marts,gold] [--build]`** — attaches a dbt + MetricFlow source. Validates the path is a dbt project, **auto-builds** the DuckDB warehouse when it's missing or stale (or when `--build` is passed), runs a **validation pass** (below), then writes a connection block with `exposed_schemas` (default `["marts"]`), sets `active_connection`, and points at the pack. Every dbt/`mf` touch goes through the engine adapter — `connect` itself never names dbt.
- **`humbert status`** — prints the active connection: name, project path, exposed schema(s) + a health summary (`N models · M metrics · K unavailable`), warehouse path + build time, skin, locale, config dir. No DSN — the warehouse is a file, so the path is what matters.
- **`humbert start [--port P] [--no-browser]`** — boots the runtime (FastAPI), serves the pre-built web `dist/` with `data-skin` *and* `lang` injected from `settings` (this **closes the bootstrap skin seam** — config-driven, no flash), exposes a small `GET /api/bootstrap` (skin, locale, app_name) the frontend reads, and opens the browser. No notebook UI yet (block 2); `start` boots and serves the skinned skeleton against the active connection.

### Exposed schemas — the Tier-2 fence

`connect` records `exposed_schemas` (default `["marts"]`, override via `--schema`). It defines the dbt layer(s) whose tables Tier 2 may query and that introspection surfaces — staging/intermediate stay out of bounds. Tier 1 metrics are already scoped by where the pack authors them. This pitch *records and validates* the list (and errors if a listed schema is empty or gone — the "IM renamed the layer" case); Tier-2 *enforcement* is block 2.

### The validation pass — fatal vs degraded

On connect (and re-connect), the engine adapter runs `mf validate-configs` (and `dbt parse`) and sorts every issue:

- **Fatal** (manifest won't parse, duplicate/ambiguous metric names) → connect fails with a clear, located message; nothing is attached.
- **Degraded** (a metric references a dropped column, an unsatisfiable metric, a missing time dimension) → connect *succeeds* but records which metrics are unavailable, surfaced in `status`. Recording-and-surfacing only here; feeding it to precise refusal is the semantic-layer module + block 3.

### The engine adapter — the one dbt seam

A thin `engine` module is the *only* code that invokes dbt or `mf`, or names them. For this pitch it exposes just what `connect` needs: `build(project_path)` (runs `dbt deps`/`seed`/`build`) and `list_metrics(project_path)` (the connect smoke-check). Hardwiring dbt commands is fine *because* it's contained here — the exit strategy in the ADR lives or dies on this boundary holding. The richer propose-then-validate / compile-run interface is the **semantic-layer module** pitch; this adapter is its seed.

### Persistence — `~/.humbert/`

Per [[../../architecture/001-stack-decisions]]: `config.json` (connections each with `active_pack`, `active_connection`, `llm`, `settings`), `projects/<name>/` caches. A platform-dirs helper picks the base dir (`~/.humbert/` on *nix; Windows equivalent — carried open item). The DuckDB warehouse for a connection lives with its dbt project, not in `~/.humbert/`.

### The embedded example — `examples/cheese/`

A minimal dbt + DuckDB project so `connect` has something to attach out of the box (`humbert connect ./examples/cheese`):

- **`seeds/cheese_production.csv`** — a **derived** FAOSTAT QCL subset: cheese production by country × milk-source × year, tonnes. Filtered to **EU-27 + Switzerland, UK, US** (individual countries, not aggregate regions), all years (1961→), tidied to long format (`area, item, year, value_tonnes`). Under ~1 MB, committed. The 65/88 MB raw QCL dumps are **gitignored** under `data/raw/`; a documented `derive_seed.py` + a README note (source, CC BY 4.0 attribution, exact filter) make the seed regenerable without being required. Contributors fetch nothing.
- **`models/`** — `staging/` clean-up + unpivot, then a star in `marts/`: `fct_cheese_production`, `dim_country`, `dim_date`, **`dim_product`** (milk source: cow / sheep / goat / buffalo).
- **`models/semantic/cheese.yml`** — one semantic model with **1–2 metrics** (e.g. `total_production`) and dimensions (country, year, milk source). Enough for MetricFlow to list a metric; the fuller pack is deferred.
- **`profiles.yml`** — `dbt-duckdb`, target a gitignored local `warehouse.duckdb`.

## Cut line

`humbert init` → `humbert connect ./examples/cheese` (auto-builds the DuckDB warehouse, runs the validation pass, records `exposed_schemas`) → `humbert status` reports the connection + health → `humbert start` boots and serves the skinned, locale-set skeleton against the active connection.

## Out of scope

- **The semantic-layer module's real interface** — propose-then-validate, compile + run a selection. `connect` validates and records health; the queryable interface is the next pitch.
- **Satisfiability tracking fed to refusal** — `connect`/`status` *record and show* unavailable metrics; turning that into precise typed refusals (`NO_VALID_METRIC`-style) is the semantic-layer module + block 3.
- **Tier-2 enforcement** — this pitch *records* `exposed_schemas`; fencing model-authored SQL to those schemas is block 2.
- **The i18n machinery** — this pitch seeds `settings.locale` + `<html lang>` + `status` display only. UI string catalogs and narrative language are a **dedicated localization pitch** landing with block 2.
- **The notebook UI and the loop** — block 2. `start` serves the skeleton, nothing more.
- **The full pack** (`domain/ context/ introspection/ tests/`) and the **public-only classification guard** — pack-scaffolding pitch. The example carries only a minimal slice.
- **Tier 2 SQL guard, LLM calls, telemetry** (`telemetry on/off`, `stats`) — later blocks.
- **`connect --parquet`** (raw-parquet-directory → DuckDB views, as Lumen had) — Humbert always goes through a dbt project; there is no raw-directory connect path. Noted so it isn't re-added.
- **Postgres / non-DuckDB engines, multi-connection management UX** beyond setting `active_connection`.
- **A rich `init` scaffold** (project templates, sample packs) — `init` does the minimum to register a project.

## Risks / unknowns

- **dbt dependency weight.** `dbt-metricflow` pulls in dbt-core + adapters — a heavyish tree for a "keep it small" tool. Accepted as the chosen architecture, but worth watching install time and footprint.
- **How the adapter talks to MetricFlow.** `mf` CLI shell-out (simplest, matches "hardwire dbt commands") vs the MetricFlow Python client. Decide in-pitch; lean CLI shell-out for `list_metrics` now, revisit when the module pitch needs compile/run.
- **Auto-build ergonomics.** dbt build failures must surface cleanly through the adapter, not as raw tracebacks. Staleness detection should stay a simple heuristic (seed/model mtime vs warehouse mtime); don't over-build it.
- **Validation-pass fidelity.** How cleanly `mf validate-configs` separates fatal from degraded, and whether unavailable metrics come back structured enough to list in `status`, needs confirming against the real tool — the fatal/degraded split is a design promise the tool has to support.
- **Exposed-schema enumeration.** Mapping `exposed_schemas` to actual models likely reads dbt's `manifest.json` (model → schema). Confirm that's the right source and that an empty/renamed schema is detectable there.
- **FAOSTAT seed derivation.** Pin the exact cheese item codes from `Production_Crops_Livestock_E_ItemCodes.csv` (don't guess names), map milk-source items to `dim_product`, exclude FAOSTAT aggregate areas (keep individual countries), and tidy wide year-columns to long. The `derive_seed.py` is documentation/regenerability, not run in CI. Confirm `dbt-duckdb`'s exact licence while here.
- **Windows persistence path.** Which platform-dirs helper and the exact directory — carried open item from the ADR.

## Related

- [[../blocks/01-setup-and-bootstrap]] — the block; semantic-layer module and pack scaffolding are the sibling pitches.
- [[../../architecture/001-stack-decisions]] — DuckDB engine, the dbt-coupling seam + exit, persistence layout, the skin seam this closes.
- [[../../product-design/004-semantic-layer]] — the pack and Tier 1, which this connects to.
- Prior pitch: [[shipped/project-bootstrap]].

---

## What actually happened

The four key CLI commands landed: through the CLI you can initialise a project and connect — through the MetricFlow semantic layer — to data residing in DuckDB, check the status, and start the frontend. Verified against a real test dataset and setup, the `examples/cheese` project built on FAOSTAT Europe data, and the whole path is explained in the README. The dbt seam is contained behind a single `engine` adapter (the only code that names dbt/`mf`, via subprocess), and the engine is an optional `dbt` extra so the core stays light and CI runs lean. The embedded seed is the real derived FAOSTAT subset (4,151 rows, ~240 KB) produced by `derive_seed.py` from the gitignored raw dump. Cut to plan: deeper satisfiability→refusal, Tier-2 enforcement, and the i18n machinery were all left to later blocks as scoped. Watch: `mf validate-configs` fatal/degraded attribution is still basic, and CI does not exercise the dbt path (deliberate).
