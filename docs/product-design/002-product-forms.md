---
date: 2026-06-04
project: humbert
status: draft
tags:
  - product-design
  - notebook
  - briefs
  - publication
---
# Two product forms

- **Notebook (exploration)** — The analyst asks, refines, drills down. The artifact is the conversation itself.
- **Brief (publication)** — A published document, narrative-led. A brief is what an analyst hands to the outside world once the exploration has earned the right to be shared.

# 1) Notebook

Humbert takes the shape of a notebook. It lets analysts work with data through natural language. Ask a question, get an answer; refine, drill down, change direction — all in conversation. Each question-and-answer pair becomes a cell in a notebook.

## The loop

A notebook is a question-and-answer engine with a tight loop at its center:

> **question → answer → evidence**

Every question produces an answer in three parts:
1. **A readable narrative** that interprets the result
2. **A visualization or table** that carries the analysis
3. **The underlying query or calculation** behind the answer

How that answer is produced — from a defined metric, from a query over governed tables, or as an honest refusal — and how sure Humbert is of it, is the orchestration described in [[009-orchestration]]. When no tier can reach the question, the answer is a named refusal, not a guess.

## Refinement, not restart

Analysis is rarely right on the first try. When the chart uses the wrong date field or aggregation, the user says "break that down by quarter instead" or clicks to adjust — they do not start over. The generated SQL is editable directly, and the notebook respects those edits in the ongoing conversation.

## The reproducible artifact: the cell

Every interaction produces a **cell** — the single unit of reproducibility. A cell carries:

- The **question** (verbatim) and an editable title.
- The **context**: parent cell, refinement-of relationship, position in the notebook.
- The **SQL**: query text, dialect, and whether the user edited it.
- The **result**: column metadata, execution time.
- The **chart**: a Vega-Lite spec. the chart *type* is what varies (a share is a pie, a comparison is a bart chart, a trend is a line, a count is one number). Some good answers need no chart at all; do not force one.
- The **narrative**: plain-language answer. One or two sentences, leading. Set in serif, because it is a reply, not a readout. Optionally a short reading: One line of context or caveat.
- **Metadata**: model name, the **tier** that produced the answer (defined metric, governed fallback, or refusal), the **certainty score**, agent steps, reasoning, and refusal status if any.

## Actions

![[notebook-cell.png]]

Three actions sit on a cell: validate, export, refine. Export bundles two things, the raw data and the answer (chart plus narrative). Refine is a follow-up.

## The lifecycle

A cell moves through two states. The path between them is what makes refinement an experiment you can roll back.

**Draft.** Authored by the LLM. Editing the question makes the LLM re-plan into a new query and re-run. Editing the SQL re-runs directly. Two doors to the same room, sized to the analyst.

**Validated.** A promotion, not a checkmark. Validation freezes the query: the LLM leaves the loop, and every future run executes that exact query, never a fresh plan. This is the determinism guarantee. The query's literals become parameters, so re-running with a new year or a new gemeente is the same query with new binds. Validation also records who signed it, when, and on which data snapshot. This is the only moment aubergine appears on the cell.

## Caveats

- Only the numbers are deterministic. The narrative is prose rendered over frozen figures, so freeze the query and the numbers and treat the sentence as a view of them, not a guarantee. 
- Scope for v0: only questions that can be expressed as SQL over data already in the platform. Anything outside that is an honest "I can't answer that," not a guess.
- **Strong** Bias toward a new cell rather than refining in place. Appending is reversible; quietly editing a frozen cell is not.

# 2) Brief

A notebook is a record of *how you got there*: drafts, refinements, dead ends. A brief is a publication of *what you can stand behind*, a **validated cell**. Validation already freezes the query, records who signed it, when, and on which snapshot. Publishing renders those validated cells for an outside reader.

A brief is **N ordered cells joined by connective prose**.
- The author's **connective prose** flows as plain serif paragraphs.
- Each included **cell** drops in as a self-contained, stamped figure: a count, a breakdown, a trend.

![[brief.png]]

Every cell still shows the question it answered and a `gevalideerd door … · snapshot` mark, so the reader can trace any number back to its calculation.

## How it works

In the notebook:
1. Mark cells to **include in the briefing**.
2. Write the **connective prose** as plain markdown cells between them.
3. Toggle from **work view** to **read view**: drafts hidden, SQL folded, only included cells and prose, set in serif.
The notebook already holds cells in order. The briefing is that order, filtered and dressed. 

## Versioned

The numbers and the prose freeze **together** at publication, so a sentence like “bijna de helft” can never quietly stop being true. Refreshing happens in the notebook, not in the publication. A refresh produces a new version of the briefing.

## Export

Publishing renders the N ordered cells and prose to a **static file** (HTML). No publishing backend, no hosting platform, no accounts.

- The permalink is a stable file path.
- Versions are `v1`, `v2`; each is its own file.
- Reading needs no login, because it is a file.
- Access is controlled by *where you put it*, not by an access-control system.

From the briefing, a reader can export the **data behind it**, not just read the numbers. That is **per cell.** The result set behind one figure, as CSV, plus that cell's answer.

## Open choices

1. **Provenance stamp: per cell or per briefing.** Per-cell is honest but gets noisy on a long briefing. A single briefing-level block (“alle cijfers gevalideerd door Lieven · snapshot 2026-03”) is calmer, but only works when every cell shares one signer and one snapshot. Keep per-cell only if briefings genuinely mix snapshots or signers.
2. **The question eyebrow: inline or in the appendix.** Showing each cell's question inline is maximal traceability, but the connective prose already introduces the figure, so it can read as redundant. The alternative is to move it to the appendix next to the SQL.
3. **Version note placement.** Fine in the footer for a short nota. For a heavily cited briefing it may belong near the `v2` badge at the top, since it is the citability mechanism.

## Caveats

- Frozen data can go stale. The honesty is the visible snapshot date and version; the reader always knows how old the numbers are.
- An export gives the publication's data, not the latest data. Newer numbers mean a new version.
- Scope for v0: a briefing can only contain what is already a validated cell. Nothing is computed at publish time.
