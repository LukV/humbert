---
project: humbert
type: planning-block
block: evaluation
status: active
updated: 2026-06-07
---
# Block 5 — Evaluation

How the semantic layer proves it can be trusted: a set of real questions whose correct answers are known in advance and frozen, run through the system and compared. This is offline evaluation ([[../../product-design/005-evaluation]]) — the regression guard, and the place model quality gets compared (the model-agnostic promise from [[../../architecture/001-stack-decisions]] cashes out here, against ground truth rather than vibes).

It comes last in v0 because it measures the other blocks: it needs the semantic layer (block 1) to run questions through, and typed refusals (block 3) to score the should-not-answer items.

**Done enough:** `humbert eval` reads the set from `pack/tests/`, runs each item through the semantic layer, compares the result to the frozen answer, and prints **two** numbers — answer accuracy and refusal accuracy. Run by hand now; the same command runs in CI later, on any change to the pack.

Design: [[../../product-design/005-evaluation]]. Related: [[../../product-design/008-information-manager]] (the IM curates the set and the column mapping).

## Open design items

- **Grader comparison rules** — canonical forms, rounding/precision, how an empty value is treated. The one place comparison must be pinned down precisely, so the score measures correctness not formatting. Settled when built.
- **Client template → column mapping** — turning the client's business-term question + frozen table + source into something the runner can execute is the IM's curation, not the client's job. The mapping shape lives here; the IM workflow that produces it is the later slot ([[../../product-design/008-information-manager]]).

## Pitches

### Eval runner — *chunky*

Reads the set from `pack/tests/` — each item carries the question (analyst's words), the correct answer as a frozen table (columns + rows, no prose, at one peilmoment), and a source reference. Runs each question through the semantic layer and collects the result against the frozen answer.

*Cut line:* `humbert eval` runs every item in `pack/tests/` and reports per-item pass/fail against the frozen tables.

### The grader — *medium*

The comparison itself: two results match when the same grouping produces the same rows and the numbers agree to a stated precision. Canonical forms, rounding, empty handling — pinned down here.

*Cut line:* a deterministic comparison that two equal-but-differently-formatted results agree on.

### Two-score report — *small*

Report the distinction that matters, never averaged into one number: **answer accuracy** (of questions that should be answered, the share whose result matches) and **refusal accuracy** (of questions that should be refused, the share correctly declined; whether it refused for the *right reason* recorded separately).

*Cut line:* the run prints both scores, with should-answer and should-refuse items counted separately.

### Model comparison — *medium*

Run the same frozen set across models/providers and report the two scores per model — the apples-to-apples quality comparison the model-agnostic design defers to here.

*Cut line:* `humbert eval` can run the set under a named model and print its two scores, so two models can be compared on the same set.

## Dependencies

Needs block 1 (the semantic layer and `pack/tests/`) and block 3 (typed refusals, for refusal accuracy). CI integration (run on every pack change) is a follow-on once the runner is stable. Distinct from block 4: evaluation is correctness against ground truth; telemetry is what happened in the wild.
