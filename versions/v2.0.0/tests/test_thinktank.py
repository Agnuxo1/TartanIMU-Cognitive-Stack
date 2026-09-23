from __future__ import annotations

from dataclasses import dataclass

from jev_orchestrator.config import Budget
from jev_orchestrator.runtime import AgentResult
from jev_orchestrator.telemetry import Telemetry
from jev_orchestrator.thinktank import Thinktank


def _answer(value):
    return {"value": value}


class FakeRouter:
    def __init__(self, use_panel: bool, critic_tier: str = "astra"):
        self.use_panel = use_panel
        self.critic_tier = critic_tier
        self.deliberation_calls = []
        self.gate_calls = []

    def deliberation(self, state):
        self.deliberation_calls.append(state)
        return {"provenance": "local", "answers": {
            "use_thinktank": _answer(1.0 if self.use_panel else 0.0),
            "mode": _answer("two_independent_then_critic" if self.use_panel else "single_worker"),
            "critic_tier": _answer(self.critic_tier),
            "human_checkpoint": _answer(1.0 if self.use_panel else 0.0),
        }}

    def gate(self, objective, result_summary, unresolved=None):
        self.gate_calls.append((objective, result_summary, unresolved or []))
        return {"provenance": "local", "answers": {"ready": _answer(1.0), "quality": _answer(1.0)}}


@dataclass
class FakeRuntime:
    def __post_init__(self):
        self.calls = []

    def run(self, agent_name, task, context="", use_web=False):
        self.calls.append((agent_name, task, context, use_web))
        model = {"luna_scout": "gpt-5.6-luna", "sol_researcher": "gpt-5.6-sol", "sol_scientist": "gpt-5.6-sol", "astra_reviewer": "gpt-6-astra"}[agent_name]
        return AgentResult(f"output from {agent_name}", agent_name, model, 10, 5, 0, 0.001, "fake")


def test_simple_decision_uses_one_worker_and_no_panel():
    router = FakeRouter(use_panel=False)
    runtime = FakeRuntime()
    result = Thinktank(router, runtime, Telemetry("thinktank-single"), Budget()).run("Summarize these facts", "facts")

    assert result.used is False
    assert [call[0] for call in runtime.calls] == ["luna_scout"]
    assert result.model_path == ["luna"]
    assert len(router.gate_calls) == 1


def test_triggered_decision_runs_two_views_and_one_critic_with_compact_context():
    router = FakeRouter(use_panel=True, critic_tier="astra")
    runtime = FakeRuntime()
    result = Thinktank(router, runtime, Telemetry("thinktank-panel"), Budget()).run(
        "Choose between two high-impact strategies",
        "observed fact A; observed fact B",
        risk="high",
        uncertainty=0.8,
        conflicting_evidence=True,
    )

    assert result.used is True
    assert [call[0] for call in runtime.calls] == ["luna_scout", "sol_researcher", "astra_reviewer"]
    assert result.model_path == ["luna", "sol", "astra"]
    assert result.human_checkpoint is True
    assert len(router.gate_calls) == 1
    assert "INDEPENDENT VIEWS" in runtime.calls[-1][2]
    assert len(runtime.calls[-1][2]) <= Budget().max_handoff_chars
