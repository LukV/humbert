# Humbert 🐄

A light, local-first analytics notebook. Ask a question of your data in plain language; get back a query, a chart, and a narrative you can stand behind.

> Not "here is a dashboard." But "here is a good first answer to the question you just asked."

Humbert - short for the Human Camembert - is for the human analyst: the AI does the plumbing, the human keeps judgement and trust. It refuses honestly when the data can't support an answer, every number traces back to its query, and the same question gives the same answer.

## Status

Early. Building v0 — see [`docs/planning/Betting Table.md`](docs/planning/Betting%20Table.md) for the plan and [`docs/planning/In%20Cycle.md`](docs/planning/In%20Cycle.md) for what's in flight.

## Quickstart

Humbert connects to a **dbt + DuckDB** project. The repo ships one — `examples/cheese` (cheese production across Europe, from FAOSTAT) — so you can run the whole path out of the box.

```bash
# 1. Backend, with the dbt engine (dbt-core + dbt-duckdb + MetricFlow)
cd apps/api
uv sync --extra dbt

# 2. Frontend — build once so `start` has something to serve
cd ../web && npm install && npm run build

# 3. Run it, from apps/api
cd ../api
uv run humbert init                            # scaffold ~/.humbert/
uv run humbert connect ../../examples/cheese   # build the warehouse + attach the source
uv run humbert status                          # show the connection + health
uv run humbert start                           # serve on http://localhost:8000
```

`humbert connect` builds the DuckDB warehouse from the dbt project, checks MetricFlow can read its metrics, and records the connection. Re-run with `--build` to force a rebuild, or `--schema marts,gold` to change which dbt layer(s) are exposed.

> **dbt fluency:** asking questions of Humbert needs none. *Connecting and maintaining* a source — the dbt project, its marts, the semantic layer — assumes you know dbt. That split is deliberate: easy for the analyst, dbt-literate for whoever maintains the source.

### Commands

| Command | What it does |
|---|---|
| `humbert init [name]` | Scaffold `~/.humbert/` and register a project. |
| `humbert connect <dbt-project> [--name] [--schema] [--build]` | Attach a dbt + MetricFlow source (needs the `dbt` extra). |
| `humbert status` | Show the active connection, exposed schema(s), health, skin, locale. |
| `humbert vocab` | List the metrics and dimensions the active source exposes. |
| `humbert query -m <metric> [--by] [--where] [--order] [--limit] [--grain] [--sql]` | Run a selection against the source; report unknown names. |
| `humbert ask "<question>" [--no-sql]` | Ask in plain language: plan → run → narrate (Tier 1). Needs an LLM key. |
| `humbert cells` | List the cells saved in the active notebook. |
| `humbert show <id>` | Show one stored cell in full — narrative, table, SQL, chart spec. |
| `humbert start [--port] [--no-browser]` | Boot the runtime and serve the UI. |

`connect` / `vocab` / `query` / `ask` need `--extra dbt`; `init` / `status` / `start` / `cells` / `show` run on the core install. `ask` also needs an LLM API key (by default `ANTHROPIC_API_KEY`).

### Asking the source

Before any notebook UI, the semantic layer is driveable from the CLI. `vocab` shows what you can ask; `query` composes a selection, validates every name against that vocabulary, then runs it through MetricFlow.

```bash
uv run humbert vocab                          # what metrics + dimensions exist?

# rank cheese-producing countries, biggest first, with the compiled SQL
uv run humbert query -m total_production \
  --by cheese_record__country --order -total_production --limit 6 --sql
```

`--by` groups, `--where` filters (a MetricFlow expression in template form, e.g. `"{{ Dimension('cheese_record__country') }} = 'Germany'"`), `--order` sorts (prefix `-` for descending), `--grain` sets the time grain, and `--sql` prints the SQL MetricFlow generated. An unknown metric or dimension is reported by name rather than run — nothing reaches the warehouse until it resolves.

### Asking in plain language

`query` makes you name the metric. `ask` lets you put the question in your own words and does that mapping for you — the two-call loop from [`009-orchestration`](docs/product-design/009-orchestration.md): **plan → run → narrate**. The model proposes a selection; Humbert validates and runs it; the model writes the answer over the rows that came back — never a number it hasn't seen the engine produce.

```bash
export ANTHROPIC_API_KEY=…           # ask needs an LLM; provider/model are config
uv run humbert ask "which countries produce the most cheese?"
```

It prints the narrative, the *reading* (how it mapped your words to metric and dimension names, so a loose match is visible and correctable), the tier and certainty, the rows, and the SQL (`--no-sql` to hide it). This is **Tier 1 only**: if no defined metric fits the question, it stops plainly rather than guessing — the governed-SQL fallback and honest refusal come in later blocks.

**Public-only by default.** v0 runs on public data, and Humbert enforces it: a metric is exposed only if every model it reads is classified `open` in dbt `meta:` — anything unclassified is withheld (default-deny). `connect`/`status` report how many were withheld and `vocab` names them. The bundled cheese project classifies its marts `open`, so it passes its own guard. Maintainers: see [`docs/technical/001-information-manager-instructions.md`](docs/technical/001-information-manager-instructions.md).

### The notebook

Every `ask` saves a **cell** — the reproducible unit ([`002-product-forms`](docs/product-design/002-product-forms.md)). A cell persists everything behind one answer: the question, the *reading*, the selection and compiled SQL, the result rows, a chart spec, the narrative, and the metadata (model, tier, certainty). Cells accumulate into a notebook, stored as plain JSON at `~/.humbert/projects/<project>/notebook.json`.

```bash
uv run humbert ask "which countries produce the most cheese?"   # saves a cell
uv run humbert cells                                             # list them
uv run humbert show 1                                            # one cell in full
```

`show` prints the cell's chart as a [Vega-Lite](https://vega.github.io/vega-lite/) spec — the right *type* for the answer's shape: a trend is a line, a breakdown a (sorted, top-N) bar, two measures a scatter, a single figure a number, and some answers get no chart at all.

> The notebook stores the result rows it returned, so a broad question (thousands of rows) makes for a large `notebook.json`. That's expected in v0; the snapshot/freeze story comes with validation.

### The notebook in the browser

`humbert start` serves the notebook as a web app: an empty page invites a question (with a starter question per chart shape for the bundled source), and each answer streams in as a cell — the narrative in serif with its figures emphasised, a Tufte-clean chart, and the SQL, chart spec, and reasoning a click away in a code drawer. Asking again appends a cell; a follow-up like *"add Italy"* refines the previous one rather than starting over; deleting a cell removes it. There's a light/dark toggle, and the chrome is ready for Dutch as well as English.

```bash
uv run humbert start          # serve http://localhost:8000 and open it
```

> Because asking now happens in the browser, `humbert start` has the same runtime needs as `humbert ask`: the LLM API key in its environment and the `dbt` extra installed. Reading an existing notebook needs neither.

### Configuration

Settings live in `~/.humbert/config.json`. The two blocks you'll touch:

```jsonc
{
  "llm": {
    "provider": "anthropic",          // v0 ships the Anthropic provider
    "model": "claude-opus-4-8",       // any model the provider offers
    "api_key_env": "ANTHROPIC_API_KEY" // which env var holds the key
  },
  "settings": {
    "max_result_rows": 1000,          // row cap on a query
    "statement_timeout_seconds": 30,
    "theme": "humbert",               // skin
    "locale": "en"                    // en / nl
  }
}
```

To ask with a different model, change `llm.model`; to point at another key, change `llm.api_key_env` and export that variable. Provider and model are config, never code — switching is a config edit (and, for a new provider, an install extra) away.

### Tuning the look (skins)

The whole interface is built from a handful of **design tokens** — colours and fonts — so changing the look is changing tokens, not components. Tokens live in [`apps/web/src/styles/theme.css`](apps/web/src/styles/theme.css) as a Tailwind `@theme` block:

```css
@theme {
  --color-paper: #fbfaf7;   /* the page background */
  --color-surface: #ffffff; /* the header bar and cards, raised above paper */
  --color-ink: #1a1a1a;     /* text */
  --color-brand: #4a2d4f;   /* aubergine — reserved for validation */
  --color-caution: #b8860b; /* amber — caution / the accent figure */

  --font-narrative: "Source Serif 4", Georgia, serif; /* the answer prose */
  --font-ui: "DM Sans", system-ui, sans-serif;        /* labels, metadata */
  --font-mono: "JetBrains Mono", ui-monospace, monospace; /* SQL */
}
```

**Experiment quickly** — edit those values, then rebuild (`cd apps/web && npm run build`) and reload. Change `--color-paper` for the background; change `--font-narrative` / `--font-ui` for the type. If you point a font token at a face that isn't installed, add it first — the three defaults are self-hosted via Fontsource (imported in [`apps/web/src/main.tsx`](apps/web/src/main.tsx)); to add another, `npm install @fontsource/<face>` and import its weights there, or drop in an `@font-face` / web-font `<link>`.

**A reusable skin** — rather than editing the defaults, add a skin file that overrides only what you want, scoped to its name:

```css
/* apps/web/src/styles/skins/dusk.css */
:root[data-skin="dusk"] {
  --color-paper: #f4f1ec;
  --font-narrative: "Lora", Georgia, serif;
}
```

Import it near the top of `theme.css` (`@import "./skins/dusk.css";`), set `"theme": "dusk"` in `settings` of `config.json`, and rebuild. The active skin is injected onto `<html data-skin="…">` server-side, so there's no flash of the default. (`humbert status` shows which skin is active.)

## Layout

```
apps/
  api/   # Python 3.13 backend (uv): runtime, semantic-layer engine, CLI
  web/   # React + TS + Vite + Tailwind v4 SPA, served by the backend
examples/
  cheese/  # the bundled dbt + DuckDB example (see its README)
docs/      # design, architecture, planning
```

## Develop

```bash
cd apps/api
uv sync --extra dbt        # core + dbt engine
uv run humbert --version
```

### Gates

```bash
cd apps/api
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd ../web && npm run build
```

CI runs the same, on the **core** install (no dbt) — the dbt path is exercised locally.

### Frontend dev server (hot reload)

`humbert start` serves the **pre-built** bundle on `:8000`, so editing React there shows nothing until you rebuild. For hot reload, run the **Vite dev server** alongside the backend and open **`:5173`** — it proxies `/api` to the backend on `:8000`.

```bash
make dev                       # runs both; open http://localhost:5173
```

Or in two terminals:

```bash
cd apps/api && uv run humbert start --no-browser   # backend + API on :8000
cd apps/web && npm install && npm run dev          # Vite (HMR) on :5173 — open this
```

Rule of thumb: **`:5173` while building the UI** (instant reload), **`:8000` to check the real built bundle** (run `npm run build` first, or `make build-web`).
