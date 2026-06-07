---
date: '2026-06-04'
tags:
  - information-manager
  - humbert
status: skeleton
---
# The information manager's view

> **Skeleton.** This page brings the others together from the perspective of the person who runs Humbert day to day: the information manager (IM). It is the last page because it is the synthesis — everything else is a piece the IM works with.

## Who the IM is

_(One line, linking to [[001-problem-and-stakeholders]].) (TODO)_

## What the IM owns

- **The semantic layer** — defines metrics, dimensions, labels, and aliases ([[004-semantic-layer]])
- **The evaluation set** — curates real questions and frozen answers with the client, and adds the column mapping ([[005-evaluation]])
- **Refusals** — reads them as a curation backlog, not as failures ([[006-honest-uncertainty]])
- **Telemetry** — uses it as the signal for what to define next ([[007-telemetry]])

## The loop

The core workflow, drawn from the pieces above:

```
review questions → run evaluation → inspect shortfalls → improve the pack → run again
```

And continuously, from real use:

```
watch telemetry → see undefined-but-asked → define the metric → it stops refusing
```

_(Expand. TODO)_

## A week in the life

_(Concrete walk-through of what the IM actually does, start to finish. TODO)_

## What the IM does not do

_(The boundaries — what belongs to the data engineer upstream, what belongs to the analyst, what belongs to the client. TODO)_

## Open questions

- How much dbt fluency the role assumes _(TODO)_
- Where curation ends and engineering begins _(TODO)_
