---
project: humbert
type: pitch
status: shipped
block: notebook
appetite: chunky
created: 2026-06-09
started: 2026-06-09
shipped_on: 2026-06-10
---
 # Beautiful defaults

## Problem

The loop works and a cell persists, but the only way to meet either is a CLI table. There is no *surface* — nothing that looks like the product the design language describes ([[../../product-design/010-design-language]]): a calm page where the question becomes a serif narrative with a clean figure, and where an uncertain answer never looks as confident as a certain one. v0's whole promise is "a good first answer you can stand behind," and standing behind it is partly *visual*. This pitch introduces the frontend: from an empty notebook you ask a question and get back a beautifully-rendered draft cell, and you keep asking.

It is also where pillar 5 — *beautiful defaults* — first bites: the first chart must look composed with zero configuration, on the default skin and on any other.

## Sketch

The first real frontend, built on the skin mechanism the bootstrap pitch already seeded. Two states from the design assets: the **empty notebook** and the **draft cell**. Asking happens in the browser, in both. The chart engine gains **one new spec** — a **scatter** for two-measure answers (§6's bivariate case; the fifth shape after number / bar / line / no-chart) — and is otherwise unchanged: the cell already carries a correct Vega-Lite spec; this pitch makes it *look* right and renders it.

### Frontend foundation — skinnable from day one

- Build on the existing mechanism: Tailwind v4 `@theme` tokens + `:root[data-skin="…"]` overrides, `data-skin` injected server-side (no flash). No new skinning system — the notebook is built from token utilities (`bg-paper`, `text-ink`, `font-narrative`, the accent), so a skin swap cascades. The cut includes confirming the `proef` skin still renders the notebook cleanly.
- Self-host the three type registers (§4) via Fontsource (local-first, offline): **Source Serif 4** (narrative), **DM Sans** (UI/eyebrows/metadata), **JetBrains Mono** (SQL).
- Encode §5's colour contract as the palette: **aubergine = validation only** (so it does *not* appear on a draft), **amber = caution** (the accent figure, the medium-certainty chip), **neutral = absence**, and the FT/Observable **series palette** for data, which never includes the accent.

### The chart engine — one new spec, one beautiful-default cap

- **Scatter** joins the deterministic chooser ([[shipped/the-cell]]'s `chart.py`): a **two-measure** selection (`len(metrics) == 2`) plots each row as a point, `x = metric₁`, `y = metric₂`, optionally coloured by a single grouping dimension. This is §6's bivariate shape — the fifth alongside number / bar / line / no-chart.
- This needs a **second metric in the cheese pack** (it ships only `total_production`). This pitch adds `product_variety` — a count-distinct of `product` — so scatter is real and testable, and so the empty state can ask *"do countries that make more cheese also make more kinds of it?"*. (Small `cheese.yml` edit; the only change to the example data.)
- **Top-N cap on bars** — a beautiful default, not just a guard: a broad answer (the 1600-row case from [[shipped/the-cell]]) must still render composed, so a bar spec shows the **top N sorted** marks and the narrative carries the tail. The cell still *stores* its full rows (the snapshot fix is Validation's); this is purely what the figure shows.

### The read + ask API

- `GET /api/notebook` — the active connection's cells as JSON (the `Cell` model). Curl-able; the frontend renders from it and re-derives nothing.
- `POST /api/ask {question}` — runs the existing synchronous orchestrator (`build_model` → `discover_vocabulary` → `orchestrator.ask` → `notebook.record`) and returns the new cell. A no-Tier-1 result comes back as a calm `no_tier1` cell, not an error. Real errors (no key, engine failure) return a quiet message the UI can show. The server reads the API key from its own env and needs the `dbt` extra at runtime — same requirements as `humbert ask`.
- `DELETE /api/notebook/cells/{id}` — removes a cell from the active notebook (a `notebook.delete(...)` that loads → drops by id → saves). Curl-able; the frontend calls it from the cell's hover affordance. Idempotent — deleting an unknown id is a quiet no-op, not an error.

### The empty state

A calm first screen (§8 plain language, §9 motion restraint): the Humbert mark, one plain invitation, and the **ask box**. Beneath it, **suggested questions** as quiet clickable prompts that fill and submit the box — chosen so the first screen quietly shows the engine's range, **one per chart shape**, for the bundled cheese source:

- *Which countries produce the most cheese?* — a ranking → **bar**
- *How has cheese production evolved over the years?* — a trend → **line**
- *How much cheese did Germany produce in 2020?* — a single figure → **big number**
- *Do countries that make more cheese also make more kinds of it?* — two measures → **scatter** (needs the new `product_variety` metric)

These four become the clickable chips. The fifth shape — **no chart** — is honest but reads as "broken" if offered as a starter, so it isn't a chip; it surfaces organically when a question has no single shape (e.g. *"how has each country's production changed over the years?"* — grouped by country *and* year → narrative alone, no figure).

Static for v0 — **vocabulary-derived suggestions** (drawn from the connected source's metrics/dimensions rather than hard-coded for cheese) are a later refinement, parked under the Beautiful-defaults slot in [[../blocks/02-notebook-and-orchestration]].

### The draft cell

Faithful to the asset, governed by §2 progressive disclosure — **at rest a cell is its question, its narrative, and its figure**:

- **Question** as a quiet DM Sans eyebrow.
- **Narrative** in Source Serif 4, large and leading — the reply, with the **amber accent** on the key figure. This is also the chart's text alternative (§7), so it is never dropped.
- **The figure**: the stored Vega-Lite spec rendered (vega-embed / react-vega), themed **Tufte-clean** (§6) — no borders, no fill, no gridlines unless earned, a single baseline, sorted bars, direct labels where they fit. Bars are capped at the **top N** so a broad answer stays composed (see the chart-engine section). "No chart", "one big number", and now "scatter" are all first-class outcomes.
- A **Draft** pill; a single low metadata line (`tier · certainty · model`), with certainty shown per §1/§7 — high reads plainly, medium surfaces the correctable assumption visibly (not yet wired to a re-plan), never colour alone. The model name (e.g. `claude-opus-4-8`) sits last as quiet provenance — which engine answered.
- **View query** unfolds the SQL (JetBrains Mono) from a quiet affordance.
- **Delete** is reached for, not shown (§2) — a quiet hover affordance that calls `DELETE /api/notebook/cells/{id}` and drops the cell from the column. Unlike the action row below, this one *works*: removing a draft is reversible-by-re-asking, so it's safe to wire now.
- The **Validate / Export / Refine** row appears as the asset shows it but is **inert** — those doors open in the Refinement and Validation pitches. Rendering them disabled is the honest "not yet."

Asking again appends another draft cell below; the notebook is a column of cells.

## Cut line

From an empty notebook, ask a question in the browser (typed or from a suggestion) and get a beautifully-rendered draft cell — serif narrative with an accent figure, a Tufte-clean chart (bar / line / scatter / big number / none), a Draft pill, `tier · certainty · model`, and foldable SQL — that persists and re-renders on reload; asking again appends a cell; deleting one removes it; and it all holds together on the `proef` skin as well as the default.

## Out of scope

- **Validation** — no freeze / sign / parameters, no aubergine validated state. Draft only. ([[../pitches/the-cell]]'s sibling Validation pitch.)
- **Refinement** — Validate/Export/Refine are inert; editing the question or SQL and re-planning is the Refinement pitch.
- **Brief / read view / export / print stylesheet** (§10) — a later block.
- **Notebook-scale disclosure** (§2) — collapse-to-one-sentence, outline rail, inline sparklines. We render empty + a column of full draft cells; the scannable-column refinements come later.
- **Camembert / pie and small multiples** (§6) — render a bar; pie and cross-dimension multiples stay deferred (decided with Luk: "render bar, that's easy").
- **Dark mode** and the §-open *warm-vs-de-creamed paper* question — keep the current warm palette; don't resolve it here.
- **UI-string localization** — English now; the Localization pitch owns nl narratives + chrome.
- **Stage streaming over HTTP** — asking shows a loading state, not the per-stage progress the CLI emits.

## Risks / unknowns

- **Synchronous ask = a spinner over a slow call.** Acceptable for v0; the orchestrator is already sync and the stage-streaming story is deferred. The trade is a plain wait, not a blank one.
- **Tufte-clean Vega-Lite theming can rabbit-hole.** Cut to "clean and composed on the five spec types" (number / bar / line / scatter / none), not pixel-matching the asset. The series palette + no-gridlines + single-baseline config is the floor; polish above that is bonus, not commitment.
- **Broad answers are heavy — payload *and* render.** A 1600-row answer ([[shipped/the-cell]]) is both a big `notebook.json` / `/api/notebook` payload and an unreadable chart. The render side is handled here (top-N bar cap); the *payload* side is **not** — the cell still stores full rows inline, and the real fix is Validation's snapshot. Acceptable for v0; named so it isn't a surprise twice.
- **Inert action buttons can read as broken.** Mitigated by a visibly-disabled state; if it still feels wrong on review, we drop the row to just *View query* and let Refinement introduce it.
- **First real component tree + a chart dependency.** `App.tsx` is a skeleton today; this adds the notebook components and react-vega. Bounded to two states, but it is the frontend's first real build-out.
- **Runtime requirements move to the server.** Asking in-browser means `humbert start` must run with the API key and the `dbt` extra present — the same needs as the CLI, now on the long-running process. Worth saying plainly in the README.

## Related

- [[../../product-design/010-design-language]] — the rules this pitch renders (§§1, 2, 4, 5, 6, 7, 8, 9)
- [[../../product-design/002-product-forms]] — the cell at rest, the draft state
- [[../../product-design/003-design-pillars]] — pillar 5, beautiful defaults
- [[../../architecture/001-stack-decisions]] — the skin mechanism, the server
- Prior pitches: [[shipped/the-cell]] (the cell + chart spec this renders), [[shipped/two-call-orchestration]] (the loop `POST /api/ask` drives), [[shipped/cli]] (seeded `data-skin` + the proef skin)

---

## What actually happened

The first frontend — and the first time the product looks like itself. From an empty notebook you ask a question and get a cell back: a serif narrative with its figures emphasised, a Tufte-clean chart (bar / line / scatter / multi-line / big number / none), and the SQL, chart spec, and reasoning a click away in a code drawer, with a delete affordance. We went hard at it. The first build hit cosmetic issues, then poor UX, then wrong chart types — so we threw it away and **ported the frontend wholesale from Lumen**, which was better both technically and on UX. On top of that we hardened two things: stricter, deterministic chart selection (and a planner that reads *"per X"* as a grouping, not a second metric), and grasping intent — telling a fresh question from a follow-up, so *"add Italy"* refines the previous cell instead of starting over. To match Lumen we pulled **stage streaming over HTTP** into scope — it was explicitly *out* — replacing the synchronous ask with SSE progress events; we also laid the groundwork for **localisation** (nl/en strings) and shipped **dark mode**. Cut as planned: validation, SQL-refinement, the brief/read view, pie/camembert, small multiples. Watch: the pack/schema browser and SQL-editing are ported but gated behind feature flags until their backends land; suggestions are static (vocabulary-derived is parked); and the follow-up carry-forward is a prompt nudge, so the *reading* line is what surfaces a misread.
