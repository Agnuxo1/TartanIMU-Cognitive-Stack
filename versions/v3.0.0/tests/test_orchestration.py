"""Policy and integration tests using deterministic fake backends."""
from __future__ import annotations

from dataclasses import dataclass

from jev_orchestrator.config import Budget
from jev_orchestrator.orchestrator import JEVOrchestrator
from jev_orchestrator.runtime import AgentResult


def _answer(value, confidence=1.0):
    return {"value": value, "confidence": confidence}


def _route(model_level="astra", agent="astra_architect", skill="python_debugging"):
    return {"answers": {
        "agent": _answer(agent),
        "tool": _answer("desktop_commander"),
        "skill": _answer(skill),
        "model_level": _answer(model_level),
        "needs_web": _answer(0.0),
        "success_criteria": _answer("tested_change"),
    }, "decision_source": "fake"}


class FakeRouter:
    def __init__(self, gates, actions=("finish",), handoff="continue_from_luna", model_level="astra", agent="astra_architect", skill="python_debugging"):
        self.gates = iter(gates)
        self.actions = iter(actions)
        self.handoff = handoff
        self.initial_calls = 0
        self.supervise_calls = 0
        self.model_level = model_level
        self.agent = agent
        self.skill = skill

    def initial(self, task, context_summary=""):
        self.initial_calls += 1
        return _route(self.model_level, self.agent, self.skill)

    def supervise(self, state):
        self.supervise_calls += 1
        action = next(self.actions, "finish")
        return {"answers": {
            "next_action": _answer(action),
            "handoff_mode": _answer(self.handoff),
            "on_track": _answer(0.1 if action.startswith("escalate") else 0.8),
            "ready_for_gate": _answer(0.0 if action.startswith("escalate") else 1.0),
        }}

    def gate(self, objective, result_summary, unresolved=None):
        return next(self.gates)


@dataclass
class FakeRuntime:
    outputs: list[str]

    def __post_init__(self):
        self.calls = []

    def run(self, agent_name, task, context="", use_web=False):
        self.calls.append((agent_name, context, use_web))
        output = self.outputs.pop(0)
        return AgentResult(output, agent_name, {"luna_coder": "gpt-5.6-luna", "sol_engineer": "gpt-5.6-sol", "sol_rights": "gpt-5.6-sol", "astra_architect": "gpt-6-astra", "astra_publisher": "gpt-6-astra"}[agent_name], 10, 5, 0, 0.001, "fake")


def _gate(ready, quality=1.0):
    return {"answers": {"ready": _answer(ready), "quality": _answer(quality), "needs_stronger_review": _answer(1.0 - ready)}}


def test_deterministic_short_circuit_happens_before_router_or_runtime():
    class ExplodingRouter:
        def initial(self, *args, **kwargs):
            raise AssertionError("Jev must not run for exact deterministic work")

    class ExplodingRuntime:
        def run(self, *args, **kwargs):
            raise AssertionError("An LLM must not run for exact deterministic work")

    result = JEVOrchestrator(router=ExplodingRouter(), runtime=ExplodingRuntime()).execute("Calculate 7 * 8")
    assert result.output == "56"
    assert result.telemetry["by_tier"] == {}


def test_initial_astra_recommendation_is_overridden_to_luna():
    router = FakeRouter([_gate(1.0)], actions=("finish",))
    runtime = FakeRuntime(["Luna completed the task."])
    result = JEVOrchestrator(router=router, runtime=runtime).execute("Implement a small Python change")
    assert runtime.calls[0][0] == "luna_coder"
    assert result.telemetry["by_tier"] == {}
    assert router.initial_calls == 1


def test_failed_luna_escalates_to_sol_with_compact_handoff():
    router = FakeRouter([_gate(0.0), _gate(1.0)], actions=("finish",), handoff="continue_from_luna", model_level="luna", agent="luna_coder")
    runtime = FakeRuntime(["Tests fail: missing edge-case handling.", "Sol fixed the edge case and tests pass."])
    result = JEVOrchestrator(router=router, runtime=runtime, budget=Budget(max_luna_rounds=1)).execute("Implement and test a Python change")
    assert [call[0] for call in runtime.calls] == ["luna_coder", "sol_engineer"]
    assert "Tests fail" in runtime.calls[1][1]
    assert result.telemetry["telemetry_file"]


def test_sol_failure_can_reach_astra_only_after_sol_gate_failure():
    router = FakeRouter([_gate(0.0), _gate(0.0), _gate(1.0)], actions=("finish",), handoff="restart_with_sol", model_level="luna", agent="luna_coder")
    runtime = FakeRuntime(["Luna incomplete.", "Sol incomplete.", "Astra completed the missing work."])
    result = JEVOrchestrator(router=router, runtime=runtime, budget=Budget(max_luna_rounds=1)).execute("Design and implement a difficult Python architecture")
    assert [call[0] for call in runtime.calls] == ["luna_coder", "sol_engineer", "astra_architect"]
    assert "Luna" not in runtime.calls[1][1]
    assert result.gate["answers"]["ready"]["value"] == 1.0
