---
date: '2026-06-05'
tags:
  - telemetry
  - humbert
status: active
---
# Telemetry

[[005-evaluation|Evaluation]] measures correctness against known answers. Telemetry observes what actually happens when people use Humbert — live questions, in production, that no one has graded in advance. Evaluation tells us whether Humbert is right; telemetry tells us how it is being used and where it falls short in the wild.

In v0 telemetry is one thing: a record of what happened each time the system answered. It is system-initiated, local, and small.

## Runtime events

At the same boundary where a cell is finalised, the runtime emits one structured event describing what happened:

```
{ event_id, cell_id, install_id, timestamp,
  kind, model, agent_steps, retry_count,
  diagnostics, latency_ms }
```

`kind` is the outcome, one of:

```
answered | empty_result | sql_error | parse_error
timeout | retry_exhausted | validation_failed
```

A refusal is a finalised cell too; its typed status ([[006-honest-uncertainty]]) travels in `diagnostics`. The raw question stays in the notebook — the event carries the `cell_id`, not the words. That keeps the stream operational, not personal.

Events append, one JSON object per line, to:

```
~/.humbert/telemetry/events.jsonl
```

A local append-only file on the user's machine. Nothing is phoned home.

## No user feedback

There is no thumbs-up, no rating, no "was this helpful?". The signal we trust is what the system did — answered, refused, errored, timed out — not what someone clicked afterwards. It keeps the surface small and avoids asking users to grade work they came to Humbert to avoid doing.

The one human judgement that matters, an analyst validating an answer, belongs to evaluation, not here.

## Reading it back

A single command reads the log and prints the aggregates:

```
humbert --stats [--days N]
```

Counts by `kind`, error and refusal rates, agent steps and latency, over the last `N` days (all of it by default). Enough to see the shape of real use without a dashboard.

## What it feeds

- The curation loop: `empty_result` and refusals are the backlog of what to define next ([[008-information-manager]]).
- Trust in use: refusal and error rates, retries, latency drift over time.

## What it is not

- Not evaluation — there is no ground truth here, only what happened.
- Not surveillance — `install_id`, never a user; aggregate outcomes, no question text, no personal data.
