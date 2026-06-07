---
project: humbert
type: planning-index
status: active
updated: 2026-06-07
---
# Betting Table

The index of blocks, in execution order. Each block is a substantial area of work with its own dependencies, framings, and pitch list. Read [[_about]] for how the planning system works. The current cycle is in [[In Cycle]]. The "what shipped" record is `pitches/shipped/`.

The goal across these blocks: **a working v0 of Humbert** — a notebook that connects to a dbt + MetricFlow source, answers a descriptive question end to end (question → cell → SQL → chart + narrative), refuses honestly when it can't, records what happened, and can be measured against frozen reference answers. Local-first, small footprint, no hosting.

## Blocks

| # | Block | Status | Where the pitches live |
|---|-------|--------|------------------------|
| 1 | Setup, Bootstrap & Semantic Layer | not started | [[blocks/01-setup-and-bootstrap]] |
| 2 | Notebook + Orchestration | not started | [[blocks/02-notebook-and-orchestration]] |
| 3 | Honest Uncertainty | not started | [[blocks/03-honest-uncertainty]] |
| 4 | Telemetry | not started | [[blocks/04-telemetry]] |
| 5 | Evaluation | not started | [[blocks/05-evaluation]] |

The numbers are the order. Finish a block before opening the next; the only safe parallel is the chart theme inside block 2, and sketching telemetry's event shape while block 2 is in flight. Each block note carries its own dependencies.

## Out of scope for v0
The binding rule: **anything not described in the design notes is out of scope.** Three deferrals are worth naming explicitly, because someone might assume they're in:

- **A data-model / pack explorer UI** — a surface that shows the user the semantic layer's scope: entities, metrics, relations, completeness, so they can see what Humbert can and can't answer. Lumen put real effort into this (its "Datamodel" view); v0 has no such screen. The pack is curated in files, not browsed in the UI.
- **Policy enforcement** — access control, masking, disclosure refusals. v0 runs on open data only; sensitivity rides in dbt `meta:` but nothing is enforced ([[../product-design/004-semantic-layer]], [[../product-design/006-honest-uncertainty]]).
- **Hosting** — cloud, multi-tenant, accounts. Humbert is local-first ([[../product-design/003-design-pillars]]).

## Later — gated slots (not yet blocks)

Framed in the design notes, not yet promoted to blocks. They open once v0 stands.

- **Brief (publication)** — render validated cells + connective prose to a static HTML file. Design: [[../product-design/002-product-forms]]. Gated on the Notebook and cell validation landing.
- **Information-manager workflow** — *document* how the IM runs Humbert day to day: the curation loop, reading refusals as a backlog, defining metrics on real demand. **Documentation, not UI** — no curation screens in scope. Design: [[../product-design/008-information-manager]] (itself still a skeleton to finish).
- **Design-language polish** — the full visual system from the mockups, beyond the beautiful defaults that ship in block 2. Design: [[../product-design/010-design-language]].

The semantic layer's *growth* — richer metric coverage — isn't a block. It happens through the IM loop on real demand (refusals and telemetry signal what to define next), not as a one-off build.

## How a block is structured

Each block note carries:

- A **framing** — what this block is, why it matters, what "done enough" looks like.
- **Open design items** when relevant — points where the design hasn't settled (cross-referenced back to the design notes).
- **Pitches** — pitch-sized work units, each with a cut line and enough detail to act on.
- **Dependencies** — what this block needs from other blocks, and what other blocks need from this one.

A pitch on a block note is a **slot** until a corresponding note exists under `pitches/`. The slot says enough to recognise the work; the pitch note says enough to start it. Most slots will never need a full pitch note — they'll just get built directly when the slot's framing is sufficient.

## How to use this

1. The block numbers are the order. Start at 1, finish blocks in sequence.
2. Skim the block note for the area you're working in.
3. When you start a pitch, run `start-pitch`: set the pitch frontmatter to `status: in-cycle`, add it to [[In Cycle]].
4. When you finish, run `ship-pitch`: move the pitch note to `pitches/shipped/` with a `shipped_on:` date and a one-paragraph "what actually happened".

If a pitch slot stops being worth doing, strike it through on the block note with a one-line note on *why*. The dead pitches are part of the record.

## Open design items vs pitches

Design questions still in motion are **not** pitches. They live as open items inside the relevant block, or back in the design notes. A pitch can be *gated* on a design item landing; the design item itself is not a pitch. Five-minute jobs are also not pitches — just do them.

## Working with Claude Code

The pitches here are written by the dev team — Luk and Claude Code together — so a block is the right place to start a design conversation, not just a build. The pitch note frames the edges (out of scope, cut line); the solution gets designed inside them. Most pitches are sized for one or two evening sessions. If the work wants to grow past the cut line, defer it to the next pitch and finish this one.

[[../architecture/001-stack-decisions]] is what Claude reads on day one to understand the tech choices without re-deriving them.
