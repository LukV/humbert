---
project: humbert
type: pitch
status: shipped
block: notebook
appetite: chunky
created: 2026-06-08
started: 2026-06-08
shipped_on: 2026-06-08
---
# Two-call orchestration — Tier 1

## Problem

Block 1 built the deterministic Tier-1 core: a vocabulary, a `Selection` IR,
`resolve()`, and a compile-and-run path, all driveable by hand through humbert
vocab / humbert query. But a person still has to *write the selection
themselves* — name the metric, the dimensions, the order. The whole point of
Humbert is that you ask in plain language and it does the plumbing. Nothing yet
turns "which countries produce the most cheese?" into that selection, runs it,
and writes an answer over the rows. This pitch builds that spine — the
**plan → run → narrate** loop ([[../../product-design/009-orchestration]]) — and
it is the first time an LLM calls the semantic-layer module. It is the point of
v0: a question becomes an answer you can trust, because the model never reports a
number it has not seen the engine produce.

## Sketch

Two model calls with deterministic work between them, exactly the contract in
[[../../product-design/009-orchestration]]:

1. **Plan** — the question + the vocabulary go to the model; it returns a
   `Selection` (the same pydantic IR block 1 built) plus a short *reading* of how
   it mapped the words to the names it chose.
2. **(deterministic)** `resolve()` validates the selection against the
   vocabulary; `run()` compiles and executes it. The numbers come from here.
3. **Narrate** — the rows + the question go back to the model; it writes the
   answer over the numbers it was handed.

Surfaced through one CLI command — `humbert ask "<question>"` — which prints the
narrative, the selection it chose (with the reading), and the SQL. No UI, no
persistence, no charts yet; this is the engine those later pitches drive.

### The agent framework — PydanticAI *(the ADR's open decision, settled here)*

The two calls need a model client that is **provider-agnostic** (pillar 2: model
is config, not code — `config.llm` already carries `provider / model /
api_key_env`) and that can return a **validated `Selection`**, not a string we
parse and pray over. [PydanticAI](https://ai.pydantic.dev) is that, and almost
nothing more: `Agent(model, output_type=Selection)` hands back our existing IR
already validated, retries the model automatically when it returns something that
doesn't fit the schema, and swaps providers by config string. It is not an
agent *loop* framework we're importing for a loop we don't have — we use the thin
single-call surface, because the alternative is hand-rolling provider selection +
JSON-schema tool definitions + parse/validate/retry, which is strictly more code
to own for strictly less safety.

**Why we need it (and why now):** the plan call's whole value is that its output
is a *typed, validated* `Selection` — the object `resolve()` already checks and
block 2's cell will freeze. Raw SDK calls give us a string; we'd rebuild
structured output and retries ourselves, against each provider. PydanticAI also
ships `TestModel` / `FunctionModel` so unit tests drive the loop with a scripted
model and **CI never calls a real LLM** — the same lean-CI discipline the engine
seam established. Deciding it now is the gate the block note names: it shapes
every line of orchestration code.

### Plan call — question → `Selection`

The model is given the question, the vocabulary (metric names + their dimensions
with kind/grain — what `humbert vocab` shows), and the instruction to compose a
`Selection` using only those names. It returns the `Selection` and a one-line
*reading*: the words it heard and the names it chose for them.

**Why we need it:** this is the loop's first call and the thing that makes
Humbert a notebook rather than a query builder. Irreducible.

### resolve → run — the deterministic middle

The proposed `Selection` goes straight through block 1's `resolve()`. Resolves →
`run()` executes it. Doesn't resolve → the structured `Unresolved` (the named
gaps) is fed **back to the planner once** as a correction ("you used
`cheese_record__region`, which isn't a dimension of `total_production`"), and it
plans again. Still unresolved after that one retry → `ask` stops with a plain
"couldn't map that to a defined metric" message naming what was missing.

**Why we need it:** this is propose-then-validate closing its loop — the guard
block 1 built specifically so a hallucinated metric name can never reach the
warehouse. The single retry is what turns a near-miss into a hit cheaply; it
reuses `resolve()` and `run()` untouched, so it costs a feedback string and a
loop bound, not new machinery. The plain stop is the **Tier-1 boundary**: not a
Tier-2 fallback (next pitch), not a styled refusal (block 3).

### Narrate call — rows → answer

The returned rows, the question, and the selection go back to the model, which
writes a short prose answer grounded in those numbers. The prompt's one hard rule
is the contract's: report only numbers present in the rows.

**Why we need it:** without it the loop returns a table, not an answer — the
narrative is the product's actual output. Irreducible. (Charts are the
*beautiful-defaults* pitch; this prints prose + the SQL.)

### The reading — the correctable synonym line

The planner's *reading* ("read **cheese** as `total_production`, grouped by
`cheese_record__country`") is printed with the answer. [[../../product-design/009-orchestration]]
names this as the safeguard for loose matching: a surfaced, correctable mapping
is not a hidden guess.

**Why we need it (and why it could be cut):** showing the resolved selection is
the irreducible part — the user must be able to see what was asked on their
behalf. The *narrated* reading line is the cheap, honest version of that and the
named safeguard, so it's in; but if it grows teeth (editing the reading to
re-plan), that's the *refinement* pitch, not this one. v0 shows it; it doesn't
yet let you click it.

## Cut line

`humbert ask "which countries produce the most cheese?"` runs plan → run →
narrate against `examples/cheese` and prints a correct narrative grounded in the
real rows (Germany on top), the selection it chose with its reading, and the
compiled SQL — with one resolve-feedback retry, and a plain "couldn't map to a
defined metric" stop when the question has no Tier-1 answer. CI exercises the
loop with a scripted test model; the real-LLM path is checked locally.

## Out of scope

- **Tier 2 — governed SQL fallback.** When no metric fits, this pitch *stops
  plainly*; writing SQL over the marts is the next pitch in this block.
- **Tier 3 — styled refusal + redirect.** Block 3. Here, "no Tier-1 answer" is a
  plain message, not the refusal *form*.
- **The cell — persistence + faithful re-render.** Separate pitch; `ask` returns
  a structured answer object but stores nothing yet.
- **Charts / Vega-Lite / beautiful defaults.** The *beautiful-defaults* pitch.
- **The notebook UI and any HTTP endpoint.** CLI-only here, matching the
  semantic-module precedent; the UI calls this engine in a later pitch.
- **The full certainty score.** Its computation is shared with block 3; this
  pitch records `tier` and a coarse confidence (high / medium-when-the-reading-
  carries-an-assumption) on the answer, and defers real scoring.
- **Streaming the plan/narrate calls.** Sync is fine for a CLI; streaming lands
  when the UI wants it (ADR open item, deferred).
- **Dutch narratives.** The narrator writes in English here; locale-aware
  narration is the *localization* pitch.

## Risks / unknowns

- **Plan-call reliability.** Will the model reliably compose a valid `Selection`
  from the vocabulary, or lean on retries? `resolve()` is the safety net (a bad
  plan can't run), and the single retry with named gaps is the mitigation — but
  if one retry isn't enough on real questions, the honest move is the plain stop,
  not more retries. Watch the retry rate on the cheese set.
- **PydanticAI surface + version.** New core dependency. Confirm `output_type`
  with a pydantic model, the retry-on-validation behaviour, and `TestModel` /
  `FunctionModel` for CI all work as expected on a pinned version, and that the
  Anthropic provider reads `config.llm` cleanly. Keep it confined to a thin
  `orchestrator` module so the framework, like the dbt engine, sits behind one
  seam and stays swappable.
- **Dependency packaging — decided: core.** `ask` needs *both* the LLM client and
  the dbt engine (it runs the query). PydanticAI + the Anthropic provider are a
  **core** dependency — the orchestration loop is the product, and gating it
  behind an extra would fragment the one path that matters; `ask` still needs
  `--extra dbt` to reach the warehouse.
- **CI without a model.** Unit tests must drive the loop deterministically with a
  scripted model and never hit the network; a real-LLM end-to-end stays a local
  manual/integration check (skipped without an API key), mirroring the engine's
  `--extra dbt` integration split.
- **Prompt grounding.** The narrate prompt must refuse to invent numbers even
  when rows are sparse or empty. Test the empty-result and single-row cases
  explicitly — a narrator that fills gaps is the exact failure the two-call split
  exists to prevent.
- **KISS check — is two calls + a retry too much?** It's the minimum the contract
  allows: one call can't both choose the numbers and write the sentence without
  risking invented figures (the whole reason for the split), and without the
  retry a one-word miss becomes a dead end instead of a hit. Everything heavier —
  Tier 2, refusal styling, certainty scoring, the cell, charts, streaming, the
  UI — is explicitly pushed to its owning pitch above. What's left is the
  irreducible spine.


---

## What actually happened

The start of block 2: this pitch integrates the LLM and the agentic framework
(PydanticAI). The outcome is the two-step model integration with deterministic
work in between — **plan → (resolve) → narrate**. Plan calls the agent with the
vocabulary and gets back a `Selection`. Resolve validates the query, then it's
compiled and run. Narrate is the LLM turning the returned rows into natural
language. Scope is pure Tier 1, deterministic output: no metric found, no answer.
No UI yet, but a new CLI endpoint, `humbert ask`.

We tested it for real. Not only the straightforward "which countries produce the
most dairy" (note — *dairy*, not cheese: the synonym read worked), but also
`humbert ask "how has cheese production evolved over the years in Germany, since
2015"`. Same answer twice; the narration differed but was above expectations each
time. The second question surfaced a bug — the planner emitted a raw-SQL `where`
filter that MetricFlow rejects — fixed mid-pitch by teaching the planner
MetricFlow's `{{ Dimension(...) }}` / `{{ TimeDimension(...) }}` template syntax,
locked with an engine-level regression test.

One annoyance to carry forward: the lack of verbosity. The blank waiting screen —
already there with `connect`, now again with `ask` — gives no grasp of what's
happening. Addressed for `ask` here with stage indicators (planning → running →
narrating, emitted by the orchestrator and rendered by the CLI); the same gap in
`connect` and the general CLI-progress story are left as a known follow-up.
