---
date: '2026-06-04'
tags:
  - refusal
  - honest-uncertainty
  - humbert
status: active
---
# Honest uncertainty

Refusal is a product feature, not a failure mode. Humbert would rather say what it cannot answer than answer convincingly and wrongly. Every dead end is a named status in the cell, with a short message — never a guess hidden in narrative.

It is the floor, not the first move. Humbert tries a defined metric, then a query over governed tables, and refuses only when neither can reach the question (see [[009-orchestration]]). And it is graded: a certainty score decides whether to answer plainly, answer with a caveat, ask, or refuse — so honesty is a dial, not a single yes or no.

## When the system refuses

In v0, Humbert refuses when:

- **no defined metric and no governed table** can reach the question — it may be answerable in principle, but nothing in the pack supports it yet
- the question is **out of scope** — causal, prospective, advisory, or a judgement about an individual person or organisation (refused without trying)

Access and disclosure refusals (you may not see this; the group is too small) belong to policy, which is out of scope for now — see [[004-semantic-layer]] and the Lumen notes.

## Typed refusals

Refusals are typed, so they can be measured ([[005-evaluation]]) and acted on. The runtime owns and extends the list. In v0 the main category is:

```
UNSUPPORTED_QUESTION
```

Later, when policy returns:

```
ACCESS_DENIED
SENSITIVE_PERSONAL_DATA
DISCLOSURE_BLOCKED
```

A refusal explains what is missing without leaking protected metadata, and points to what is nearby where it can — a named gap with a direction, not a closed door.

## What is in scope

The current depth answers descriptive "what" questions.

| Allowed at the current depth                                  |
| ------------------------------------------------------------- |
| *What do we see?* — observations                              |
| *How many?* — counts, sums, frequencies                       |
| *Which evolution?* — time series, trends                      |
| *Which distribution?* — distributions, percentages            |
| *Which comparison?* — differences between entities or periods |

| Refused (named explicitly, returned as a status)                                  |
| --------------------------------------------------------------------------------- |
| *Why?* — diagnostic                                                               |
| *What if?* — scenario                                                             |
| *What should we do?* — advisory                                                   |
| Causal / predictive                                                               |
| Judgement about individual people or organisations                                |
| (later, with policy) too-small group, sensitive attribute                         |

## Undefined is not unanswerable

A question with no matching metric is not a dead end by itself — it first tries the governed fallback. When even that cannot reach it, the refusal is the most useful one there is: the information manager's signal to define the metric. Either way, a question the pack could not answer cleanly is what grows the vocabulary, through the evaluation and telemetry loops. (See [[008-information-manager]].)
