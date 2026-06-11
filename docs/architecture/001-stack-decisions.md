---
project: humbert
type: architecture
status: active
updated: 2026-06-11
---
# Stack decisions

What Humbert is built with, and why. This is what Claude Code reads on day one before touching the planning folder — so it doesn't re-derive the stack from the block notes. The settled decisions are carried from the design notes and the Lumen lineage; the runtime config shape they produced is real code now (`apps/api/src/humbert/config.py`). Items marked *open* are real decisions still to make.

## Settled

- **Local-first.** Runs against a source on a laptop; no cloud or hosted service required to begin (design pillar 6, [[../product-design/003-design-pillars]]).
- **Backend: Python 3.13** (uv-managed). Pinned to 3.13 rather than newest (Lumen ran 3.14) for dbt-core + MetricFlow headroom — those lag new Python releases, and the whole product routes through them. Frontend: **React + TypeScript, built with Vite as a plain SPA** — *not* Next.js. The analytical core is the Python runtime; the UI is one client over its API (pillar 7), so the frontend has no backend of its own to justify Next's server model, and SSR / RSC / edge / hosting are all things v0 explicitly excludes ([[../product-design/003-design-pillars]], `_context.md`'s "keep it small"). Styling is **plain CSS, no Tailwind**: design tokens as CSS variables in `apps/web/src/styles.css` (`[data-theme]` blocks for light/dark); components never hardcode a colour or font. Dev: Vite dev server with HMR proxying `/api` to the Python process. Prod/`humbert start`: Python serves the pre-built `dist/`. There is **no router yet** — the notebook is a single view; reach for React Router when a second route is real. Revisit Next only if a hosted multi-tenant form ever becomes real.
- **Semantic layer via dbt + MetricFlow.** Defined metrics (Tier 1) come from MetricFlow; `connect` points Humbert at a dbt project, not a raw database. The semantic layer is **its own in-process module** ([[../product-design/004-semantic-layer]]): the notebook reaches data only through its interface — no warehouse handle, dbt connection, or raw SQL leaks past it. Promotable to a service later behind the same interface.
- **Engine: DuckDB, not Postgres.** The local warehouse is an embedded DuckDB file — no server process (fits local-first and "keep it small"), columnar and fast for group-by analytics, first-class dbt adapter (`dbt-duckdb`) and MetricFlow support. Example/source data is committed as **dbt seeds (CSV)** and built into a **gitignored `.duckdb`** by `dbt build`; Parquet is reserved for genuinely large raw inputs. Postgres is not a v0 target.
- **Two-call orchestration.** Plan → run → narrate, with deterministic SQL compilation between the model calls ([[../product-design/009-orchestration]]). The model never reports a number it hasn't seen the engine produce.
- **Agent framework: PydanticAI** ([ai.pydantic.dev](https://ai.pydantic.dev)). The plan call returns the `Selection` IR (block 1's pydantic model) **already validated** via `Agent(model, output_type=Selection)`, with automatic retry when the model returns something off-schema — so a hallucinated selection never reaches `resolve()` as a string we parse and pray over. It is **provider-agnostic** (driven by `config.llm`'s `provider / model / api_key_env`, honouring model-agnosticism), and ships `TestModel` / `FunctionModel` so unit tests drive the loop with a scripted model and **CI never calls a real LLM**. We use only its thin single-call surface — there is no open-ended agent *loop* here, just two structured calls — and confine it behind one `orchestrator` seam, the way the dbt engine is confined, so it stays swappable. Chosen over the raw provider SDK, which would mean hand-rolling provider selection, JSON-schema tool definitions, and parse/validate/retry per provider: more code to own, less safety. Decided with block 2's two-call-orchestration pitch.
- **Charts as Vega-Lite specs**, FT / Observable-style theme as the default (design pillar 5).
- **The cell is the unit of reproducibility** — query, result metadata, chart spec, narrative, tier, certainty score ([[../product-design/002-product-forms]]).
- **Model-agnostic.** Provider and model are config, not code: `llm: { provider, model, api_key_env }` (`config.py`'s `LLM` model). Swapping models must not break past work (design pillar 2). Quality comparison across models is deferred to **Evaluation** (block 5), where there's ground truth to compare against.
- **Persistence at `~/.humbert/`** (*nix) and `%LOCALAPPDATA%\humbert` on Windows — hand-rolled in `config.py`, no platform-dirs dependency; `HUMBERT_HOME` overrides the location (the tests use it). Layout mirrors Lumen's `~/.lumen/`:
  - `config.json` — connections (dbt projects, each with `exposed_schemas` — the dbt layer(s) Tier 2 may query, default `["marts"]`), `active_connection`, `llm`, `settings` (`theme`, `app_name`, `locale` — `en`/`nl`, default `en`, drives UI chrome and narrative language — and the empty-state `suggestions`). Query limits (`max_result_rows`, `statement_timeout_seconds`) return as settings when Tier 2 needs them.
  - `projects/<name>/` — per-connection state: `notebook.json`, optional `theme.json`, `feedback.jsonl`.
  - `telemetry/events.jsonl` — append-only event log ([[../product-design/007-telemetry]]); not built yet. **`feedback.jsonl` is back** — the notebook UI grew thumbs up/down per cell, appended per-connection next to `notebook.json` (reversed from the earlier "no feedback" call when the cell shipped).
- **Open source**, model- and provider-agnostic where it can be (design pillars 7, 8).

## Skinning — per-client design system

Humbert ships as a reference implementation with one default skin; specific clients get their own. Concretely: **Humbert** (default — its fonts, colours, and the name "Humbert") and **Proef** for CJM (its own fonts, colours, and app name). Same product, different skin.

The mechanism, as built (an earlier Tailwind-`@theme` plan was superseded — there is no Tailwind):

- **Design tokens** are the design decisions as named CSS variables in one source of truth — `apps/web/src/styles.css`, with `[data-theme="light|dark"]` blocks — never hardcoded values in components. A *skin* is one set of token values.
- **Skins are runtime data, not builds.** A deployment drops a `theme.json` next to the connection it brands (`~/.humbert/projects/<name>/theme.json`, falling back to `~/.humbert/theme.json`, falling back to built-in defaults — `theme.py`). It carries the app name, locale, brand colours, chart palette, and font names. One build serves every client.
- **The server applies it.** `GET /api/theme` hands the resolved theme to the SPA, which sets the CSS variables (`theme_to_css_vars`) over the default tokens. `data-skin` and `lang` are injected onto `<html>` server-side when `index.html` is served — no flash of the default on first paint. This is the one piece of server-templating the otherwise-static SPA needs.
- **The app name** (Humbert vs Proef) is **config/branding, not a token** — it rides in `theme.json` alongside the colours and is rendered by the UI as text.

The hands-on guide for information managers (writing a `theme.json`, custom fonts, logos) is `docs/technical/001-information-manager-instructions.md`.

## The dbt routing question — answered

Because everything is routed through dbt, two Lumen-era concerns shrink:

- **DataSource Protocol — dropped.** Lumen's protocol existed to abstract Postgres / DuckDB / Parquet behind one interface. dbt's adapter (and MetricFlow) now owns the connection and dialect, and the semantic-layer module owns the single handle. The multi-source abstraction is redundant — don't port it.
- **SQL validation — mostly gone, not entirely.** Tier 1 SQL is MetricFlow-generated and safe; no validation needed. But **Tier 2** (the governed fallback, [[../product-design/009-orchestration]]) is *model-authored* SQL over the marts, so it still needs a light guard — **not** Lumen's pglast AST validator, but: read-only execution, single statement, auto-`LIMIT` (`max_result_rows`), `statement_timeout_seconds`, and scoped to governed marts only. Both limits are configuration plus a thin execution wrapper, not a validation subsystem — they enter `settings` when Tier 2 is built (they were carried as dormant settings for a while and removed until needed).

## dbt + MetricFlow coupling — deliberate, isolated, reversible

Humbert routes Tier 1 through dbt + MetricFlow. This is a deliberate bet, taken with eyes open.

- **The licence risk is real and concentrated in MetricFlow.** MetricFlow's licence has changed twice — AGPL (≤0.140) → BSL, *non-production-use-only* (0.150–0.208.2) → Apache 2.0 (0.209.0+). We pin Apache versions (`metricflow ≥0.209`, `dbt-metricflow 0.13.x`), so today the whole stack is OSI-open. But it flip-flopped inside ~two years, so "the licence changes under us" is track record, not paranoia. By contrast **dbt-core is Apache 2.0, committed long-term**, and the commercial **Fusion engine is unused** — so the risk sits on MetricFlow alone.
- **One seam contains the bet.** A dbt **engine adapter** inside the semantic-layer module is the *only* code that invokes dbt / `mf` or even names them. Everything above speaks Humbert's own terms — metrics, dimensions, selections, rows. `connect` calls `engine.build(...)` / `engine.list_metrics(...)`; it never shells out to dbt directly. Swap that one adapter, keep the rest.
- **The exit is pre-built, not hypothetical.** The durable substrate is dbt-core + DuckDB + the marts; MetricFlow is a replaceable top layer. **Tier 2 (model-authored SQL over the governed marts) already answers questions without MetricFlow** ([[../product-design/009-orchestration]]) — so the floor under us is always plain SQL against DuckDB tables. If the licence turns, we pin/fork the last Apache MetricFlow (Apache permits the fork) or fall back to SQL-over-marts; the hardwired dbt commands change in one file.

This is why hardwiring dbt commands into `connect` is acceptable: the coupling is real but contained, and getting out is a localised change, not a rewrite.

## Classification & the public-only guard — model-level, default-deny

v0 runs on public data only ([[../product-design/004-semantic-layer]]), and that promise is enforced, not assumed:

- **Classification rides in dbt `meta:`, at the model level.** A marts model declares `meta: { classification: open }`. v0 stops at model granularity — per-attribute/column classification, masking, and disclosure are deferred until non-open data is actually connected (the design defers them too). Coarse open/not-open is exactly enough to hold the v0 promise.
- **The guard is default-deny.** A metric is exposed only if *every* model it reads is classified `open`; an **unclassified** model is treated as not-open and withheld. Forgetting to classify hides data rather than leaking it — the fail-safe direction.
- **Enforced at the vocabulary chokepoint.** The classification *read* lives in the engine adapter (parsing `meta:` from `manifest.json`); the *policy* (default-deny, what to withhold) lives in the semantic-layer module where the `Vocabulary` is assembled. Every downstream consumer — `vocab`, `query`, and block 2's Tier 1/Tier 2 — inherits the fence for free, without knowing classification exists. Building it here, before block 2 gives the chokepoint consumers, avoids retrofitting every data-reaching path later.
- **Withhold-and-report, not abort.** `connect`/`status` report how many objects were withheld; the connect fails only if the filter leaves the exposed layer empty (with a message naming the fix). A strict mode that hard-fails on any unclassified model is deferred until a real project wants it.

## Open — decide before the block that needs them

- **Tier-2 execution path** *(parked 2026-06-09, with the Tier-2 pitch)*. Exactly how model SQL runs through the semantic-layer module against the marts, and the precise guard rules. Deferred behind **The cell** — settle when Tier 2 is picked up.

Settled since: **streaming** — `POST /api/ask` is an SSE stream (stage events + reasoning tokens + the finished cell), consumed by `apps/web/src/utils/sse.ts`; the CLI takes the same path synchronously. **Windows persistence path** — no platform-dirs helper; `config.py` hand-rolls `%LOCALAPPDATA%\humbert` with `HUMBERT_HOME` as the override.

## Related

- [[../planning/_about]] — how the planning surface works.
- [[../planning/blocks/01-setup-and-bootstrap]] — where most open items get decided.
- [[../product-design/009-orchestration]] — the runtime contract this stack serves.
- [[../_context]] — tone and the "keep it small" constraint.
