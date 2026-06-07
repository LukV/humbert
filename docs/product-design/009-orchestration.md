---
date: 2026-06-05
project: humbert
status: draft
tags:
  - orchestration
  - certainty
  - refusal
  - humbert
---
# Orchestration

How a question becomes an answer, and why the answer can be trusted.

## The two-call contract

Every question runs through two model calls with deterministic work between them.

1. **Plan.** The question becomes a *selection*: defined metrics, dimensions, filters — or, when no metric fits, a query over governed tables.
2. **Run.** The engine compiles the plan to SQL and executes it. The numbers come from here.
3. **Narrate.** The model writes the answer over the rows that came back.

Two calls, not one, for a single reason: a model that wrote the numbers and the sentence in one breath could invent figures that read like facts. Splitting the work means the model never reports a number it has not seen the engine produce.

## Three tiers, in order of confidence

Not every question maps to a defined metric. Rather than answer too eagerly or refuse too quickly, Humbert tries three sources of truth in order, each less certain than the last. The order is borrowed from [[How anthropic enables ai analytics article|Anthropic's data team]], who run the same hierarchy.

| Tier | Source                               | Certainty                   |
| ---- | ------------------------------------ | --------------------------- |
| 1    | Defined metrics (the semantic layer) | High — the canonical number |
| 2    | Governed tables (the fallback)       | Lower — computed, not defined |
| 3    | Refusal                              | The honest floor            |

## Tier 1 — defined metrics

The question maps to metrics and dimensions that already exist. The model proposes a selection; the engine compiles it; the answer is the same number every other surface in the organisation would produce.

Matching is allowed to be loose. If an analyst asks about "attendances" and the defined metric is *visits*, the model maps one to the other — finding the right word in context is what a model is good at, and demanding the exact term would make Humbert brittle. The safeguard is not to forbid the match but to **show it**: the answer says it read *attendances* as **visits**, and the analyst can correct it. A surfaced, correctable reading is not a hidden guess.

## Tier 2 — governed fallback

No defined metric fits. Instead of stopping, the model reasons over governed tables — which models feed the concept, which share grain, which are deprecated — and writes SQL against them. The query is shown and can be edited. The answer is flagged for what it is: computed from underlying tables, not a defined metric, and less certain because of it.

One line holds firm here: **the model writes a query, never a definition.** A useful fallback answer is a signal for the information manager to define the metric, and that promotion is a person's decision, not the model's. Anthropic tried having a model author metric definitions and found it net-negative — the definitions looked plausible and smuggled in the very ambiguity the layer exists to remove. The vocabulary grows on real demand, through [[005-evaluation]] and [[007-telemetry]]; see also [[008-information-manager]].

## Tier 3 — refusal

When neither a defined metric nor a governed table can reach the question, Humbert refuses. When the question is out of scope — causal, prospective, advisory, or a judgement about a person or organisation — it refuses without trying. Refusal is the floor, not the default: a named status with a short message that points to what *is* nearby. See [[006-honest-uncertainty]].

## The certainty score

A single score decides the tier and shapes the answer.

- **High** — answer plainly.
- **Medium** — answer, but surface the assumption: the synonym read, or the fallback source.
- **Low** — answer with a visible caveat, or ask one clarifying question instead.
- **Floor** — refuse, with a redirect.

The score is stored on the cell, so a reproduced answer carries not just its query and numbers but how sure Humbert was and which tier produced it.

## What is deterministic, and what is not

Tier 1 is fully deterministic: same question, same data, same number. Tier 2 becomes reproducible the moment a cell is validated, because validation freezes the query (see [[002-product-forms]]). The narrative is prose over frozen numbers in either case — freeze the query and the figures, and treat the sentence as a view of them, not a separate guarantee.

## The query is always visible

Every tier shows its SQL, and every cell lets the analyst read and edit it. Tier 1 shows the compiled query; Tier 2 shows the generated one. Editing the SQL hands planning to the analyst: for that cell the model leaves the loop, and the edited query runs as written.

## Related

- [[002-product-forms]] — the cell, and what validation freezes
- [[004-semantic-layer]] — Tier 1, the defined vocabulary
- [[006-honest-uncertainty]] — refusal, the floor
- [[005-evaluation]] · [[007-telemetry]] — how the vocabulary grows
- [[How anthropic enables ai analytics article|Anthropic's analytics stack]] — the sources-of-truth hierarchy
