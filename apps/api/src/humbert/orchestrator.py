"""The two-call orchestration loop — Tier 1.

The first place an LLM meets the semantic-layer module. It runs the contract
from docs/product-design/009-orchestration.md:

1. **Plan** — the question + the vocabulary go to the model; it returns a
   ``Selection`` (block 1's IR) plus a one-line *reading* of how it mapped the
   words to the names it chose.
2. **(deterministic)** ``semantic.resolve`` validates the selection; if it
   doesn't resolve, the named gaps are fed back to the planner *once* and it
   tries again. A resolved selection runs through ``semantic.run`` — the numbers
   come from there, never from the model.
3. **Narrate** — the rows go back to the model, which writes the answer over the
   numbers it was handed, forbidden from inventing any.

This module is the **LLM seam**: it is the only code that names the agent
framework (PydanticAI), the way ``engine`` is the only code that names dbt. It
speaks to the deterministic core through ``semantic`` and never touches the
warehouse itself. No Tier 2, no styled refusal, no charts, no persistence — those
are later pitches; here a question with no Tier-1 answer stops plainly.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from humbert import semantic
from humbert.config import LLM

Certainty = Literal["high", "medium"]

# The stage keys ``ask`` emits as the loop moves. Renderers (CLI, server) map
# them to copy; typing them lets mypy police those mappings against drift.
Stage = Literal["planning", "replanning", "running", "narrating"]


class OrchestratorError(Exception):
    """A problem reaching or configuring the model — not a failed answer."""


class Plan(BaseModel):
    """What the plan call returns: a selection plus how it read the question."""

    selection: semantic.Selection
    reading: str


@dataclass
class Answer:
    """A Tier-1 answer: the narrative, the numbers behind it, and how it was read."""

    question: str
    reading: str
    selection: semantic.Selection
    columns: list[str]
    rows: list[list[str]] = field(default_factory=list)
    compiled_sql: str = ""
    narrative: str = ""
    tier: int = 1
    certainty: Certainty = "high"
    duration_seconds: float = 0.0  # wall-clock of the run step, shown on the cell


@dataclass
class NoTier1Answer:
    """No defined metric fit the question — the plain Tier-1 boundary.

    Not a Tier-2 fallback (next pitch) and not a styled refusal (block 3): just an
    honest stop that names what the planner reached for and what didn't resolve.
    """

    question: str
    reading: str
    problems: list[str]


_PLAN_INSTRUCTIONS = """\
You turn an analyst's plain-language question into a Selection over a defined \
semantic layer (defined metrics and their dimensions).

Rules:
- Use ONLY the metric and dimension names you are given. Never invent a name.
- Dimensions use MetricFlow's dunder form, e.g. `cheese_record__country`.
- Pick the metric whose meaning best fits the question, grouping/ordering/limiting \
as the question implies. Loose wording is fine — map "cheese" to the metric that \
measures it.
- "per X", "by X", "for each X", "across X", "broken down by X" all mean GROUP BY \
the dimension X — not select a second metric. ("production per variety" = \
total production grouped by the variety/product dimension.)
- When a word matches both a metric and a dimension (e.g. "variety" could be the \
`product_variety` metric or the `product` dimension), prefer GROUPING BY the \
dimension, unless the question explicitly asks how many/how varied (a count).
- Choose TWO metrics ONLY when the question relates two distinct measures — a \
correlation or trade-off ("do places that make more also make more kinds?"). A \
plain "how much … per/by X" is ONE metric grouped by X, never two.
- Filters in `where` MUST use MetricFlow's template syntax, never raw SQL columns \
(a raw column name fails unless it is also grouped). Wrap each dimension:
  - categorical: `{{ Dimension('cheese_record__country') }} = 'Germany'`
  - time: `{{ TimeDimension('metric_time', 'year') }} >= '2015-01-01'`
  Combine conditions with AND/OR inside one expression. To filter a time range, \
use the time `where` template — do not rely on `time_grain`, which only sets the \
grain of a grouped time dimension.
- Always fill `reading`: one short line naming the words you heard and the names \
you chose, e.g. "read cheese as total_production, by country, top 5".
- If nothing fits, still return your best attempt — it will be validated, not \
trusted blindly."""

# Module-level, the way PydanticAI recommends: the instructions are static and
# the configured model is passed per run.
_plan_agent: Agent[None, Plan] = Agent(output_type=Plan, instructions=_PLAN_INSTRUCTIONS)

_NARRATE_INSTRUCTIONS = """\
You write a short, plain answer to the analyst's question using ONLY the numbers \
in the result rows. This is the one rule that cannot bend: never state, estimate, \
or round to a figure that is not present in the rows. Lead with the answer, stay \
warm and concise, and don't narrate the columns mechanically. If there are no \
rows, say plainly that the query returned nothing."""

_narrate_agent: Agent[None, str] = Agent(output_type=str, instructions=_NARRATE_INSTRUCTIONS)


def build_model(llm: LLM) -> Model:
    """Construct the configured model. The CLI calls this; tests inject their own.

    Provider and model are config, not code (design pillar 2). v0 ships the
    Anthropic provider; other providers are a config + extra away.
    """
    api_key = os.environ.get(llm.api_key_env)
    if not api_key:
        raise OrchestratorError(
            f"No API key found in ${llm.api_key_env}. Set it to ask questions, "
            "or change `llm.api_key_env` in config.json."
        )
    if llm.provider == "anthropic":
        return AnthropicModel(llm.model, provider=AnthropicProvider(api_key=api_key))
    raise OrchestratorError(f"Unsupported LLM provider '{llm.provider}'. v0 supports 'anthropic'.")


def ask(
    question: str,
    *,
    project_dir: Path,
    vocabulary: semantic.Vocabulary,
    model: Model,
    on_stage: Callable[[Stage], None] | None = None,
    prior_question: str | None = None,
    prior_selection: semantic.Selection | None = None,
) -> Answer | NoTier1Answer:
    """Run plan → run → narrate for one question. Tier 1 only.

    ``model`` is a PydanticAI model — the live one from :func:`build_model`, or a
    scripted ``TestModel`` / ``FunctionModel`` in tests, so CI never calls a real
    LLM.

    ``on_stage`` is called with a stage key (``planning`` / ``replanning`` /
    ``running`` / ``narrating``) as the loop moves through its phases, so a caller
    can show progress over the slow model calls. The orchestrator emits keys, not
    copy — the CLI decides how to render them.

    ``prior_question`` / ``prior_selection`` carry the cell a follow-up refines:
    the planner is shown the previous structured query and told to start from it
    *only* when this question clearly refers back ("add Italy", "just France"),
    and to ignore it otherwise. The output is still a validated Tier-1 selection,
    so a misread is a quality miss the ``reading`` surfaces — never an unsafe one.
    """
    notify: Callable[[Stage], None] = on_stage or (lambda _stage: None)

    notify("planning")
    plan, resolved, first_try = _plan_and_resolve(
        question, vocabulary, model, notify, prior_question, prior_selection
    )

    if isinstance(resolved, semantic.Unresolved):
        return NoTier1Answer(question=question, reading=plan.reading, problems=resolved.problems)

    # The retry (if any) means the first reading missed — a weaker mapping.
    certainty: Certainty = "high" if first_try else "medium"

    notify("running")
    started = time.perf_counter()
    result = semantic.run(resolved, vocabulary, project_dir)
    duration = time.perf_counter() - started
    notify("narrating")
    narrative = _narrate(question, plan, result, model)

    return Answer(
        question=question,
        reading=plan.reading,
        selection=plan.selection,
        columns=result.columns,
        rows=result.rows,
        compiled_sql=result.compiled_sql,
        narrative=narrative,
        tier=1,
        certainty=certainty,
        duration_seconds=duration,
    )


def _plan_and_resolve(
    question: str,
    vocabulary: semantic.Vocabulary,
    model: Model,
    notify: Callable[[Stage], None],
    prior_question: str | None = None,
    prior_selection: semantic.Selection | None = None,
) -> tuple[Plan, semantic.ResolvedSelection | semantic.Unresolved, bool]:
    """Plan, validate, and retry once with the named gaps fed back.

    Returns the (last) plan, the resolution, and whether it resolved on the first
    attempt — the coarse signal ``ask`` turns into certainty.
    """
    vocab_text = _vocabulary_prompt(vocabulary)
    prior_text = _prior_prompt(prior_question, prior_selection)

    run = _plan_agent.run_sync(
        f"{prior_text}Question: {question}\n\nAvailable vocabulary:\n{vocab_text}", model=model
    )
    plan: Plan = run.output
    resolved = semantic.resolve(plan.selection, vocabulary)
    if isinstance(resolved, semantic.ResolvedSelection):
        return plan, resolved, True

    # One correction: hand back exactly what didn't resolve and let it re-plan.
    notify("replanning")
    gaps = "\n".join(f"- {p}" for p in resolved.problems)
    retry = _plan_agent.run_sync(
        "That selection didn't resolve:\n"
        f"{gaps}\n\n"
        "Propose a corrected Selection using only the names in the vocabulary above.",
        model=model,
        message_history=run.all_messages(),
    )
    plan = retry.output
    return plan, semantic.resolve(plan.selection, vocabulary), False


def _narrate(question: str, plan: Plan, result: semantic.Result, model: Model) -> str:
    """The second call: prose over the rows the engine actually returned."""
    rows_text = _rows_prompt(result)
    out = _narrate_agent.run_sync(
        f"Question: {question}\n"
        f"Reading: {plan.reading}\n\n"
        f"Result:\n{rows_text}\n\n"
        "Write the answer.",
        model=model,
    )
    return out.output.strip()


def _prior_prompt(prior_question: str | None, prior_selection: semantic.Selection | None) -> str:
    """The refine-or-start-fresh preamble, or empty when there's no prior cell.

    Shown to the planner before the question so a follow-up like "add Italy" or
    "just France" can carry the previous selection forward. The rule biases to
    *fresh*: the prior is used only when the question plainly refers back to it.
    """
    if prior_question is None or prior_selection is None:
        return ""
    return (
        "There is a previous answer in this conversation.\n"
        f"Previous question: {prior_question}\n"
        f"Previous selection (the structured query that answered it): "
        f"{prior_selection.model_dump_json()}\n"
        "If THIS question refines the previous one — it refers back, e.g. "
        '"add Italy", "and Belgium too", "just France", "by year instead", '
        '"drop the filter" — start from the previous selection and change ONLY '
        "what this question asks, keeping the rest. If the question stands on its "
        "own, ignore the previous selection entirely and plan it fresh.\n\n"
    )


def _vocabulary_prompt(vocabulary: semantic.Vocabulary) -> str:
    """Render the vocabulary the way ``humbert vocab`` shows it, for the planner."""
    lines: list[str] = []
    for metric in vocabulary.metrics:
        lines.append(f"metric: {metric.name}")
        for dim in metric.dimensions:
            grain = f" (grains: {dim.grain})" if dim.kind == "time" and dim.grain else ""
            lines.append(f"  dimension: {dim.name} [{dim.kind}{grain}]")
    return "\n".join(lines) if lines else "(no metrics exposed)"


def _rows_prompt(result: semantic.Result) -> str:
    """Render the returned rows as a compact table for the narrator."""
    if not result.rows:
        return "(no rows returned)"
    header = " | ".join(result.columns)
    body = "\n".join(" | ".join(row) for row in result.rows)
    return f"{header}\n{body}"
