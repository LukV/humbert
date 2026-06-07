---
project: humbert
type: planning-block
block: notebook
status: active
updated: 2026-06-07
---
# Block 2 — Notebook + Orchestration

The core loop and the point of v0. A question becomes a cell: plan → run → narrate, rendered as chart + narrative with the SQL visible underneath. This is product shape 1 ([[../../product-design/002-product-forms]]) wired to the orchestration contract ([[../../product-design/009-orchestration]]). Tier 1 (defined metrics, from block 1's module) and Tier 2 (governed fallback) both live here; Tier 3 (refusal) is block 3.

**Done enough:** ask a descriptive question against the connected source and get a cell — narrative, chart, and the query — with Tier 1 answering from defined metrics and Tier 2 falling back to governed SQL when no metric fits. You can refine (edit the question to re-plan, or the SQL to re-run) and validate (freeze the query). Beautiful defaults out of the box.

Design: [[../../product-design/002-product-forms]], [[../../product-design/009-orchestration]], [[../../product-design/003-design-pillars]]. Stack: [[../../architecture/001-stack-decisions]].

## Open design items

- **Certainty score** — its computation is shared with block 3 (it shapes the answer in both). Decide the shape here, since Tier 1/2 already need "how sure".
- **Agent framework** carried from block 1 — this is the block that exercises it.

## Pitches

### Two-call orchestration — Tier 1 — *chunky*

The plan → run → narrate spine, Tier 1 path. The model proposes a MetricFlow selection; the module compiles and runs it (block 1); the model narrates over the returned rows, never inventing numbers. Surfaces the synonym read ("read *attendances* as **visits**") as a correctable line, not a hidden guess.

*Cut line:* a defined-metric question returns a correct narrated answer over real rows, with the selection shown.

### Tier 2 — governed fallback — *chunky*

When no metric fits, the model writes SQL over governed marts, flagged as computed-not-defined and less certain. The SQL is shown and editable. Includes the **Tier-2 guard** from [[../../architecture/001-stack-decisions]]: read-only, single statement, auto-`LIMIT`, `statement_timeout`, governed-marts only.

*Cut line:* a question with no matching metric returns a flagged fallback answer from governed SQL, within the guard rails.

*Out of scope:* promoting a fallback into a defined metric — that's the IM's decision, never the model's ([[../../product-design/004-semantic-layer]]).

### The cell — *chunky*

The reproducible unit ([[../../product-design/002-product-forms]]): question + editable title, context (parent, refinement-of), SQL (text, dialect, edited?), result metadata, the Vega-Lite chart, the narrative (serif, leading), and metadata (model, tier, certainty, agent steps). The data model and its render.

*Cut line:* a cell that persists and re-renders faithfully from stored state — chart, narrative, SQL, tier.

### Beautiful defaults — *medium*

Chart-type selection by answer shape (share → pie, comparison → bar, trend → line, count → one number; some answers need no chart) and the FT / Observable-style theme as the default. Reads the per-project Tailwind theme. This is pillar 5, and it ships *with* the loop, not after.

*Cut line:* the four core chart types render beautifully on the default theme; "no chart" is a valid outcome.

### Refinement — *medium*

Editing the question makes the model re-plan into a new query and re-run; editing the SQL re-runs directly (the model leaves the loop for that cell). Strong bias toward a **new cell** over editing in place — appending is reversible.

*Cut line:* both edit doors work and produce a new cell rather than mutating the old one.

### Validation — *medium*

Promote a draft cell to validated: freeze the query (no re-planning ever again), turn literals into parameters (re-run with a new year/gemeente = same query, new binds), and record who signed it, when, on which snapshot. The determinism guarantee ([[../../product-design/002-product-forms]]).

*Cut line:* a validated cell re-runs its frozen, parameterised query and records signer + snapshot.

### Localization — en / nl — *medium*

Bilingual UI and narratives. The CLI pitch ([[../pitches/shipped/cli]]) seeds `settings.locale` (`en`/`nl`, default `en`), injects `<html lang>` on `start`, and shows it in `status`; this pitch builds the machinery: a frontend string catalog for UI chrome (labels, buttons, stage indicators, refusal copy) and **narrative language** — the planner/narrator writes its answer in the configured locale. Dutch number formatting is already a design-language rule ([[../../product-design/010-design-language]]). Lands here because there's little to translate until the notebook UI and narratives exist.

*Cut line:* with `locale: nl`, UI chrome and the generated narrative both render in Dutch; `en` is the default and unchanged.

*Out of scope:* locales beyond `en`/`nl`; translating user data or metric labels (those come from the pack's `meta:`).

## Dependencies

Needs block 1 (the connection and the semantic-layer module). Block 3 extends the cell with the refusal state and the certainty score's floor. Block 4 hooks the cell-finalised boundary to emit telemetry. Validation here is the precondition for the later **Brief** slot.
