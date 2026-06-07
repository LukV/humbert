---
project: humbert
type: planning-block
block: telemetry
status: active
updated: 2026-06-07
---
# Block 4 — Telemetry

What actually happens when people use Humbert, recorded locally and small. Telemetry observes the loop blocks 2 and 3 produce — answered, refused, errored, timed out — so there's nothing to observe until they exist. It is system-initiated, local, append-only, and not personal. This is [[../../product-design/007-telemetry]] verbatim.

**Done enough:** every finalised cell appends one structured event to `~/.humbert/telemetry/events.jsonl`, and `humbert --stats` reads the log back into aggregates. No dashboard, no phone-home, no user feedback.

Design: [[../../product-design/007-telemetry]].

## Open design items

None significant — the event shape and the stats output are specified in the design note. The one judgement is exactly where the cell-finalised boundary sits in block 2's code (the emit point), which can be sketched while block 2 is in flight.

## Pitches

### Runtime event emission — *medium*

At the cell-finalised boundary, emit one event: `{ event_id, cell_id, install_id, timestamp, kind, model, agent_steps, retry_count, diagnostics, latency_ms }`. `kind` ∈ `answered | empty_result | sql_error | parse_error | timeout | retry_exhausted | validation_failed`. A refusal is a finalised cell too — its typed status (block 3) rides in `diagnostics`. The event carries `cell_id`, **never the question text** — the words stay in the notebook. Append one JSON object per line.

*Cut line:* every finalised cell — answered or refused or errored — writes one correct line to `events.jsonl`.

*Out of scope:* any `feedback.jsonl` — there is no user feedback (no thumbs, no ratings). The signal we trust is what the system did.

### `humbert --stats` — *medium*

One command reads the log and prints aggregates: counts by `kind`, error and refusal rates, agent steps and latency, over the last `--days N` (all of it by default). Enough to see the shape of real use without a dashboard.

*Cut line:* `humbert --stats [--days N]` prints the counts-by-kind and the error/refusal rates from the log.

## Dependencies

Needs blocks 2 and 3 (outcomes to log; refusals to type). Feeds the later **Information-manager workflow** slot (`empty_result` and refusals are the backlog of what to define next) and gives block 3 the data to tune certainty thresholds against. Not evaluation — there's no ground truth here, only what happened.
