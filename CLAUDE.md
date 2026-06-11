# CLAUDE.md

Read this first. It's a map, not a manual — it points at the notes that hold the detail, so a fresh session knows where to look before touching code.

## What Humbert is

A light, local-first analytics notebook for the cultural and youth sector. The product vision lives in `docs/product-design/` (`001`–`010`) and the tone that governs all writing in `docs/_context.md` — **plain, warm, modest, keep it small.**

## Where things live

- **The why** — `docs/product-design/001-problem-and-stakeholders.md` … `010-design-language.md`.
- **The stack (read before coding)** — `docs/architecture/001-stack-decisions.md`. What we build with and *why*, so you don't re-derive it.
- **The what (how the code works today)** — `docs/technical/002-current-implementation.md`. Module map, endpoints, SSE vocabulary.
- **Running a data pack** — `docs/technical/001-information-manager-instructions.md`. The operator guide: connecting a dbt project, classification, skins.
- **The plan & the work** — `docs/planning/`: `_about.md` (how the planning system works), `Betting Table.md` (blocks in execution order), `In Cycle.md` (what's being built right now), `blocks/`, `pitches/`.
- **Tone** — `docs/_context.md`. Applies to all prose, UI copy, and commit messages.

## How we work

Adapted Shape Up–style: **blocks** (top-level, in order) → **pitches** (work units bounded by an explicit *out of scope* and a one-sentence *cut line* — not time estimates). Pitches are co-written by Luk + Claude before building. Two skills run the cycle: `start-pitch` (enter) and `ship-pitch` (leave + release).

Start at `docs/planning/In Cycle.md` to see the current pitch.

## Repo layout

```
apps/
  api/   # Python 3.13 backend (uv): runtime, semantic-layer module, CLI
  web/   # React + TS + Vite SPA (plain CSS, no Tailwind), served by the backend
examples/
  cheese/  # bundled dbt + DuckDB reference pack
docs/    # design, architecture, planning (the source of truth for intent)
```

## Code conventions

**Backend (`apps/api/src/humbert/`)** — flat, one module per concern (`engine`, `semantic`, `orchestrator`, `notebook`, `chart`, `theme`, `config`, `cli`), plus the `server/` package (app factory in `server/__init__.py`, shared state in `server/state.py`, one file per concern under `server/routes/` with its Pydantic request/response models co-located, Cell→wire mapping in `server/wire.py`). No new packages until a module outgrows one file. mypy is strict and covers tests; ruff rules are E/F/I/UP/B/SIM, line length 100.

**Two seams, never crossed:**
- only `engine.py` names or shells out to dbt / `mf`;
- only `orchestrator.py` imports `pydantic_ai`.

Everything else speaks Humbert's terms — metrics, dimensions, selections, cells.

**Frontend (`apps/web/src/`)** — no Tailwind, no router. Plain CSS: design tokens as CSS variables in `styles.css` (`[data-theme]` blocks); components never hardcode colours or fonts (read tokens via `cssVar()` when JS needs them). User-facing strings go through `t()` in `src/locales/` — add both `en` and `nl`. API calls go through `src/utils/api.ts` (same-origin, opt-in retry); not-yet-built features hide behind `FEATURES` in `src/config.ts`. Cross-cutting state logic lives in `src/hooks/`.

**Tests** — one `tests/test_<module>.py` per backend module. The orchestrator is tested with PydanticAI's `TestModel`/`FunctionModel` — CI never calls a real LLM, and never runs dbt.

## Gates

Before committing non-trivial work, run the `local-gates` skill (ruff, ruff format, mypy, pytest, frontend build). CI runs the same.

```bash
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd apps/web && npm run build
```
