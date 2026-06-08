---
project: humbert
type: pitch
status: shipped
block: setup
appetite: medium
created: 2026-06-08
started: 2026-06-08
shipped_on: 2026-06-08
---
# Pack scaffolding — the public-only guard

## Problem

v0's entire safety story is one sentence: **public data only** ([[../../product-design/004-semantic-layer]]). Right now nothing enforces it. `connect` exposes every model in the marts schema and `vocab`/`query` will run against any metric MetricFlow can see — there is no notion of *classification*, so the "public only" promise is a claim with no mechanism behind it. The moment block 2 lets the LLM (Tier 1) and governed SQL (Tier 2) reach data, every data-reaching path inherits whatever the source exposes. A trust guarantee with no enforcement is a lie, and Humbert's whole identity is trustworthiness. This is the last block-1 pitch on purpose: the fence has to exist **before** the loop that would otherwise reach past it.

## Sketch

"The pack" is not four new directories. Per the design, the connected dbt project **is** the pack — the governed slice from the marts up. `domain/` is the semantic models we already read. What the dbt project doesn't yet carry is the one thing that makes it a *governed* slice: **classification**, and a fence that refuses to expose anything not classified open. That fence is this pitch. The other pack directories are deferred to the blocks that consume them (below, with reasons).

### Classification in dbt `meta:` — model level

Each marts model carries its sensitivity in dbt `meta:`:

```yaml
models:
  - name: fct_cheese_production
    meta:
      classification: open
```

v0 classifies at the **model** level, not per-column. The design explicitly defers "access, masking, and disclosure… until needed" — per-attribute classification is that, and v0 is open-data-only, so coarse model-level open/not-open is exactly enough to keep the promise. The cheese marts get `classification: open` so the example passes its own guard.

### The public-only guard — default-deny

The load-bearing piece. When the vocabulary is built (and at `connect`), a metric is exposed **only if every model it reads is classified `open`**. Anything else is withheld — **default-deny**: an *unclassified* model is treated as not-open, not as open. This is the fail-safe direction; forgetting to classify hides data rather than leaking it. `connect` reports the count (`K withheld`), and if the filter empties the exposed layer, the error names the cause ("no models classified `open` — add `classification: open` to your marts").

The read lives in the engine (`classifications()` parses `meta:` from `manifest.json`); the *policy* (default-deny, what to withhold) lives in the semantic module, applied where the `Vocabulary` is assembled — so every downstream consumer (vocab, query, and block 2's Tier 1/Tier 2) inherits the fence for free, at the one chokepoint, without ever knowing about classification.

### `active_pack` made honest

`Connection.active_pack` exists but is unused. In the dbt-is-the-pack model there's one pack per connection, so this stays a thin label (the connection/pack name), recorded and shown in `status` — not a second abstraction. Just enough that "which pack is active" has an answer.

### What this is *not* building (deferred, with reasons)

- **`context/`** (glossary, source notes, pitfalls — prose for the planner) → **block 2.** It's consumed by the LLM planner, which doesn't exist yet. Built speculatively now, we'd be guessing what the planner needs; built with the planner, we'd know. The loop closes without it (the planner can read labels + names for the cheese demo).
- **`introspection/`** (cached schema/profiling) → **deferred until measured.** Pure cache. The module reads live today and it's fast; add caching when profiling shows a need, not before.
- **`tests/`** (evaluation set) → **block 5**, as the block note already states. Nothing to put in it until the evaluation harness exists.
- **Per-attribute / per-column classification, masking, disclosure** → **until non-open data arrives.** The design defers it; model-level default-deny holds the v0 promise.

## Cut line

The connected dbt project loads as a classified pack: every exposed metric traces to `open`-classified models, anything unclassified is withheld by default, and `connect`/`status` report how many were withheld. The cheese example carries `classification: open` and passes its own guard — `vocab` shows `total_production`; a project with an unclassified mart has it withheld with a clear message.

## Out of scope

- `context/`, `introspection/`, `tests/` directories and their content — deferred to blocks 2, (when measured), and 5 respectively (see above).
- Per-column classification, masking, row-level access, disclosure controls — until non-open data is actually connected.
- Synonym/alias matching — `meta:` may carry `label`/`aliases`, but *consuming* aliases is block 2's planner; this pitch reads `classification` only.
- A strict mode that hard-fails `connect` on any unclassified model — v0 is default-deny-and-report (withhold, don't abort); revisit if real projects want the stricter gate.
- Any pack format beyond "the dbt project + classification" — no separate pack manifest file, no pack registry.

## Risks / unknowns

- **Where `meta:` lands in the manifest.** `classification` set on a dbt model should surface under that node's `meta` (or `config.meta`) in `manifest.json` — confirm the exact path, and whether it also needs reading from semantic-model `meta:` for metrics defined there. The whole guard rests on reading it reliably.
- **Metric → models mapping.** A metric reads a measure on a semantic model, which `ref()`s a marts model. Tracing metric → underlying model(s) → classification needs the manifest's lineage; confirm it's there without re-deriving the dbt graph. For the single-model cheese case it's direct; multi-hop is the risk.
- **Default-deny ergonomics.** A real dbt project with dozens of unclassified marts would expose nothing until classified — correct, but the message must make the fix obvious, not feel like breakage.
- **`active_pack` redundancy.** If it adds nothing over the connection in v0, say so and keep it a label — don't invent pack identity the product doesn't need yet.

---

## What actually happened

A metric is exposed **only if every model it reads is classified `open`**. Anything else is withheld. By **default we deny**: an *unclassified* model is treated as not-open, not as open. To express classification use the dbt `meta:` key. 