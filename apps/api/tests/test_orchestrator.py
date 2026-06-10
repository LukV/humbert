"""The two-call loop, driven by a scripted model so CI never calls a real LLM.

A single ``FunctionModel`` serves both calls by branching on
``info.output_tools``: the plan call asks for structured output (an output tool
is present), the narrate call wants plain text (none is).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from humbert import orchestrator, semantic
from humbert.config import LLM

PlanArgs = dict[str, object]


def _vocab() -> semantic.Vocabulary:
    return semantic.Vocabulary(
        metrics=[
            semantic.MetricInfo(
                name="total_production",
                dimensions=[
                    semantic.DimensionInfo(name="cheese_record__country", kind="categorical"),
                    semantic.DimensionInfo(name="metric_time", kind="time", grain="day"),
                ],
            )
        ]
    )


def _scripted(plans: list[PlanArgs], narrative: str = "Germany leads.") -> FunctionModel:
    """A model that returns each plan in turn, then narrates with fixed prose."""
    state = {"plan": 0}

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if info.output_tools:
            i = min(state["plan"], len(plans) - 1)
            state["plan"] += 1
            return ModelResponse(
                parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=plans[i])]
            )
        return ModelResponse(parts=[TextPart(narrative)])

    return FunctionModel(fn)


def _stub_run(monkeypatch: pytest.MonkeyPatch, result: semantic.Result) -> list[semantic.Selection]:
    """Replace semantic.run with a stub; return a list that records what it ran."""
    ran: list[semantic.Selection] = []

    def fake_run(
        resolved: semantic.ResolvedSelection,
        vocabulary: semantic.Vocabulary,
        project_dir: Path,
    ) -> semantic.Result:
        ran.append(resolved.selection)
        return result

    monkeypatch.setattr(semantic, "run", fake_run)
    return ran


_RESULT = semantic.Result(
    columns=["cheese_record__country", "total_production"],
    rows=[["Germany", "100"], ["France", "80"]],
    compiled_sql="SELECT country, sum(kg) ...",
)

_GOOD_PLAN: PlanArgs = {
    "selection": {
        "metrics": ["total_production"],
        "group_by": ["cheese_record__country"],
        "order_by": ["-total_production"],
        "limit": 5,
    },
    "reading": "read cheese as total_production, by country, top 5",
}


def test_happy_path_narrates_over_real_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    ran = _stub_run(monkeypatch, _RESULT)
    answer = orchestrator.ask(
        "which countries produce the most cheese?",
        project_dir=Path("."),
        vocabulary=_vocab(),
        model=_scripted([_GOOD_PLAN]),
    )
    assert isinstance(answer, orchestrator.Answer)
    assert answer.narrative == "Germany leads."
    assert answer.rows[0][0] == "Germany"
    assert answer.compiled_sql.startswith("SELECT")
    assert answer.reading.startswith("read cheese")
    assert answer.tier == 1
    assert answer.certainty == "high"
    # The selection the planner proposed is what actually ran.
    assert ran[0].metrics == ["total_production"]
    assert ran[0].group_by == ["cheese_record__country"]


def test_one_retry_recovers_and_marks_medium_certainty(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_run(monkeypatch, _RESULT)
    bad: PlanArgs = {
        "selection": {"metrics": ["total_production"], "group_by": ["cheese_record__region"]},
        "reading": "read cheese as total_production, by region",
    }
    answer = orchestrator.ask(
        "cheese by region?",
        project_dir=Path("."),
        vocabulary=_vocab(),
        model=_scripted([bad, _GOOD_PLAN]),
    )
    assert isinstance(answer, orchestrator.Answer)
    # Recovered on the retry — a weaker mapping, so certainty drops.
    assert answer.certainty == "medium"


def test_unresolvable_question_stops_plainly(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_run(monkeypatch, _RESULT)
    miss: PlanArgs = {"selection": {"metrics": ["visitors"]}, "reading": "read visitors"}
    answer = orchestrator.ask(
        "how many visitors?",
        project_dir=Path("."),
        vocabulary=_vocab(),
        model=_scripted([miss, miss]),  # both attempts miss
    )
    assert isinstance(answer, orchestrator.NoTier1Answer)
    assert any("visitors" in p for p in answer.problems)
    assert answer.reading == "read visitors"


def test_stage_events_track_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_run(monkeypatch, _RESULT)
    stages: list[str] = []
    orchestrator.ask(
        "q",
        project_dir=Path("."),
        vocabulary=_vocab(),
        model=_scripted([_GOOD_PLAN]),
        on_stage=stages.append,
    )
    assert stages == ["planning", "running", "narrating"]


def test_stage_events_include_replanning_on_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_run(monkeypatch, _RESULT)
    bad: PlanArgs = {
        "selection": {"metrics": ["total_production"], "group_by": ["cheese_record__region"]},
        "reading": "by region",
    }
    stages: list[str] = []
    orchestrator.ask(
        "q",
        project_dir=Path("."),
        vocabulary=_vocab(),
        model=_scripted([bad, _GOOD_PLAN]),
        on_stage=stages.append,
    )
    assert stages == ["planning", "replanning", "running", "narrating"]


def test_narrator_is_handed_only_returned_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """The narrate prompt carries the engine's rows — the anti-hallucination seam."""
    _stub_run(monkeypatch, _RESULT)
    seen: dict[str, str] = {}

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if info.output_tools:
            return ModelResponse(
                parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=_GOOD_PLAN)]
            )
        # Capture what the narrator was actually given.
        last = messages[-1].parts[-1]
        seen["prompt"] = getattr(last, "content", "")
        return ModelResponse(parts=[TextPart("...")])

    orchestrator.ask("q", project_dir=Path("."), vocabulary=_vocab(), model=FunctionModel(fn))
    assert "Germany" in seen["prompt"]
    assert "100" in seen["prompt"]


def test_empty_result_still_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    empty = semantic.Result(
        columns=["cheese_record__country", "total_production"], rows=[], compiled_sql="SELECT 1"
    )
    _stub_run(monkeypatch, empty)
    answer = orchestrator.ask(
        "q", project_dir=Path("."), vocabulary=_vocab(), model=_scripted([_GOOD_PLAN], "Nothing.")
    )
    assert isinstance(answer, orchestrator.Answer)
    assert answer.rows == []


def test_prior_prompt_is_empty_without_a_full_parent() -> None:
    sel = semantic.Selection(metrics=["total_production"])
    assert orchestrator._prior_prompt(None, None) == ""
    assert orchestrator._prior_prompt("q", None) == ""
    assert orchestrator._prior_prompt(None, sel) == ""


def test_prior_selection_reaches_the_planner(monkeypatch: pytest.MonkeyPatch) -> None:
    """A follow-up hands the planner the previous query plus the refine-or-fresh rule."""
    _stub_run(monkeypatch, _RESULT)
    plan_prompts: list[str] = []

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if info.output_tools:
            plan_prompts.append(str(getattr(messages[-1].parts[-1], "content", "")))
            return ModelResponse(
                parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=_GOOD_PLAN)]
            )
        return ModelResponse(parts=[TextPart("...")])

    prior = semantic.Selection(
        metrics=["total_production"],
        group_by=["metric_time", "cheese_record__country"],
    )
    orchestrator.ask(
        "add Italy",
        project_dir=Path("."),
        vocabulary=_vocab(),
        model=FunctionModel(fn),
        prior_question="compare cheese production between France and Germany over time",
        prior_selection=prior,
    )
    assert plan_prompts
    assert "compare cheese production between France and Germany" in plan_prompts[0]
    assert "total_production" in plan_prompts[0]
    assert "refines the previous" in plan_prompts[0]


# --- build_model: provider/key plumbing ------------------------------------


def test_build_model_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    model = orchestrator.build_model(LLM())
    assert model.model_name == "claude-opus-4-8"


def test_build_model_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(orchestrator.OrchestratorError, match="ANTHROPIC_API_KEY"):
        orchestrator.build_model(LLM())


def test_build_model_unsupported_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_KEY", "x")
    llm = LLM(provider="cohere", model="x", api_key_env="MY_KEY")
    with pytest.raises(orchestrator.OrchestratorError, match="provider"):
        orchestrator.build_model(llm)
