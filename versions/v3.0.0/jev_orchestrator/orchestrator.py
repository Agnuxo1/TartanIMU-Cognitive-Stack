"""End-to-end JEV-directed orchestration loop."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .catalog import AGENT_MODELS, LOCAL_TOOL_EXECUTORS, PLUGIN_HOSTS
from .config import Budget, DEFAULT_BUDGET
from .deterministic import compress_context, deterministic_route
from .router import JevRouter
from .runtime import AgentRuntime
from .telemetry import Telemetry

@dataclass
class OrchestrationResult:
    output: str
    route: dict[str, Any]
    supervisor: dict[str, Any] | None
    gate: dict[str, Any] | None
    telemetry: dict[str, Any]

class JEVOrchestrator:
    def __init__(self, run_name: str = "run", use_cache: bool = True, router: JevRouter | None = None, runtime: AgentRuntime | None = None, budget: Budget = DEFAULT_BUDGET) -> None:
        self._compat_client = run_name if not isinstance(run_name, str) and hasattr(run_name, "evaluate") else None
        if self._compat_client is not None:
            run_name = "compatibility"
        self.telemetry = Telemetry(run_name)
        self.router = router or JevRouter(self.telemetry, use_cache=use_cache)
        self.runtime = runtime or AgentRuntime(self.telemetry, validate_models=False)
        self.budget = budget

    def route(self, objective: str, context: dict[str, Any] | None = None) -> Any:
        """Compatibility entry point for agents using the original client facade."""
        if self._compat_client is None:
            return self.router.initial(objective, str(context or ""))
        from .client import JEVResponse

        response = self._compat_client.evaluate(
            {"objective": objective, "context": context or {}},
            {
                "agent": {"type": "choice", "instructions": "Select the initial agent role.", "criteria": {"luna": "Use Luna first", "sol": "Escalation only", "astra": "Last resort only"}},
                "model": {"type": "choice", "instructions": "Select the initial model tier.", "criteria": {"luna": "Mandatory first attempt", "sol": "After Luna evidence", "astra": "After Sol evidence"}},
                "needs_supervision": {"type": "noul", "instructions": "Does this task need event-driven supervision?"},
            },
        )
        return response

    def gatekeep(self, result: dict[str, Any]) -> Any:
        """Compatibility completion gate for older agent integrations."""
        if self._compat_client is None:
            return self.router.gate(str(result.get("objective", "")), str(result))
        return self._compat_client.evaluate(
            result,
            {
                "ready": {"type": "noul", "instructions": "Is the work ready to deliver?"},
                "policy_ok": {"type": "noul", "instructions": "Does the work comply with the orchestration policy?"},
            },
        )

    @staticmethod
    def _value(route: dict[str, Any], key: str) -> Any:
        return route.get("answers", {}).get(key, {}).get("value")

    @staticmethod
    def _confidence(route: dict[str, Any], key: str) -> float:
        answer = route.get("answers", {}).get(key, {})
        return float(answer.get("confidence", 1.0) or 0.0)

    @staticmethod
    def _route_agent(route: dict[str, Any]) -> str:
        requested = str(JEVOrchestrator._value(route, "agent") or "luna_scout")
        skill = str(JEVOrchestrator._value(route, "skill") or "general")
        if requested in AGENT_MODELS and AGENT_MODELS[requested] == "luna":
            return requested
        if skill == "opportunity_discovery":
            return "luna_opportunity_scout"
        if skill == "grant_application":
            return "luna_application_writer"
        if skill == "submission_compliance":
            return "luna_form_filler"
        if skill == "editorial_operations":
            return "luna_editor" if "luna_editor" in AGENT_MODELS else "luna_scout"
        if skill == "publishing_metadata":
            return "luna_metadata" if "luna_metadata" in AGENT_MODELS else "luna_reader"
        if skill in {"python_debugging", "repository_analysis"}:
            return "luna_coder"
        if skill == "general":
            return "luna_scout"
        return "luna_reader"

    @staticmethod
    def _is_opportunity_task(task: str) -> bool:
        lowered = task.lower()
        return any(word in lowered for word in ("subvención", "subvenciones", "grant", "funding", "convocatoria", "convocatorias", "premio", "premios", "concurso", "concursos", "presentación de proyecto", "project presentation", "award"))

    @classmethod
    def _escalation_agent(cls, task: str, tier: str) -> str:
        if cls._is_opportunity_task(task):
            return "sol_grants_researcher" if tier == "sol" else "astra_submission_auditor"
        return "sol_engineer" if tier == "sol" else "astra_architect"

    @staticmethod
    def _is_ready(gate: dict[str, Any], budget: Budget) -> bool:
        answers = gate.get("answers", {})
        ready = float(answers.get("ready", {}).get("value", 0.0) or 0.0)
        quality = float(answers.get("quality", {}).get("value", 0.0) or 0.0)
        normalized_quality = quality / 4.0 if quality > 1.0 else quality
        return ready >= budget.gate_ready_threshold and normalized_quality >= budget.gate_quality_threshold

    @staticmethod
    def _failure_evidence(state: dict[str, Any], gate: dict[str, Any] | None, round_number: int, budget: Budget) -> list[str]:
        evidence = list(state.get("observed_failures", []))
        if round_number >= budget.max_luna_rounds:
            evidence.append("max_luna_rounds_reached_without a satisfied gate")
        if state.get("problems"):
            evidence.extend(str(item) for item in state["problems"])
        if gate and not JEVOrchestrator._is_ready(gate, budget):
            evidence.append("gatekeeper_not_satisfied")
        if float(state.get("on_track", 1.0) or 0.0) < budget.escalation_on_low_confidence:
            evidence.append("low_on_track_probability")
        return list(dict.fromkeys(evidence))

    def _supervise(self, state: dict[str, Any]) -> dict[str, Any]:
        checkpoint = self.router.supervise(state)
        self.telemetry.event("supervision_checkpoint", {"round": state.get("round"), "phase": state.get("phase"), "answers": checkpoint.get("answers", {})})
        return checkpoint

    def _run_agent(self, agent: str, task: str, context: str, tool: str, needs_web: bool, round_number: int, phase: str):
        web_tools = {"exa", "firecrawl", "context7", "github", "scite", "openai_web_search"}
        if tool in PLUGIN_HOSTS and tool not in LOCAL_TOOL_EXECUTORS:
            self.telemetry.event("plugin_host_handoff", {"plugin": tool, "host": PLUGIN_HOSTS[tool], "status": "selection_recorded_only", "executed_locally": False, "fallback": "openai_web_search" if needs_web else "none"})
        self.telemetry.event("agent_started", {"agent": agent, "model_level": AGENT_MODELS[agent], "round": round_number, "phase": phase, "tool": tool})
        return self.runtime.run(agent, task, context, use_web=needs_web or tool in web_tools)

    def execute(self, task: str, context: str = "") -> OrchestrationResult:
        self.telemetry.event("task_started", {"objective": task, "budget": self.budget.__dict__})
        deterministic = deterministic_route(task)
        if bool(deterministic["handled"]):
            output = str(deterministic["result"])
            gate = {"answers": {"ready": {"value": 1.0}, "needs_stronger_review": {"value": 0.0}, "quality": {"value": 1.0}}, "model": "deterministic", "decision_source": "code"}
            route = {"answers": {"model_level": {"value": "none"}, "deterministic": {"value": 1.0}}, "model": "deterministic", "decision_source": "code"}
            self.telemetry.event("deterministic_short_circuit", {"kind": deterministic["kind"], "result": output, "llm_calls": 0})
            self.telemetry.event("final", {"gate": gate["answers"], "model_path": ["deterministic"], "escalation": None})
            return OrchestrationResult(output, route, None, gate, self.telemetry.summary())

        route = self.router.initial(task, compress_context(context, 5000))
        self.telemetry.event("initial_route", {"answers": route.get("answers", {}), "decision_source": route.get("decision_source")})
        tool = str(self._value(route, "tool") or "desktop_commander")
        needs_web = float(self._value(route, "needs_web") or 0.0) >= 0.50
        agent = self._route_agent(route)
        requested_level = str(self._value(route, "model_level") or "luna")
        effective_level = AGENT_MODELS.get(agent, "luna")
        if requested_level != effective_level:
            self.telemetry.event("route_normalized", {"requested_model_level": requested_level, "effective_model_level": effective_level, "agent": agent})
        working_context = compress_context(context, self.budget.max_handoff_chars)
        findings: list[str] = []
        problems: list[str] = []
        observed_failures: list[str] = []
        output = ""
        supervisor: dict[str, Any] | None = None
        gate: dict[str, Any] | None = None
        model_path = [effective_level]
        rounds = 0

        while rounds < self.budget.max_luna_rounds and len(model_path) <= self.budget.max_agent_calls:
            if self.telemetry.summary()["total_tokens"] >= self.budget.max_total_tokens:
                observed_failures.append("total_token_budget_exhausted_before_next_luna_round")
                self.telemetry.event("budget_exhausted", {"budget": self.budget.max_total_tokens, "phase": "luna"})
                break
            rounds += 1
            result = self._run_agent(agent, task, working_context, tool, needs_web, rounds, "luna")
            output = result.output
            findings.append(compress_context(output, 3500))
            state = {"objective": task, "phase": "luna_round", "agent": agent, "model_level": "luna", "tool": tool, "findings": findings[-3:], "problems": problems, "observed_failures": observed_failures, "round": rounds, "tokens_used": self.telemetry.summary()["total_tokens"], "success_criteria": self._value(route, "success_criteria"), "candidate_next_actions": ["continue", "change_tool", "change_agent", "escalate_sol", "finish"]}
            supervisor = self._supervise(state)
            action = str(self._value(supervisor, "next_action") or "continue")
            state["on_track"] = self._value(supervisor, "on_track")
            if action == "finish" or rounds >= self.budget.max_luna_rounds:
                gate = self.router.gate(task, compress_context(output, 7000), problems)
                self.telemetry.event("gate_checkpoint", {"phase": "luna", "round": rounds, "answers": gate.get("answers", {})})
                if self._is_ready(gate, self.budget):
                    break
                observed_failures = self._failure_evidence(state, gate, rounds, self.budget)
                break
            if action in {"continue", "change_tool", "change_agent"}:
                if action == "change_tool":
                    tool = "openai_web_search" if needs_web else "desktop_commander"
                    self.telemetry.event("tool_changed", {"tool": tool, "round": rounds})
                elif action == "change_agent":
                    agent = "luna_coder" if agent != "luna_coder" else "luna_reader"
                working_context = compress_context("\n\n".join(findings[-2:]), self.budget.max_handoff_chars)
                continue
            observed_failures = self._failure_evidence(state, None, rounds, self.budget)
            break

        if gate is None:
            gate = self.router.gate(task, compress_context(output, 7000), problems)
            self.telemetry.event("gate_checkpoint", {"phase": "luna", "round": rounds, "answers": gate.get("answers", {})})

        if not self._is_ready(gate, self.budget):
            observed_failures = list(dict.fromkeys(observed_failures + self._failure_evidence({"problems": problems, "observed_failures": observed_failures, "on_track": self._value(supervisor or {}, "on_track")}, gate, rounds, self.budget)))
            self.telemetry.event("pre_escalation", {"from": "luna", "evidence": observed_failures, "gate": gate.get("answers", {})})
            mode = str(self._value(supervisor or {}, "handoff_mode") or "continue_from_luna")
            sol_context = compress_context("OBJECTIVE:\n" + task + "\n\nACCEPTANCE CRITERIA:\n" + str(self._value(route, "success_criteria")) + "\n\nOBSERVED LUNA FINDINGS:\n" + "\n".join(findings[-2:]) + "\n\nOBSERVED FAILURES:\n" + "\n".join(observed_failures), self.budget.max_handoff_chars) if mode == "continue_from_luna" else compress_context("OBJECTIVE:\n" + task + "\n\nACCEPTANCE CRITERIA:\n" + str(self._value(route, "success_criteria")), self.budget.max_handoff_chars)
            self.telemetry.event("escalation_decision", {"from": "luna", "to": "sol", "mode": mode, "evidence": observed_failures})
            sol = self._run_agent(self._escalation_agent(task, "sol"), task, sol_context, tool, needs_web, 1, "sol")
            output = sol.output
            model_path.append("sol")
            sol_state = {"objective": task, "phase": "post_sol", "agent": sol.agent, "model_level": "sol", "tool": tool, "findings": [compress_context(output, 5000)], "problems": observed_failures, "observed_failures": observed_failures, "round": 1, "tokens_used": self.telemetry.summary()["total_tokens"], "candidate_next_actions": ["finish", "escalate_astra"]}
            supervisor = self._supervise(sol_state)
            gate = self.router.gate(task, compress_context(output, 7000), observed_failures)
            self.telemetry.event("gate_checkpoint", {"phase": "sol", "answers": gate.get("answers", {})})

        if not self._is_ready(gate, self.budget) and len(model_path) < self.budget.max_agent_calls:
            self.telemetry.event("pre_escalation", {"from": "sol", "to": "astra", "evidence": observed_failures, "gate": gate.get("answers", {})})
            astra = self._run_agent(self._escalation_agent(task, "astra"), task, compress_context("OBJECTIVE:\n" + task + "\n\nSOL OUTPUT:\n" + output + "\n\nUNRESOLVED:\n" + "\n".join(observed_failures), self.budget.max_handoff_chars), tool, needs_web, 1, "astra")
            output = astra.output
            model_path.append("astra")
            gate = self.router.gate(task, compress_context(output, 7000), observed_failures)
            self.telemetry.event("gate_checkpoint", {"phase": "astra", "answers": gate.get("answers", {})})

        self.telemetry.event("final", {"gate": gate.get("answers", {}), "model_path": model_path, "rounds": rounds, "observed_failures": observed_failures, "escalation": model_path[1:] or None})
        return OrchestrationResult(output, route, supervisor, gate, self.telemetry.summary())
