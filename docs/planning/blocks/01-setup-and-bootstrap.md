---
project: humbert
type: planning-block
block: setup
status: active
updated: 2026-06-07
---
# Block 1 — Setup, Bootstrap & Semantic Layer

The ground floor. Nothing else can be built or tested until the project stands up and a question can reach governed data. This block does three things: scaffolds the repo and its discipline, builds the CLI path (`init` → `connect` → `start`), and stands up the **semantic-layer module** ([[../../product-design/004-semantic-layer]]) so Tier 1 has a vocabulary to read.

A slimmed port of `lumen/README.md` is the starting point for the CLI and the project shape — but `connect` now points at a dbt project (MetricFlow), not a raw database.

**Done enough:** `humbert init` scaffolds a project; `humbert connect` attaches a dbt + MetricFlow source and the semantic-layer module exposes its metrics and dimensions; `humbert start` runs. No notebook UI yet — that's block 2. The semantic layer can answer "what metrics and dimensions exist, and does this proposed selection resolve against them?" — the propose-then-validate interface block 2 will call.

Design: [[../../product-design/004-semantic-layer]]. Stack: [[../../architecture/001-stack-decisions]].

## Open design items
- **Agent framework** (PydanticAI?) — decide here; it shapes block 2. [[../../architecture/001-stack-decisions]].
- **Next.js vs plain React/Vite** for the frontend shell.
- **Skin swap mechanism** — runtime CSS-variable swap (recommended) vs build-time bundles, and where the per-skin token files live. The default **Humbert** skin plus a **Proef** skin (CJM's fonts/colours/name) is the v0 target; selection is by `settings.theme`. See [[../../architecture/001-stack-decisions#Skinning — per-client design system]].
- **Pack physical layout** — the pack is the governed slice from the marts up, in one dbt project; confirm the `pack/` directory shape (`domain/ context/ introspection/ tests/`).

## Pitches

### Project bootstrap — *chunky*

Repo layout (Python backend, React/TS/Tailwind frontend), Git, GitHub CI, QA instructions, and the Claude Skills that run the cycle (`start-pitch`, `ship-pitch`, plus any project-specific ones). The architecture note ([[../../architecture/001-stack-decisions]]) already exists — this wires the repo to match it and to point back at this planning surface (a `CLAUDE.md` "read first" pointer, as Lumen did).

*Cut line:* a repo that builds, lints, and runs CI green on an empty skeleton, with `CLAUDE.md` pointing at the design + planning notes.

### CLI — `init` / `connect` / `start` — *medium*

The three commands. `init` scaffolds a project and its `~/.humbert/` config entry. `connect` attaches a dbt + MetricFlow source (writes a connection block, sets `active_connection`, points at the pack). `start` boots the runtime. Persistence layout per [[../../architecture/001-stack-decisions]].

*Cut line:* `init` → `connect` to one dbt project → `start` boots, against the example source.

### Semantic-layer module — *chunky*

The in-process module behind the whole loop. Discovers MetricFlow metrics and dimensions, exposes the available vocabulary to the planner, and implements **propose-then-validate**: a proposed selection (metric + dimensions + filters) is checked against what exists before it compiles. Unknown names don't become queries here — they fall through (block 3's concern). Nothing — warehouse handle, raw SQL — leaks past the interface.

*Cut line:* given a valid selection, the module compiles and runs it via MetricFlow and returns rows; given an invalid one, it reports the unknown name. No fallback, no UI.

*Out of scope:* the Tier-2 governed fallback (block 2) and refusal (block 3).

### Pack scaffolding — *medium*

The pack directory: `domain/` (dbt semantic models + `meta:` labels, aliases, classification), `context/` (glossary, source notes, pitfalls), `introspection/` (cached schema/profiling), `tests/` (evaluation set — filled in block 5). Plus the **public-only guard**: the pack build refuses to expose anything not classified `open` in dbt `meta:`.

*Cut line:* a pack that loads, with the open-only classification guard enforced on build.

## Dependencies

None up the chain. Everything downstream depends on this block: block 2 needs the connection and the semantic-layer module; block 5 reads `pack/tests/`. The agent-framework and frontend-shell decisions made here set the terms for block 2.
