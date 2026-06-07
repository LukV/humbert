---
project: humbert
type: pitch
status: shipped
block: setup
appetite: chunky
created: 2026-06-07
started: 2026-06-07
shipped_on: 2026-06-07
---
# Project bootstrap

## Problem

There is no repo yet — only design notes, planning notes, an architecture note, and a few loose files (`.cz.toml`, `.gitignore`, `README.md`, `.claude/`). Nothing builds, nothing lints, there is no CI, and the two skills that run the cycle (`start-pitch`, `ship-pitch`) point at Lumen-shaped paths. Every other block depends on this one: block 1's CLI and semantic-layer module have nowhere to live, and the quality gates everything is checked against don't run. This pitch lays the ground floor — the repo, its discipline, and a green build — so the first real feature has a place to land.

## Sketch

A monorepo matching the `.gitignore` that's already here (`apps/api/`, `apps/web/`, `apps/ios/` later) and the stack note ([[../../architecture/001-stack-decisions]]).

### Layout

```
humbert/
  apps/
    api/                  # Python backend, uv-managed
      pyproject.toml      # ruff, mypy (strict), pytest config
      src/humbert/        # the package (CLI entry point lands in the next pitch)
        __init__.py
      tests/
    web/                  # React + TS + Vite + Tailwind v4 SPA
      package.json        # "build": "tsc && vite build"
      index.html          # <html data-skin="humbert"> for now (config-driven later)
      vite.config.ts      # dev proxy /api → Python
      src/
        main.tsx
        styles/
          theme.css       # @theme: token names + Humbert (reference) defaults
          skins/
            proef.css     # [data-skin="proef"] stub overrides — proves the swap
  .github/workflows/ci.yml
  CLAUDE.md               # "read first" → architecture + planning + tone
  .cz.toml .gitignore README.md   # already present
```

### The toolchain is whatever makes the gates green

The gates are already specified by the `local-gates` skill: `ruff check`, `ruff format --check`, `mypy` (strict), `pytest`, and the frontend `tsc && vite build`. Bootstrap makes all five pass on a skeleton. That fixes the toolchain without re-deciding it: uv + ruff + mypy + pytest on the Python side; Vite + TypeScript + Tailwind v4 on the web side.

### Realign `local-gates` to the real layout

The skill is still a verbatim Lumen port — `mypy lumen/`, `pytest tests/`, `cd frontend && npm run build`. Repoint it at `apps/api/` and `apps/web/` (and `cd` accordingly) so the documented gates match the repo. Small, but part of "the repo's discipline actually runs."

### CI mirrors the gates

One `ci.yml` with two jobs — Python (ruff, mypy, pytest via uv) and web (npm ci, build) — running the same commands `local-gates` runs locally. Green on the skeleton is the bar.

### Skin plumbing, default skin, stub second skin

Land the CSS-variable structure from the stack note: `theme.css` declaring token names + Humbert defaults, a stub `proef.css` overriding a handful of tokens to prove the runtime swap works. Components written against semantic names from the first line. `data-skin` is hard-coded to `humbert` in `index.html` for now; the *config-driven* selection (reading `settings.theme`, server-injecting the attribute) wires up in the CLI pitch when `config.json` is first read — a clean seam, not a gap.

### CLAUDE.md as the read-first pointer

As Lumen did: a short root `CLAUDE.md` pointing at [[../../architecture/001-stack-decisions]] (the stack), [[../_about]] + [[../Betting Table]] (the planning surface), and [[../../_context]] (tone). The map a fresh session reads on day one, not a duplicate of any of them.

## Cut line

A repo that builds, lints, type-checks, tests, and runs CI green on an empty skeleton, with `CLAUDE.md` pointing at the design + planning notes.

## Out of scope

- **The CLI commands** `init` / `connect` / `start` — next pitch. Bootstrap leaves a place for the entry point, not the commands.
- **The semantic-layer module** and **pack scaffolding** — their own pitches in this block.
- **Config (`config.json`) reading and `~/.humbert/` persistence** — arrives with the CLI pitch; bootstrap hard-codes `data-skin="humbert"`.
- **Config-driven skin selection and server-side `data-skin` injection** — gated on config existing; the static default is enough to prove the plumbing.
- **The full Proef brand** (real fonts/colours/assets) — only a stub skin to prove the swap mechanism.
- **Any notebook UI, API contract, or backend↔frontend payload** beyond what a green build needs (a health route at most) — block 2.
- **Agent framework (PydanticAI) choice** — needed for block 2, not forced by bootstrap.

## Risks / unknowns

- **Python version vs the dbt/MetricFlow stack — decided: 3.13.** Lumen ran 3.14, but the whole product routes through dbt + MetricFlow (and likely PydanticAI later), and dbt-core support tends to lag new Python releases. Pinning 3.14 risked blocking the semantic-layer pitch; 3.13 is the floor everything else builds on, chosen for dbt/MetricFlow headroom over newest-Python.
- **Tailwind v4 `@theme` + runtime skin swap.** The `:root` vs `[data-skin]` source-order behaviour (stack note) should be verified in a real v4 build, not assumed — the stub Proef skin is partly there to catch this early.
- **Monorepo CI shape.** Two jobs in one workflow vs a matrix; uv caching; Node caching. Minor, but worth getting clean once so later pitches inherit it.
- **uv project structure.** Single package under `apps/api/` vs a uv workspace. Lean single package now; revisit only if a second Python package appears.

## Related

- [[../../architecture/001-stack-decisions]] — the stack and the Vite / skin decisions this pitch forced.
- [[../blocks/01-setup-and-bootstrap]] — the block; CLI, semantic-layer module, and pack scaffolding are its sibling pitches.
- [[../../product-design/003-design-pillars]] — local-first, open source (the why behind the shape).
- [[../../_context]] — tone and "keep it small".

---

## What actually happened

Landed the monorepo ground floor: `apps/api/` (Python 3.13, uv, ruff + mypy strict + pytest, stub `humbert` CLI entry point) and `apps/web/` (React 19 + TS + Vite 7 + Tailwind v4 SPA) both building green, plus `.github/workflows/ci.yml` mirroring the local gates, a read-first `CLAUDE.md`, and the `local-gates` skill realigned off its Lumen paths. We added on top of what was pitched the OSS license (Apache 2.0) and merged the READMEs to only one at the root of the repo.
