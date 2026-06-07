---
date: 2026-06-04
project: humbert
status: active
tags:
---
# Eight design pillars

The pillars fall into three groups: *whether you can trust the answer*, *how the answer presents itself*, *how the product is built and shipped*.

## Trust and verification

### 1. Explainability

Every visualization can be expanded to reveal the query and logic underneath it. The generated SQL is visible. Analysts do not trust black boxes.

### 2. Reproducibility

Given the same question against the same data and schema, Humbert produces the same query, the same chart, the same narrative. The system resolves the user's intent into an intermediate representation — a SQL query, a declarative chart specification, a data-bound narrative template — that is deterministic and replayable. Every insight is auditable and version-controllable. Switching models does not break past work.

### 3. Honest uncertainty

When the data does not support an answer, Humbert says so. "We cannot answer this from the available sources" is a first-class output, not a failure mode. In serious analytical settings, a plausible but unsupported answer is dangerous; saying so honestly is more valuable than a confident approximation. In v0 this is graded by a certainty score rather than a single yes or no — see [[009-orchestration]].

## Output craft

### 4. Narrative as a first-class output

The response is a story, not just a chart. "Pipeline is down 12% YoY, driven primarily by a drop in enterprise deals in Q3. Mid-market has actually grown 8%."  - concise, specific, opinionated.

### 5. Beautiful defaults

The first chart a user sees sets the tone. Default colors, typography, and proportions must be beautiful out of the box — inspired by Observable Plot and the Financial Times chart style. 

## Architecture and shipping

### 6. Local-first

Humbert should be usable against a database on a laptop, with no cloud integration or hosted service required to begin. 

### 7. Open and embeddable

The UI matters, but it cannot be the only way in. The analytical core should be reachable through APIs and open protocols (MCP) so other LLM clients, internal platforms, and downstream tools can call Humbert as a trustworthy analytical service. 

### 8. Open source

Source code, core logic, and design choices should be as transparent, reusable, and auditable as possible. This supports public accountability as Humbert is used in public settings, supports collaboration where it is used in private ones, and in both cases is the most direct hedge against vendor lock-in for a tool whose whole pitch is that you can see how it works.
