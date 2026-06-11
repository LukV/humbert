---
name: local-gates
description: Run the full local quality gate sequence — ruff lint, ruff format check, mypy, pytest, frontend build (tsc + vite). Reports concise pass/fail per gate. Use when answering "did I break anything", "run the gates", "check before I push", or before authoring a commit on non-trivial changes.
---

# local-gates

Run all local quality gates in order. Concise output.

## When to use

- Before committing a non-trivial change.
- When the developer asks "did I break anything", "run the gates", "check before I push".
- After a non-trivial change to either backend or frontend code.

Single-file documentation tweaks don't need this.

## Steps

Run these commands in order. Report each gate's pass/fail concisely. **Continue to the next gate even on failure** so the full picture surfaces in one report; collect failures at the end.

Python gates run from `apps/api/` (uv-managed); the frontend gate runs from `apps/web/`.

1. `cd apps/api && uv run ruff check .` — Python lint
2. `uv run ruff format --check .` — Python format check (verify only; don't auto-format)
3. `uv run mypy` — Python type check (strict mode, zero errors expected; files configured in `pyproject.toml`)
4. `uv run pytest` — tests
5. `cd apps/web && npm run build` — frontend type check + build (the `build` script runs `tsc -b && vite build`, so this is also the TypeScript gate)

## Reporting shape

Successful run:

```
✓ ruff check
✓ ruff format
✓ mypy
✓ pytest — 167 passed
✓ frontend build

All gates passed.
```

With failures:

```
✓ ruff check
✗ ruff format — 2 files would be reformatted
✓ mypy
✗ pytest — 3 failed, 164 passed (see tests/test_orchestration.py::test_retry_loop)
✓ frontend build

2 gates failed. Run `uv run ruff format .` to fix formatting; run `uv run pytest tests/test_orchestration.py::test_retry_loop -v` for the test detail.
```

Always end with one line: either `All gates passed.` or `N gates failed.` plus the most useful next command.

## Don't

- Don't run gates one-at-a-time stopping at the first failure. Run them all, report together.
- Don't run gates in parallel — they share working state (mypy and pytest especially) and parallel output is hard to read.
- Don't run `pytest -v`, `pytest --cov`, or `mypy --verbose` by default. Concise output. If Luk wants verbose, he'll ask.
- Don't suggest code fixes after the report. This skill reports, period. Acting on failures is a separate decision.
- Don't run network-dependent tests or migrations as part of this — local gates only.
