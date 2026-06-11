---
project: humbert
type: planning-block
block: notebook
status: active
updated: 2026-06-11
---
# Block 2 — Notebook + Orchestration

The core loop and the point of v0. A question becomes a cell: plan → run → narrate, rendered as chart + narrative with the SQL visible underneath. This is product shape 1 ([[../../product-design/002-product-forms]]) wired to the orchestration contract ([[../../product-design/009-orchestration]]). Tier 1 (defined metrics, from block 1's module) and Tier 2 (governed fallback) both live here; Tier 3 (refusal) is block 3.

**Done enough:** ask a descriptive question against the connected source and get a cell — narrative, chart, and the query — with Tier 1 answering from defined metrics and Tier 2 falling back to governed SQL when no metric fits. You can refine (edit the question to re-plan, or the SQL to re-run) and validate (freeze the query). Beautiful defaults out of the box.

Design: [[../../product-design/002-product-forms]], [[../../product-design/009-orchestration]], [[../../product-design/003-design-pillars]]. Stack: [[../../architecture/001-stack-decisions]].

## Open design items

- **Certainty score** — its computation is shared with block 3 (it shapes the answer in both). Decide the shape here, since Tier 1/2 already need "how sure".
- ~~**Agent framework** carried from block 1 — this is the block that exercises it.~~ Settled: **PydanticAI** ([[../../architecture/001-stack-decisions]]), with the two-call-orchestration pitch.

## Pitches

### Two-call orchestration — Tier 1 — *chunky* — **shipped 2026-06-08**

The plan → run → narrate spine, Tier 1 path. The model proposes a MetricFlow selection; the module compiles and runs it (block 1); the model narrates over the returned rows, never inventing numbers. Surfaces the synonym read ("read *attendances* as **visits**") as a correctable line, not a hidden guess.

*Cut line:* a defined-metric question returns a correct narrated answer over real rows, with the selection shown.

Shipped as [[../pitches/shipped/two-call-orchestration]] — PydanticAI as the agent framework, `humbert ask` CLI, with stage indicators for progress. Left a follow-up for block 3: shaping raw `mf` run-errors into typed human messages.

### Tier 2 — governed fallback — *chunky* — **parked 2026-06-09**

> Parked behind **The cell** — Tier 1 proved responsive, and the cell is the backbone the rest of the block hangs off. The cell's data model already holds `tier`/`certainty`, so a Tier-2 cell is a value it can carry, not a schema change. Revisit once the cell exists; its **Tier-2 guard** open item in the ADR is parked with it.

When no metric fits, the model writes SQL over governed marts, flagged as computed-not-defined and less certain. The SQL is shown and editable. Includes the **Tier-2 guard** from [[../../architecture/001-stack-decisions]]: read-only, single statement, auto-`LIMIT`, `statement_timeout`, governed-marts only.

*Cut line:* a question with no matching metric returns a flagged fallback answer from governed SQL, within the guard rails.

*Out of scope:* promoting a fallback into a defined metric — that's the IM's decision, never the model's ([[../../product-design/004-semantic-layer]]).

### The cell — *chunky* — **shipped 2026-06-09**

The reproducible unit ([[../../product-design/002-product-forms]]): question + editable title, context (parent, refinement-of), SQL (text, dialect, edited?), result metadata, the Vega-Lite chart spec, the narrative, and metadata (model, tier, certainty). The data model, its persistence, and the deterministic chart-*spec* it carries — built and exercised headlessly (CLI); the browser render is a later pitch.

Shipped as [[../pitches/shipped/the-cell]] — `Cell` + `notebook.json` per connection, `humbert ask` persists, `cells` / `show` read back; deterministic chart-type chooser (line/bar/number/none). Surfaced the rows-in-JSON bloat for real (a 1600-row answer → a very long notebook); its fix lands with **Validation** (snapshot/freeze).

> Scope re-carve (2026-06-09): **chart-type selection** (the right Vega-Lite spec for the answer shape) lives *here*, not in Beautiful defaults — a correct spec is part of what a cell carries. Beautiful defaults shrinks to *theming* that spec.

*Cut line:* a cell that persists and re-renders faithfully from stored state — narrative, reading, SQL, rows, tier, certainty, and a correct (plain) chart spec.

### Beautiful defaults — *chunky* — **shipped 2026-06-10**

Grew from *medium* to *chunky*: this is where the **frontend is introduced**. It renders the two states from the assets — the empty notebook (ask box + suggested questions) and the draft cell — beautifully, with asking done in the browser. Built on the seeded skin tokens, skinnable from day one. The chart engine gains a fifth spec — **scatter** for two-measure answers — and otherwise just gets made lovely (Tufte-clean); chart-*type* selection already lives in [[../pitches/shipped/the-cell]]. Scatter needs a second cheese metric (`product_variety`), added here. Bars are capped at top-N so broad answers still render composed. Cells can be **deleted**; the footer shows `tier · certainty · model`. Pie/camembert and small multiples stay deferred — render a bar. This is pillar 5.

Shipped as [[../pitches/shipped/beautiful-defaults]] — the React notebook UI over `POST /api/ask` (SSE: stage events, reasoning stream, the finished cell), cell delete, light/dark, en/nl chrome.

*Cut line:* from an empty notebook, ask and get a beautifully-rendered, persisted draft cell; asking again appends a cell; deleting one removes it; it holds on the `proef` skin as well as the default.

*Later (parked here):* **vocabulary-derived suggestions** — the empty-state starter questions are hard-coded for cheese in this pitch; deriving them from the connected source's own metrics and dimensions (so any pack gets sensible prompts) is a refinement for once more than one source exists.

### Refinement — *medium*

Editing the question makes the model re-plan into a new query and re-run; editing the SQL re-runs directly (the model leaves the loop for that cell). Strong bias toward a **new cell** over editing in place — appending is reversible.

*Cut line:* both edit doors work and produce a new cell rather than mutating the old one.

### Validation — *medium*

Promote a draft cell to validated: freeze the query (no re-planning ever again), turn literals into parameters (re-run with a new year/gemeente = same query, new binds), and record who signed it, when, on which snapshot. The determinism guarantee ([[../../product-design/002-product-forms]]).

*Cut line:* a validated cell re-runs its frozen, parameterised query and records signer + snapshot.

*Carried in:* the rows-in-JSON bloat from [[../pitches/shipped/the-cell]] — a broad answer (1600 rows) makes `notebook.json` very long. The freeze/snapshot story here is where a cell stops storing raw rows inline and references a snapshot instead.

### Localization — en / nl — *medium*

Bilingual UI and narratives. The CLI pitch ([[../pitches/shipped/cli]]) seeds `settings.locale` (`en`/`nl`, default `en`), injects `<html lang>` on `start`, and shows it in `status`; this pitch builds the machinery: a frontend string catalog for UI chrome (labels, buttons, stage indicators, refusal copy) and **narrative language** — the planner/narrator writes its answer in the configured locale. Dutch number formatting is already a design-language rule ([[../../product-design/010-design-language]]). Lands here because there's little to translate until the notebook UI and narratives exist.

*Cut line:* with `locale: nl`, UI chrome and the generated narrative both render in Dutch; `en` is the default and unchanged.

*Out of scope:* locales beyond `en`/`nl`; translating user data or metric labels (those come from the pack's `meta:`).

## Dependencies

Needs block 1 (the connection and the semantic-layer module). Block 3 extends the cell with the refusal state and the certainty score's floor. Block 4 hooks the cell-finalised boundary to emit telemetry. Validation here is the precondition for the later **Brief** slot.
