"""Adaptive System-One reflex fabric for JEV-Orchestrator v3.

The fabric decides *when* a bounded semantic checkpoint is worth paying for.
It never replaces deterministic safety rules and never executes side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Budget, DEFAULT_BUDGET


@dataclass(frozen=True)
class ReflexSignal:
    event: str
    uncertainty: float = 0.0
    risk: str = "moderate"
    semantic_ambiguity: bool = False
    failure_observed: bool = False
    conflicting_evidence: bool = False
    irreversible: bool = False
    tokens_used: int = 0
    checkpoints_used: int = 0


@dataclass(frozen=True)
class ReflexDecision:
    call_jev: bool
    reason: str
    question_pack: str
    allow_parallel_agents: bool
    allow_escalation: bool


class ReflexFabric:
    """Cheap deterministic pre-gate around expensive semantic decisions."""

    ALWAYS_CHECK = frozenset({"initial_route", "pre_escalation", "pre_finish"})
    EVENT_CHECK = frozenset({
        "tool_failure", "agent_failure", "conflicting_evidence",
        "acceptance_uncertain", "phase_change", "high_value_decision",
    })

    def __init__(self, budget: Budget = DEFAULT_BUDGET) -> None:
        self.budget = budget

    @staticmethod
    def _risk_high(risk: str) -> bool:
        return risk.lower() in {"high", "critical"}

    def decide(self, signal: ReflexSignal) -> ReflexDecision:
        if signal.checkpoints_used >= self.budget.max_checkpoints:
            return ReflexDecision(False, "checkpoint_budget_exhausted", "none", False, False)
        if signal.tokens_used >= self.budget.max_total_tokens:
            return ReflexDecision(False, "token_budget_exhausted", "none", False, False)

        trigger = (
            signal.event in self.ALWAYS_CHECK
            or signal.event in self.EVENT_CHECK
            or signal.semantic_ambiguity
            or signal.failure_observed
            or signal.conflicting_evidence
            or signal.irreversible
            or signal.uncertainty >= self.budget.thinktank_uncertainty_threshold
            or self._risk_high(signal.risk)
        )
        if not trigger:
            return ReflexDecision(False, "deterministic_fast_path", "none", False, False)

        parallel = (
            signal.conflicting_evidence
            or signal.uncertainty >= self.budget.thinktank_uncertainty_threshold
            or (self._risk_high(signal.risk) and signal.semantic_ambiguity)
        )
        escalation = signal.failure_observed or signal.uncertainty >= self.budget.escalation_on_low_confidence
        pack = "route" if signal.event == "initial_route" else "gate" if signal.event == "pre_finish" else "checkpoint"
        return ReflexDecision(True, "semantic_checkpoint_justified", pack, parallel, escalation)

    def snapshot(self, signal: ReflexSignal) -> dict[str, Any]:
        decision = self.decide(signal)
        return {
            "event": signal.event,
            "call_jev": decision.call_jev,
            "reason": decision.reason,
            "question_pack": decision.question_pack,
            "allow_parallel_agents": decision.allow_parallel_agents,
            "allow_escalation": decision.allow_escalation,
        }
