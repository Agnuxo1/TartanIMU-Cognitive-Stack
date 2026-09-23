from jev_orchestrator.reflex_fabric import ReflexFabric, ReflexSignal


def test_routine_round_uses_deterministic_fast_path():
    decision = ReflexFabric().decide(ReflexSignal(event="luna_round"))
    assert decision.call_jev is False
    assert decision.reason == "deterministic_fast_path"


def test_initial_route_always_uses_jev():
    decision = ReflexFabric().decide(ReflexSignal(event="initial_route"))
    assert decision.call_jev is True
    assert decision.question_pack == "route"


def test_uncertainty_enables_panel_and_escalation():
    decision = ReflexFabric().decide(
        ReflexSignal(event="luna_round", uncertainty=0.8)
    )
    assert decision.call_jev is True
    assert decision.allow_parallel_agents is True
    assert decision.allow_escalation is True


def test_failure_triggers_checkpoint_and_escalation():
    decision = ReflexFabric().decide(
        ReflexSignal(event="agent_failure", failure_observed=True)
    )
    assert decision.call_jev is True
    assert decision.allow_escalation is True


def test_conflicting_evidence_allows_parallel_agents():
    decision = ReflexFabric().decide(
        ReflexSignal(event="conflicting_evidence", conflicting_evidence=True)
    )
    assert decision.call_jev is True
    assert decision.allow_parallel_agents is True


def test_budget_exhaustion_blocks_extra_checkpoint():
    fabric = ReflexFabric()
    decision = fabric.decide(
        ReflexSignal(event="pre_finish", checkpoints_used=fabric.budget.max_checkpoints)
    )
    assert decision.call_jev is False
    assert decision.reason == "checkpoint_budget_exhausted"
