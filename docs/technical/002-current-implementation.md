---
project: humbert
type: technical
status: living
updated: 2026-06-11
---
# Current implementation

How Humbert's code works today, written for a new contributor, or a Claude session that shouldn't have to reverse-engineer 3,000 lines to find a seam. The *why* behind these choices lives in [[projects/humbert/docs/architecture/001-stack-decisions|001-stack-decisions]] the operator's guide for running a data pack is [[001-information-manager-instructions]]. This note is the *what*.

## The shape of the system

One question flows through the system like this:

```
 "which countries produce the most cheese?"
        │
        ▼
 orchestrator.ask          plan → run → narrate (two LLM calls, PydanticAI)
        │  proposes a Selection, validated by…
        ▼
 semantic.resolve/run      the deterministic core: vocabulary, validation
        │  compiles and runs through…
        ▼
 engine.query              the only module that shells out to dbt / mf
        │  returns rows + compiled SQL
        ▼
 notebook.record           the answer becomes a Cell in notebook.json
        │  (chart.chart_spec picks the Vega-Lite spec on the way in)
        ▼
 server/wire.wire_cell     the Cell reshaped to the JSON the SPA renders
```

Two seams hold this together, and they are never crossed:

- **Only `engine.py` names dbt or `mf`.** Everything above it speaks Humbert's terms — metrics, dimensions, selections, rows. The MetricFlow licence bet (see the ADR) is contained in this one file.
- **Only `orchestrator.py` imports `pydantic_ai`.** The LLM is two structured calls behind one seam, swappable the same way.

Everything is synchronous Python. There is no task queue, no async resource, no database server — local-first means a DuckDB file, JSON files under `~/.humbert/`, and subprocesses.

**The tier vocabulary**, which the code uses everywhere: **Tier 1** answers from *defined metrics* through MetricFlow — deterministic SQL, the model never writes a query. **Tier 2** (parked, not built) will be governed model-written SQL over the marts when no metric fits. **Tier 3** (block 3, not built) is the styled honest refusal. Today only Tier 1 exists: a question that doesn't map to a defined metric stops plainly as a `NoTier1Answer`, which the notebook renders as a calm refused cell.

**If you're new, read in this order:** `semantic.py` first (the core idea — vocabulary, `Selection`, validate-then-run — in ~350 lines), then `orchestrator.py` (how the LLM is allowed to touch it), then `server/routes/ask.py` (how a browser question travels). After those three, the rest is plumbing you can read on demand.

## Stack at a glance

| Layer | Choice |
|---|---|
| Backend | Python 3.13, uv-managed, FastAPI + uvicorn |
| Semantic layer | dbt-core + MetricFlow (via the `dbt`/`mf` binaries, never their Python API) |
| Warehouse | DuckDB file, built by `dbt build` from committed seeds |
| LLM | PydanticAI (`pydantic-ai-slim[anthropic]`); provider/model from config |
| Frontend | React 19 + TypeScript + Vite SPA; plain CSS design tokens, no Tailwind, no router |
| Charts | Vega-Lite specs, generated deterministically in Python, rendered by react-vega |
| Quality gates | ruff (E/F/I/UP/B/SIM, line 100), ruff format, strict mypy (src + tests), pytest, tsc + vite build |

## Backend modules (`apps/api/src/humbert/`)

Flat, one module per concern. The server is the one package, because routes wanted one file per concern too.

### `config.py` — persistence and configuration

`~/.humbert/` (or `%LOCALAPPDATA%\humbert` on Windows; `HUMBERT_HOME` overrides — the tests use it) holds one `config.json` and per-connection state:

```
~/.humbert/
  config.json            # connections, active_connection, llm, settings
  projects/<name>/
    notebook.json        # the cells (see notebook.py)
    theme.json           # optional skin (see theme.py)
    feedback.jsonl       # appended thumbs up/down
```

`Config` is a Pydantic model: `connections` (each a dbt project path with `exposed_schemas` and the health counts `connect` recorded), `llm` (`provider` / `model` / `api_key_env` — model-agnosticism is config, not code), and `settings` (`theme`, `app_name`, `locale` en/nl, the empty-state `suggestions`). Unknown keys in an existing config.json are ignored on load, so removing a setting is painless.

### `engine.py` — the dbt + MetricFlow seam

Everything dbt: `build` (deps + build), `parse`, `introspect` (the connect-time validation pass), vocabulary inputs, and `query`. Three things worth knowing:

- **Artifacts are read through Pydantic models** (`_Manifest`, `_SemanticManifest`) that declare exactly the slice of dbt's JSON we use and ignore the rest. Parsed artifacts are memoised by file mtime (`_artifact_cache`), so the megabyte manifests are parsed once per build, not once per reader.
- **`mf` output is parsed defensively**: ANSI codes stripped, the `• name` bullets of `mf list dimensions`, the SQL after the `--explain` marker. These parsers have dedicated tests because they are the brittle edge.
- **`query` runs `mf` twice in series** — `--csv` for rows, `--explain` for SQL. Not concurrently: both invocations open the DuckDB file and DuckDB allows one writing process at a time.

`EngineError` is the module's one exception; everything above maps or repackages it.

### `semantic.py` — the deterministic Tier-1 core

Humbert's own vocabulary of asking:

- `Vocabulary` — the metrics and dimensions the source exposes; the "what can I ask?".
- `Selection` — the reproducible IR of a question (metrics + group_by + where + order/limit/grain). Serialisable on purpose: this is what a validated cell will freeze. Concretely, "which countries produce the most cheese?" becomes:

  ```json
  {
    "metrics": ["total_production"],
    "group_by": ["cheese_record__country"],
    "where": [],
    "order_by": ["-total_production"],
    "limit": 6,
    "time_grain": null
  }
  ```

  Dimensions use MetricFlow's dunder form; `where` entries are MetricFlow filter templates (`{{ Dimension('cheese_record__country') }} = 'Germany'`), passed through unvalidated by design — a malformed one surfaces later as an engine error.
- `resolve(selection, vocabulary)` — propose-then-validate by exact name. Returns `ResolvedSelection` or `Unresolved` with every gap named. Never an exception, never a refusal — data the caller acts on.
- `run(resolved, …)` — compile-and-run through the engine.
- **The public-only guard** (`classify_metrics`): default-deny — a metric is exposed only if every model it reads is classified `open` in dbt `meta:`. Enforced where the `Vocabulary` is assembled, so every consumer inherits it without knowing it exists.

`load_pack` (discovery) shells out to `mf list dimensions` once per metric — seconds each — so the result is **cached on disk** at `<project>/target/humbert_pack.json`, keyed on the dbt artifacts' mtimes. A rebuild moves the key and the next load rediscovers; everything else (including each fresh CLI invocation) reads the cache. A malformed or stale cache silently falls back to rediscovery.

### `orchestrator.py` — the two-call loop

`ask(question, …)` runs the contract from `009-orchestration`:

1. **Plan** — the question + vocabulary go to the model, which returns a `Plan` (`Selection` + a one-line `reading` of how it mapped the words). PydanticAI validates the shape; a hallucinated selection never reaches `resolve` as a string we parse and pray over.
2. **Validate (deterministic)** — `semantic.resolve`; on failure, the named gaps are fed back *once* and the model re-plans. Resolved on the first try ⇒ `certainty: high`, on the retry ⇒ `medium`. Still unresolved ⇒ `NoTier1Answer` (an honest stop, not an error).
3. **Narrate** — the rows go back to the model, which is forbidden from stating a number not present in them.

The agents are module-level (instructions are static); the configured model is passed per run, so tests pass a scripted `TestModel`/`FunctionModel` and CI never calls a real LLM. Progress is reported through `on_stage`, typed `Stage = Literal["planning", "replanning", "running", "narrating"]` — the orchestrator emits keys, the CLI and server each own their copy.

### `chart.py` — deterministic chart choice

A chart type is a property of the data, not a judgement call, so this is plain code: time grouping → line, categorical → top-20 bar, single value → number, two measures → scatter, time + category → a line per category (≤ 6 series), anything else → no chart, which is a valid outcome. Specs carry the Tufte-clean config (no gridlines, direct labels, muted series palette). `parse_number` / `rows_to_records` live here and are shared with `server/wire.py`, so chart and table coerce text→number identically.

### `notebook.py` — the cell and its persistence

`Cell` is the reproducible unit: question, reading, selection, SQL, rows, chart spec, narrative, and the metadata that says how the answer was reached (model, tier, certainty). `Notebook` is an ordered list of cells in one `notebook.json` per connection. Mutations (`record`, `set_title`, `delete`) are load-modify-save on one file, serialised by a module lock — the server runs each ask on its own thread, and two in-flight answers must not claim the same id. `record_feedback` appends to `feedback.jsonl` next to it. The orchestrator never knows persistence exists.

One thing that will otherwise confuse you: **a cell has two shapes.** The *stored* cell here is flat (`sql` is a string, `rows` a list of text lists, ids are ints). The cell the SPA receives is nested — `sql` / `result` / `chart` / `narrative` / `refusal` / `metadata` blocks, ids as strings, measure values coerced back to numbers. `server/wire.py` is the one place that mapping lives; `notebook.json` and the network tab will never match, and that's intentional.

### `theme.py` — skins

A skin is a `theme.json` (app name, locale, brand colours, palette, fonts) resolved project-first: `projects/<connection>/theme.json` → `~/.humbert/theme.json` → built-in defaults. `theme_to_css_vars` turns it into the CSS custom properties the SPA sets over its default tokens. No rebuild — skinning is runtime data.

### `server/` — the web runtime

```
server/
  __init__.py   create_app(config, dist): exception handlers, router
                registration, static mounts, the SPA catch-all
  state.py      AppState(config, dist) — stowed on app.state, injected via…
  deps.py       StateDep, and require_connection → ConnectionDep
  errors.py     APIError(status, message) → {"error": message}
  sse.py        the SSE frame formatter
  wire.py       wire_cell: stored Cell → the nested JSON the SPA renders
  routes/       one file per concern, request models beside their handlers
    ask.py  cells.py  health.py  theme.py  misc.py
```

`create_app(config, dist)` takes explicit arguments (no lifespan, no globals) — tests build an app per case with a `Config()` and a tmp dir. Routes get shared state via FastAPI dependencies: `StateDep` for config/dist, `ConnectionDep` where a route needs the active connection (raising the one 400 otherwise). **Every failure has one wire shape**: `{"error": message}` — `APIError` raises from routes, and handlers normalise `HTTPException` and validation errors to the same shape.

The SPA is served by a catch-all that injects `lang` and `data-skin` into `index.html` (cached by the file's mtime, sent with `Cache-Control: no-cache` so a rebuilt bundle is never referenced by a stale shell). Unknown `/api/*` paths are real 404s, never the shell.

### `cli.py` — the commands

Thin Typer commands that read/write config and delegate to the modules: `init` (scaffold home / a pack), `connect` (validate + build + record), `status`, `vocab`, `query`, `ask`, `cells`, `show`, `start` (uvicorn + browser). `connect`/`vocab`/`query`/`ask` need the `dbt` extra; `ask` and `start` need the LLM key.

## The web API

All routes under `/api`, registered in `create_app`. Errors are always `{"error": message}`.

| Method, path | What it does |
|---|---|
| `GET /api/bootstrap` | skin, locale, app name from config |
| `GET /api/theme` | resolved theme: app name, locale, custom CSS URL, CSS variables |
| `GET /api/healthz` | named checks (connection, warehouse file, metrics readable) → `ok` / `degraded` / `down` |
| `GET /api/notebook` | every cell, wire-shaped |
| `POST /api/ask` | the streaming ask (below) |
| `PATCH /api/cells/{id}` | rename (empty title = fall back to the question) |
| `DELETE /api/cells/{id}` | delete, idempotent (`{"deleted": bool}`) |
| `GET /api/suggestions` | the empty-state chips (static, from config) |
| `POST /api/feedback` | append a thumbs up/down |
| `GET /api/schema` | a stub so the SPA's probe resolves cleanly |

**`POST /api/ask`** takes `{question, parent_cell_id?}`. Setup problems — no connection, no API key, an unreadable engine — fail *before* the stream starts, as plain JSON (400/502); the SPA shows those in its header banner. Otherwise the response is an SSE stream:

| Event | Payload | Meaning |
|---|---|---|
| `stage` | `{"stage": "thinking" \| "correcting" \| "executing" \| "narrating"}` | progress over the slow calls |
| `cell` | the wire-shaped cell | the answer — including a calm refused cell for no-Tier-1 |
| `error` | `{"message": …}` | the loop failed; shown quietly in the notebook |

The orchestrator runs on a worker thread pushing frames onto a queue the response generator drains. The worker deliberately outlives a disconnected client: the (paid) answer still completes and persists.

A follow-up sends `parent_cell_id`; if that cell has a resolved selection, the planner is shown the previous question + selection and told to refine *only* when the new question plainly refers back ("add Italy") — otherwise it plans fresh.

## The frontend (`apps/web/src/`)

Plain React SPA — no router (one view), no Tailwind (one `styles.css` of design tokens under `[data-theme="light|dark"]` blocks; components never hardcode a colour or font).

```
App.tsx               layout: topbar, error banner, hero or notebook
hooks/
  useTheme.ts         light/dark toggle, persisted, sets <html data-theme>
  useHealth.ts        /api/healthz on mount + adaptive polling (2s while
                      disconnected, 30s steady-state); owns connectionError
  useBranding.ts      /api/theme: app name, locale, skin CSS variables
  useNotebook.ts      cells, suggestions, cell CRUD, and the ask/SSE pipeline
components/
  CellView.tsx        one cell (memoized; lazy chart; code drawer on demand)
  ChartRenderer.tsx   react-vega + dark-mode/skin spec rewriting (lazy chunk)
  NarrativeView.tsx   markdown → DOMPurify → figure emphasis spans
  CodeView.tsx        SQL / chart spec / reasoning tabs (sqlEdit flag off)
  InputBar.tsx        hero and compact variants of the ask box
  StageIndicator.tsx  the processing dots + stage copy
  ReasoningStream.tsx the collapsible streaming reasoning text
  FeedbackControls.tsx thumbs up/down → POST /api/feedback
utils/
  api.ts              same-origin fetch helpers; retry is opt-in
  fetchWithRetry.ts   startup-only backoff (never retries an abort)
  sse.ts              the SSE parser (spec-correct joining + end flush)
types/ cell.ts api.ts  the wire shapes
locales/              en.json + nl.json + t(); locale is reactive via
                      useSyncExternalStore — setLocale re-renders subscribers
```

Worth knowing:

- **Strings go through `t()`** and every user-facing string exists in both `en.json` and `nl.json`. The locale arrives with `/api/theme`; components that render copy subscribe with `useLocale()`.
- **The cells don't re-render while reasoning streams.** `CellView` is `React.memo` with stable callbacks; the per-token `reasoningText` updates touch only App's own tree. The vega stack is a lazy chunk loaded when the first chart renders.
- **LLM markdown is sanitized.** The narrative is parsed by marked, sanitized by DOMPurify, *then* the figures are wrapped in `narrative__num` spans (on the parsed HTML's text nodes — doing it before parsing corrupts ordered lists). Hovering a chart point highlights the matching figures by digit-match.
- **Asking twice is safe.** A new ask aborts the in-flight one; teardown is guarded by controller identity so the replaced request can't switch off its successor's indicator.
- **Feature flags** (`src/config.ts`): `FEATURES.sqlEdit` hides the SQL-editing UI until the Refinement pitch builds `/api/run-sql`.

Dev workflow: `make dev` runs uvicorn on `:8000` and Vite (HMR, proxying `/api`) on `:5173`. `humbert start` serves the built `dist/` — the backend injects skin and locale into the shell at serve time.

## Caches

Small and boring, all keyed on file mtimes so invalidation is "the file changed":

| Cache | Where | Key | Why |
|---|---|---|---|
| Parsed dbt artifacts | `engine._artifact_cache` (in-process) | manifest mtime | several readers per vocabulary build, MB-scale files |
| Discovered pack | `<project>/target/humbert_pack.json` (disk) | both artifacts' mtimes | discovery is N× `mf list dimensions` subprocess calls |
| SPA shell | closure in `server/__init__.py` | `index.html` mtime | injected per config, not per request |

## Testing

One `tests/test_<module>.py` per module; strict mypy covers the tests too. The expensive boundaries are faked, the logic is real:

- **Orchestrator**: PydanticAI's `FunctionModel` scripts the model's answers — the full plan/retry/narrate loop runs with no API key and no network.
- **Engine**: artifact readers run against real temp-file manifests; subprocess calls are stubbed with canned `mf` output (including the ANSI/bullet parsing).
- **Server**: `TestClient(create_app(Config(), tmp_path))` per test; `HUMBERT_HOME` points at a tmp dir.
- **Integration** (`test_semantic_integration.py`): the real `mf` against `examples/cheese`, skipped when the dbt extra isn't installed — CI runs the core install and **never runs dbt or an LLM**.

## Gates

`make gates`, the `local-gates` skill, and CI run the identical sequence:

```bash
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd apps/web && npm run build
```

Releases: Luk runs `cz bump` (commitizen, `.cz.toml`), which now also stamps `apps/api/pyproject.toml`, `humbert/__init__.py`, and `apps/web/package.json` via `version_files`.
