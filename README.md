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
| `humbert start [--port] [--no-browser]` | Boot the runtime and serve the UI. |

`connect` / `vocab` / `query` need `--extra dbt`; `init` / `status` / `start` run on the core install.

### Asking the source

Before any notebook UI, the semantic layer is driveable from the CLI. `vocab` shows what you can ask; `query` composes a selection, validates every name against that vocabulary, then runs it through MetricFlow.

```bash
uv run humbert vocab                          # what metrics + dimensions exist?

# rank cheese-producing countries, biggest first, with the compiled SQL
uv run humbert query -m total_production \
  --by cheese_record__country --order -total_production --limit 6 --sql
```

`--by` groups, `--where` filters (a MetricFlow expression, passed through), `--order` sorts (prefix `-` for descending), `--grain` sets the time grain, and `--sql` prints the SQL MetricFlow generated. An unknown metric or dimension is reported by name rather than run — nothing reaches the warehouse until it resolves.

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

### Frontend dev server

```bash
cd apps/web && npm install && npm run dev   # proxies /api to the backend on :8000
```
