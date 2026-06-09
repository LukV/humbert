---
project: humbert
type: planning-block
block: honest-uncertainty
status: active
updated: 2026-06-07
---
# Block 3 — Honest Uncertainty

Tier 3: refusal as a named cell state, and the certainty score that grades every answer. This operationalises design pillar 3 and [[../../product-design/006-honest-uncertainty]] inside the cell. It comes after the loop because refusal only means something once there's an answer path to refuse *instead of* — a clean "I can't answer that" is worth more than a confident wrong number.

**Done enough:** when no tier can reach a question, the cell shows a **typed** refusal with a short message and a redirect to what's nearby — never a guess buried in narrative. Out-of-scope questions (causal, prospective, advisory, judgement about a person or org) are refused without trying. A certainty score is stored on the cell and shapes the answer: plain / caveat / ask / refuse.

Design: [[../../product-design/006-honest-uncertainty]], [[../../product-design/009-orchestration]].

## Open design items

- **Certainty thresholds** — where high/medium/low/floor sit. Tune against telemetry (block 4) once there's real data; start conservative to avoid over-refusal.
- **The clarifying-question path** — at "low", ask one question instead of answering. Confirm the interaction.

## Follow-ups carried in

- **Engine-error shaping.** Surfaced by the two-call-orchestration pitch ([[../pitches/shipped/two-call-orchestration]]): when a query reaches the engine and `mf` fails (a malformed filter, a binder error), the raw `mf` traceback — spinner chars, stack trace, "report a bug" footer — is dumped at the user verbatim. That's the wrong register. A failed *run* (as opposed to a failed *resolve*, which is already clean) should become a short, typed, human message in the same family as a refusal — this is where error-shaping belongs, alongside the refusal state's copy. Not a guess buried in narrative, not a stack trace either.

## Pitches

### Refusal as a cell state — *medium*

A first-class "no answer" state alongside chart-with-narrative. Typed status — v0 ships `UNSUPPORTED_QUESTION` (the list is owned and extended by the runtime; `ACCESS_DENIED` etc. wait for policy, which is out of scope). The message explains what's missing without leaking protected metadata, and points to what *is* nearby. Rendered as a recognised state, not an apology.

*Cut line:* a question no tier can reach renders as a typed `UNSUPPORTED_QUESTION` cell with a redirect.

### Out-of-scope gate — *medium*

Detect and refuse the question kinds outside the current descriptive depth — causal ("why"), prospective ("what if"), advisory ("what should we do"), and judgements about individual people or organisations — *without* trying to answer. The allowed/refused table in [[../../product-design/006-honest-uncertainty]] is the spec.

*Cut line:* the four out-of-scope kinds are refused up front with the right typed reason.

### Certainty score — *chunky*

A single score per answer that decides the tier and shapes the output: **high** answer plainly, **medium** surface the assumption (synonym read, fallback source), **low** caveat or ask one question, **floor** refuse with a redirect. Stored on the cell so a reproduced answer carries how sure Humbert was and which tier produced it.

*Cut line:* every cell stores a certainty score, and the four bands visibly change the answer's presentation.

## Dependencies

Needs block 2 (an answer path to refuse instead of, and the cell to carry the score and the refusal state). Feeds block 4 (the typed refusal travels in the telemetry event's `diagnostics`) and block 5 (refusal accuracy can't be measured without typed refusals). The certainty thresholds get tuned once block 4's telemetry is observable.
