---
date: '2026-05-19'
tags:
  - semantic-layer
  - humbert
status: active
---
# Semantic layer

Underneath the [[002-product-forms]] lives the semantic layer. The product forms are what users work with. The semantic layer is what makes their questions answerable and the answers trustworthy. It defines **what things mean**.

It is declarative, versioned, diffable, testable, and small enough to reason about.

## Domain

The semantic layer describes the world in the language practitioners actually use.

| Object         | Example                                  | Role                                                                                                                    |
| -------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Entity         | Organisation, activity, person, location | The things the domain is about                                                                                          |
| Relationship   | Activity happens at location             | How entities connect                                                                                                    |
| Metric         | Total amount, number of visits           | What can be calculated                                                                                                  |
| Dimension      | Year, municipality, category             | How metrics can be grouped                                                                                              |
| Classification | Open, internal, confidential, personal   | Every dataset, every Domain object, and every attribute carries a classification. Classification rides in dbt `meta:`.  |

## The pack

The semantic layer is packaged as a **pack** — declarative files, versioned and reviewable.

```
pack/
  domain/        metrics, dimensions, entities, relationships
                 (dbt semantic models + meta: labels, aliases, classification)
  context/       glossary, source notes, known pitfalls (prose for the LLM)
  introspection/ schema, dbt-schema, profiling, samples
                 (read from sources; cached, not owned)
  tests/         evaluation questions and frozen reference answers
```

The principle matters more than the layout: versioned, diffable, reviewable, testable, curated by the information manager, executable by the runtime.

## v0 — what we are building

These rules describe Tier 1, the defined-metric path. The full plan → answer flow, the governed-SQL fallback, and the refusal floor live in [[009-orchestration]].

- **One compiler: dbt's semantic layer (MetricFlow).** The LLM resolves a question into a MetricFlow selection — a defined metric, exposed dimensions, filters — over a curated vocabulary. In this path it never writes SQL: determinism lives in MetricFlow, and the validated cell stores the selection, not the sentence.
- **The pack owns the dbt semantic layer (MetricFlow), floored at the marts — not the transformation code.** From the marts up, the dbt semantic layer is the single source of truth for definitions: metrics and dimensions, with labels and aliases in their `meta:`, no parallel vocabulary file. Prose context stays as pack files. The dbt code that *builds* the marts is upstream and not part of the pack. Physically this can be one dbt project; the pack is the governed slice from the marts up, not the whole repo.
- **Propose-then-validate.** The LLM proposes a selection; the semantic layer checks every metric and dimension against the ones that exist before compiling. An unknown name does not become a query here — it falls through to the governed-SQL fallback, and only a question that no tier can reach is refused (see [[009-orchestration]], [[006-honest-uncertainty]]).
- **Defined metrics first.** There is no on-the-fly *definition* composer: the model never mints a reusable metric. A descriptive question with no matching metric falls through to the governed fallback, and a useful answer there is a signal for the information manager to define the metric. The vocabulary grows on real demand.
- **Public data only.** v0 runs on open data. Sensitivity classification rides in dbt `meta:`, and the pack build refuses to expose anything not classified open. Access, masking, and disclosure are out of scope until needed.
- **The semantic layer is its own module, in-process for now.** The notebook reaches data only through the module's interface. No warehouse connection, dbt handle, or raw SQL ever leaves it. Promotable to a service later by exposing the same interface over HTTP, unchanged.
