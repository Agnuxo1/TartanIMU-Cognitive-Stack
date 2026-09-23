"""Run the requested real benchmark matrix without inventing unavailable metrics."""
from __future__ import annotations

import json
import time
from pathlib import Path

from jev_orchestrator.config import Budget
from jev_orchestrator.orchestrator import JEVOrchestrator
from jev_orchestrator.router import JevRouter
from jev_orchestrator.runtime import AgentRuntime, ModelBackendUnavailable
from jev_orchestrator.telemetry import Telemetry

TASK = "Inspect a small Python implementation and propose a tested, minimal fix for an edge case."


def _record(name, fn):
    started = time.perf_counter()
    try:
        value = fn()
        result = {"status": "completed", "latency_seconds": time.perf_counter() - started, **value}
    except ModelBackendUnavailable as exc:
        result = {"status": "unavailable", "latency_seconds": time.perf_counter() - started, "reason": str(exc)}
    except Exception as exc:  # Keep benchmark runs comparable and stack-trace free.
        result = {"status": "failed", "latency_seconds": time.perf_counter() - started, "reason": f"{type(exc).__name__}: {str(exc)[:300]}"}
    return name, result


class InducedFailureRouter:
    """Use real initial Jev/Luna work, then force a gate failure to test escalation."""

    def __init__(self, telemetry):
        self.inner = JevRouter(telemetry, use_cache=False)
        self.gates = 0

    def initial(self, task, context_summary=""):
        return self.inner.initial(task, context_summary)

    def supervise(self, state):
        decision = self.inner.supervise(state)
        answers = decision["answers"]
        answers["next_action"] = {"value": "finish", "probabilities": {"finish": 1.0}, "confidence": 1.0}
        answers["handoff_mode"] = {"value": "continue_from_luna", "probabilities": {"continue_from_luna": 1.0}, "confidence": 1.0}
        return decision

    def gate(self, objective, result_summary, unresolved=None):
        self.gates += 1
        if self.gates == 1:
            return {"answers": {"ready": {"value": 0.0}, "quality": {"value": 0.0}, "needs_stronger_review": {"value": 1.0}}, "decision_source": "induced_failure"}
        return {"answers": {"ready": {"value": 1.0}, "quality": {"value": 1.0}, "needs_stronger_review": {"value": 0.0}}, "decision_source": "induced_failure"}


def deterministic_case():
    result = JEVOrchestrator(run_name="benchmark-deterministic").execute("Calculate exactly 123456789 * 98765")
    return {"output": result.output, "tokens": result.telemetry["total_tokens"], "cost_usd": result.telemetry["estimated_cost_usd"], "model_path": ["deterministic"], "quality": result.gate["answers"]}


def direct_sol_case():
    telemetry = Telemetry("benchmark-direct-sol")
    runtime = AgentRuntime(telemetry, validate_models=True)
    result = runtime.run("sol_engineer", TASK, "Return a concise proposed fix and test plan.")
    return {"output": result.output, "tokens": telemetry.summary()["total_tokens"], "cost_usd": telemetry.summary()["estimated_cost_usd"], "model_path": ["sol"], "telemetry": telemetry.summary()}


def luna_first_case():
    result = JEVOrchestrator(run_name="benchmark-luna-first", budget=Budget(max_luna_rounds=2)).execute(TASK)
    return {"output": result.output, "tokens": result.telemetry["total_tokens"], "cost_usd": result.telemetry["estimated_cost_usd"], "model_path": [tier for tier in result.telemetry["by_tier"]], "gate": result.gate["answers"]}


def induced_failure_case():
    telemetry = Telemetry("benchmark-induced-escalation")
    router = InducedFailureRouter(telemetry)
    runtime = AgentRuntime(telemetry, validate_models=True)
    result = JEVOrchestrator(run_name="benchmark-induced-escalation", router=router, runtime=runtime, budget=Budget(max_luna_rounds=1)).execute(TASK)
    return {"output": result.output, "tokens": result.telemetry["total_tokens"], "cost_usd": result.telemetry["estimated_cost_usd"], "model_path": [tier for tier in result.telemetry["by_tier"]], "gate": result.gate["answers"], "note": "The first gate failure is deliberately induced; it is not a claim that Luna failed naturally."}


def main():
    cases = [
        ("deterministic", deterministic_case),
        ("baseline_direct_sol_subscription", direct_sol_case),
        ("luna_first_with_jev", luna_first_case),
        ("luna_first_to_sol_induced_failure", induced_failure_case),
    ]
    report = {"task": TASK, "cases": {}}
    for name, fn in cases:
        key, value = _record(name, fn)
        report["cases"][key] = value
    report["comparison_policy"] = "Only completed cases contain measured model metrics; unavailable or failed cases remain explicitly marked."
    out = Path("telemetry") / "benchmark-suite-latest.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
