# CLAUDE.md

Read this first. It's a map, not a manual — it points at the notes that hold the detail, so a fresh session knows where to look before touching code.

## What Humbert is

A light, local-first analytics notebook for the cultural and youth sector. The product vision lives in `docs/product-design/` (`001`–`010`) and the tone that governs all writing in `docs/_context.md` — **plain, warm, modest, keep it small.**

## Where things live

- **The why** — `docs/product-design/001-problem-and-stakeholders.md` … `010-design-language.md`.
- **The stack (read before coding)** — `docs/architecture/001-stack-decisions.md`. What we build with and *why*, so you don't re-derive it.
- **The plan & the work** — `docs/planning/`: `_about.md` (how the planning system works), `Betting Table.md` (blocks in execution order), `In Cycle.md` (what's being built right now), `blocks/`, `pitches/`.
- **Tone** — `docs/_context.md`. Applies to all prose, UI copy, and commit messages.

## How we work

Adapted Shape Up–style: **blocks** (top-level, in order) → **pitches** (work units bounded by an explicit *out of scope* and a one-sentence *cut line* — not time estimates). Pitches are co-written by Luk + Claude before building. Two skills run the cycle: `start-pitch` (enter) and `ship-pitch` (leave + release).

Start at `docs/planning/In Cycle.md` to see the current pitch.

## Repo layout

```
apps/
  api/   # Python 3.13 backend (uv): runtime, semantic-layer module, CLI
  web/   # React + TS + Vite + Tailwind v4 SPA, served by the backend
docs/    # design, architecture, planning (the source of truth for intent)
```

## Gates

Before committing non-trivial work, run the `local-gates` skill (ruff, ruff format, mypy, pytest, frontend build). CI runs the same.

```bash
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd apps/web && npm run build
```
