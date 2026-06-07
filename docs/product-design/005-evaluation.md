---
date: '2026-06-05'
tags:
  - evaluation
  - humbert
status: active
---
# Offline evaluation

Offline evaluation is how the [[004-semantic-layer|semantic layer]] proves it can be trusted. It rests on a set of **real questions whose correct answer is known in advance and frozen** — the ground truth the system is measured against. The set is curated with the client, because only the sector knows which questions matter and what the right answer is.

It is offline by design. A passing set means the system has no obvious gaps on the questions we know to ask; it does not tell us how the live system performs in daily use. That is a separate measurement, read from [[007-telemetry|telemetry]], and not the job of this set.

## What each item carries

- **The question** in the analyst's own words, the way a colleague would actually ask it.
- **The correct answer as a table** — columns and rows, no prose — frozen at one reference moment (peilmoment).
- **The source**: a reference to machine-readable, structured data (a DWH table, Parquet, an API endpoint — not a PDF).

Per theme the set is a deliberate mix: a few simple single-source questions, a few harder ones that combine datasets or need a more involved metric, and two or three the system **should not answer** — the data is missing, or the question is out of scope (causal, prospective, advisory). The should-not-answer items matter as much as the rest: they test whether the system refuses when it ought to.

## How it runs

A single command reads the set from the domain pack (`pack/tests/`) and, for each item, runs the question through the semantic layer and compares the result to the frozen answer.

It is a **separate process, outside the software**. For now it is run by hand, alongside the solution; later the same command runs in CI, on any change to the pack. Either way the set is the regression guard — a change that quietly breaks a known-good answer is caught the next time it runs.

The cycle is plain: run the set, see where it falls short, fix the pack, run again.

## The score is two numbers, not one

A single percentage would average away the distinction that matters most: answering wrongly and answering when it should have refused are different failures.

- **Answer accuracy** — of the questions that should be answered, the share whose result matches the frozen answer.
- **Refusal accuracy** — of the questions that should be refused, the share the system correctly declined. Whether it refused for the right reason is recorded separately.

## What "compare" means

Two results match when the same grouping produces the same rows and the numbers agree to a stated precision. The exact rules — canonical forms, rounding, how an empty value is treated — are an implementation detail of the grader, settled when we build it, not here. Worth noting now, because this is the one place the comparison has to be pinned down precisely, so the score measures correctness and not formatting.

## Correctness is the IM's to define

The client delivers the question, the frozen table, and the source, in business terms. Turning that into something the command can run — mapping each reference column to a metric or dimension in the pack — is curation, and it lives on our side with the information manager. The client template stays business-facing. (See [[008-information-manager]].)

## Why it matters

Together these prove the three properties Proef is asked to demonstrate: it does not hallucinate (it refuses when the data falls short), it is deterministic (the same question on the same data gives the same answer), and it is verifiable (every answer traces back to its source).
