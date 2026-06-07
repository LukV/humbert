# Humbert 🐄 

A light, local-first analytics notebook for the cultural and youth sector. Ask a question of your data in plain language; get back a query, a chart, and a narrative you can stand behind. 

> Not "here is a dashboard." But "here is a good first answer to the question you just asked."

Humbert - short for the Human Camembert - is for the human analyst: the AI does the plumbing, the human keeps judgement and trust. It refuses honestly when the data can't support an answer, every number traces back to its query, and the same question gives the same answer.

## Status

Early. Building v0 — see [`docs/planning/Betting Table.md`](docs/planning/Betting%20Table.md) for the plan and [`docs/planning/In%20Cycle.md`](docs/planning/In%20Cycle.md) for what's in flight.

## Layout

```
apps/
  api/   # Python 3.13 backend (uv): runtime, semantic-layer module, CLI
  web/   # React + TS + Vite + Tailwind v4 SPA, served by the backend
docs/    # design, architecture, planning
```

## Develop

```bash
# Backend
cd apps/api
uv sync        # create the venv and install dev deps
uv run humbert # prints the version
```

## Gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

## Frontend
```bash
cd apps/web && npm install && npm run dev
```
