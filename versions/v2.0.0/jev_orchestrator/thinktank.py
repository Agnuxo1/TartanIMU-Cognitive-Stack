"""Bounded multi-model deliberation on top of the JEV router.

The thinktank is deliberately conditional.  JEV decides whether the extra
tokens are justified; the runtime executes bounded independent views and one
critic using the authenticated Codex subscription backend.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .catalog import AGENT_MODELS
from .config import Budget, DEFAULT_BUDGET
from .deterministic import compress_context
from .runtime import AgentResult, AgentRuntime
from .router import JevRouter
from .telemetry import Telemetry


@dataclass
class ThinktankResult:
    used: bool
    decision: dict[str, Any]
    views: list[AgentResult]
    critic: AgentResult | None
    final_output: str
    gate: dict[str, Any] | None
    model_path: list[str]
    human_checkpoint: bool
    failures: list[str]


class Thinktank:
    """Run the smallest independent-view panel justified by JEV."""

    def __init__(self, router: JevRouter, runtime: AgentRuntime, telemetry: Telemetry, budget: Budget = DEFAULT_BUDGET) -> None:
        self.router = router
        self.runtime = runtime
        self.telemetry = telemetry
        self.budget = budget

    @staticmethod
    def _value(payload: dict[str, Any], key: str, default: Any = None) -> Any:
        return payload.get("answers", {}).get(key, {}).get("value", default)

    @staticmethod
    def _tier(agent: str) -> str:
        return AGENT_MODELS.get(agent, "unknown")

    def run(
        self,
        task: str,
        context: str = "",
        *,
        risk: str = "moderate",
        uncertainty: float = 0.0,
        conflicting_evidence: bool = False,
        primary_agent: str = "luna_scout",
        force: bool = False,
    ) -> ThinktankResult:
        decision = self.router.deliberation({
            "objective": task,
            "task": task,
            "risk": risk,
            "uncertainty": uncertainty,
            "conflicting_evidence": conflicting_evidence,
            "acceptance_criteria": "Evidence-backed answer satisfying the original objective.",
            "facts": compress_context(context, self.budget.max_handoff_chars),
        })
        mode = str(self._value(decision, "mode", "single_worker"))
        use_panel = force or float(self._value(decision, "use_thinktank", 0.0) or 0.0) >= 0.5
        human_checkpoint = float(self._value(decision, "human_checkpoint", 0.0) or 0.0) >= 0.5
        self.telemetry.event("thinktank_plan", {"decision": decision.get("answers", {}), "mode": mode, "forced": force, "risk": risk})

        if not use_panel or mode == "single_worker":
            result = self.runtime.run(primary_agent, task, compress_context(context, self.budget.max_handoff_chars), use_web=False)
            gate = self.router.gate(task, compress_context(result.output, 7000), [])
            self.telemetry.event("thinktank_skipped", {"reason": "panel_not_justified", "agent": primary_agent, "gate": gate.get("answers", {})})
            return ThinktankResult(False, decision, [result], None, result.output, gate, [self._tier(primary_agent)], human_checkpoint, [])

        view_agents = [primary_agent if primary_agent in AGENT_MODELS and AGENT_MODELS[primary_agent] == "luna" else "luna_scout", "sol_researcher"]
        view_agents = list(dict.fromkeys(view_agents))[: self.budget.max_thinktank_views]
        base_context = compress_context(
            "OBJECTIVE:\n" + task + "\n\nCOMPACT FACTS:\n" + context +
            "\n\nINDEPENDENCE RULE:\nAnalyze independently. Separate observed facts, inferences, assumptions, disagreements, and a recommendation.",
            self.budget.max_handoff_chars,
        )
        views: list[AgentResult] = []
        failures: list[str] = []
        for index, agent in enumerate(view_agents, start=1):
            try:
                result = self.runtime.run(
                    agent,
                    f"Independent view {index}. Do not defer to another worker; produce a compact evidence-based analysis of the objective.",
                    base_context,
                    use_web=False,
                )
                views.append(result)
                self.telemetry.event("thinktank_view", {"index": index, "agent": agent, "model": result.model})
            except Exception as exc:
                failures.append(f"{agent}:{type(exc).__name__}")
                self.telemetry.event("thinktank_view_failed", {"index": index, "agent": agent, "reason": type(exc).__name__})

        if not views:
            raise RuntimeError("Thinktank produced no usable independent view.")

        critic_tier = str(self._value(decision, "critic_tier", "sol"))
        critic_agent = "astra_reviewer" if critic_tier == "astra" or mode == "three_role_debate" else "sol_scientist"
        evidence = "\n\n".join(f"VIEW {index} ({view.agent}, {view.model}):\n{compress_context(view.output, 2800)}" for index, view in enumerate(views, start=1))
        critic_context = compress_context("OBJECTIVE:\n" + task + "\n\nINDEPENDENT VIEWS:\n" + evidence + "\n\nCOMPACT FACTS:\n" + context, self.budget.max_handoff_chars)
        critic: AgentResult | None = None
        try:
            critic = self.runtime.run(
                critic_agent,
                "Act as the independent critic and gatekeeper. Compare the views against the objective and acceptance criteria. Do not use majority vote: identify which claims are evidenced, resolve disagreements, state unresolved blockers, and give one recommendation.",
                critic_context,
                use_web=False,
            )
            self.telemetry.event("thinktank_critic", {"agent": critic_agent, "model": critic.model})
        except Exception as exc:
            failures.append(f"{critic_agent}:{type(exc).__name__}")
            self.telemetry.event("thinktank_critic_failed", {"agent": critic_agent, "reason": type(exc).__name__})

        final_output = critic.output if critic is not None else views[0].output
        unresolved = list(failures)
        if len(views) < 2:
            unresolved.append("independent_view_missing")
        gate = self.router.gate(task, compress_context(final_output + "\n\n" + evidence, 7000), unresolved)
        model_path = [self._tier(item.agent) for item in views]
        if critic is not None:
            model_path.append(self._tier(critic.agent))
        self.telemetry.event("thinktank_final", {"mode": mode, "model_path": model_path, "failures": failures, "gate": gate.get("answers", {})})
        return ThinktankResult(True, decision, views, critic, final_output, gate, model_path, human_checkpoint, failures)
