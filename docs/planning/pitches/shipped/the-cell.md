---
project: humbert
type: pitch
status: shipped
block: notebook
appetite: chunky
created: 2026-06-09
started: 2026-06-09
shipped_on: 2026-06-09
---
# The cell

## Problem

Tier 1 already produces a complete answer — narrative, reading, selection, rows, SQL, certainty — but it lives for the length of one `humbert ask` and then evaporates. There is nowhere for an answer to *be*. The product form is a notebook of reproducible cells ([[../../product-design/002-product-forms]]): you ask, you get a cell, you come back to it, it's still the same. None of the slots that follow — refinement forks a cell, validation freezes one, a brief publishes them — have a unit to operate on. And every answer today is a table; there is no record of *what shape* the answer is, so nothing downstream can know a trend should be a line and a breakdown a bar.

This pitch builds that unit: a cell that persists, re-renders faithfully from stored state, and carries the *right chart spec* for its answer shape.

## Sketch

The reproducible unit and the deterministic logic that fills it. No browser — exercised headlessly through the CLI. The render to screen is a later pitch; what this pitch guarantees is that a cell *holds everything a faithful render will need* and survives a reload unchanged.

### The data model

A `Cell` (pydantic) capturing what 002 lists, built from an `orchestrator.Answer` / `NoTier1Answer`:

- **Identity** — `id`, `title` (defaults to the question; editable later), `created_at`.
- **Question** — the verbatim question and the `reading` (how the words mapped to names).
- **Context** — `parent_id`, `refinement_of` (carried as fields now; *wiring* them is the Refinement pitch).
- **Query** — the `Selection`, the compiled `sql`, its `dialect`, and `edited: bool` (false now; SQL editing is Refinement).
- **Result** — `columns`, `rows`, row count. (Rows persisted for v0; a snapshot/re-run story is Validation's.)
- **Chart** — a Vega-Lite spec, or `null` when no chart fits.
- **Narrative** — the prose answer.
- **Metadata** — `model`, `tier`, `certainty`, and the refusal/no-Tier-1 status when there is one.

A **notebook** is an ordered list of cells, persisted as one `notebook.json` per connection under `projects/<name>/` — the same per-connection cache pattern `connect` already uses. One notebook per source for v0.

### The chart spec — correct, not yet beautiful

The cell's defining new piece: a **deterministic** chooser that reads the answer *shape* (the resolved `Selection` + the `Result`'s columns) and emits a Vega-Lite spec. No LLM, no extra call — it's a property of the data, so it's testable and honest:

- grouped by a **time** dimension → **line** (a trend)
- grouped by a **categorical** dimension, one measure → **bar** (a comparison)
- a **single value** (one row, one measure) → **number** (one big figure, no axes)
- otherwise, or nothing to plot → **no chart** (`null`) — a valid, un-forced outcome ([[../../product-design/002-product-forms]])

*Pie/share is deliberately out* — telling a share from a comparison needs a proportion signal the selection doesn't carry yet; bar is the honest default. The spec is *plain*: correct mark, encodings, and field types, with no theme. Making it beautiful (FT/Observable styling, the project Tailwind theme) is **Beautiful defaults**, which now shrinks to *theming a correct spec*.

### Headless surface

`humbert ask` persists each answer as a cell into the active notebook (and prints as it does today). Two thin readers prove faithful re-render from stored state:

- `humbert cells` — list the notebook's cells (id, title, tier, certainty).
- `humbert show <id>` — one cell in full, including its chart spec as JSON.

Reload the notebook and a cell reconstructs identically — same SQL, same rows, same spec. That round-trip *is* the cut line.

## Cut line

`humbert ask` persists a cell carrying narrative, reading, SQL, rows, tier, certainty, and a correct (plain) Vega-Lite spec for its shape; `humbert show <id>` re-renders it identically from `notebook.json` after a reload.

## Out of scope

- **Any browser render.** The React notebook UI is a later pitch; this is data model + CLI only.
- **Beautiful charts.** Theme, FT/Observable styling, project-Tailwind reading — that's Beautiful defaults. Here the spec is correct but unstyled.
- **Pie / share charts.** Deferred until there's a proportion signal to choose them honestly.
- **Editing** a cell's title or SQL, and **re-planning** — that's Refinement. The fields exist; the doors don't open here.
- **Validation / freezing / parameters / snapshots** — that's Validation. No promotion in this pitch.
- **Tier 2 / refusal cells.** Only Tier-1 answers and the plain no-Tier-1 stop become cells; styled refusal is block 3.

## Risks / unknowns

- **Chart-shape inference is coarser than the design's four categories.** We ship three (line / bar / number) + "no chart" and defer pie. Risk: a breakdown that's really a share renders as a bar. Acceptable for v0 — honest, just less expressive — and revisited when a proportion signal exists.
- **Persisting rows in `notebook.json`.** Fine for v0's small public result sets; a large result would bloat the file. The `max_result_rows` guard already caps this, but the snapshot/re-run story (Validation) is where this gets designed properly. Note it, don't solve it here.
- **`Cell` ↔ `orchestrator.Answer` overlap.** Two near-identical shapes risk drift. Decide the seam: the cell is the persisted record, the Answer is the in-flight result the orchestrator returns; the notebook layer maps one to the other (and adds id/title/timestamps/chart). Keep `orchestrator` unaware of persistence.
- **Where the chart builder lives.** A small module reading `Result` + `Selection` shape (not the orchestrator, which must stay the LLM seam; not `engine`, which is dbt-only). Likely its own `chart`/`notebook` module in the deterministic core.

## Related

- [[../../product-design/002-product-forms]] — the cell, its fields, its lifecycle
- [[../../product-design/009-orchestration]] — what produces a cell (the tiers)
- [[../../product-design/010-design-language]] — chart-type-by-shape intent
- [[../../architecture/001-stack-decisions]] — per-connection cache layout
- Prior pitches: [[shipped/two-call-orchestration]] (produces the `Answer` a cell wraps)

---

## What actually happened

This pitch introduced the key artefact — **The Cell** — which persists everything behind a question and its answer: the SQL, the results, the narrative, the certainty, the model. `humbert ask` now produces a cell in a notebook; the notebook is stored as `notebook.json` in `~/.humbert/projects/<project>/`, and `humbert cells` / `humbert show <id>` read it back faithfully. The deterministic chart-spec chooser landed here too — the right Vega-Lite *type* by answer shape (line / bar / number / none), beauty deferred — which is why chart-type selection moved out of Beautiful defaults into this pitch. No browser: it's all driven from the CLI, as scoped.

The surprise: `humbert ask "when did Germany take pole position, which country was first before that?"` returned ~1600 rows. The response *was* correct — but it made `notebook.json` very long. The rows-in-JSON bloat we flagged as a risk showed up for real on the first genuinely broad question. Left as-is for v0; the snapshot/freeze story (the **Validation** pitch) is where it gets solved properly.
