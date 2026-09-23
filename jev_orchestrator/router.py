"""TypeSafe Jev director, supervisor, and completion gatekeeper."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from typesafe_sdk import Choice, Noul, Score

from .catalog import AGENTS, CONTEXT_POLICIES, PLUGINS, RESEARCH_METHODS, SKILLS, SUCCESS_CRITERIA, TOOLS, WORK_METHODS
from .config import CACHE_DIR, POLICY_VERSION, TYPESAFE_MODEL, TYPESAFE_TIMEOUT_SECONDS
from .connection import JevConnectionError, create_jev_client
from .telemetry import Telemetry, Usage

MODEL_CHOICES = {
    "none": "No generative model is needed; use deterministic code or a specialized tool.",
    "luna": "Mandatory first attempt for every task that needs an LLM, regardless of initial complexity.",
    "sol": "Eligible only after observable Luna failure or insufficiency.",
    "astra": "Eligible only after Sol failure or insufficiency as a last resort.",
}

class JevRouter:
    """Keep semantic decisions in Jev while enforcing safety policy in code."""

    def __init__(self, telemetry: Telemetry, use_cache: bool = True, client: Any | None = None) -> None:
        self.telemetry = telemetry
        self.use_cache = use_cache
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.client = client
        if self.client is None:
            try:
                self.client = create_jev_client(timeout=TYPESAFE_TIMEOUT_SECONDS)
                self.telemetry.event("jev_connection_ready", {"credential_count": self.client.credential_count})
            except JevConnectionError:
                self.client = None

    def _cache_path(self, prefix: str, state: dict[str, Any], questions: dict[str, Any]) -> Path:
        material = {"policy_version": POLICY_VERSION, "typesafe_model": TYPESAFE_MODEL, "prefix": prefix, "state": state, "questions": json.dumps(questions, sort_keys=True, ensure_ascii=False, default=str)}
        raw = json.dumps(material, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        return CACHE_DIR / f"{prefix}-{hashlib.sha256(raw).hexdigest()}.json"

    @staticmethod
    def _answer_payload(answer: Any) -> dict[str, Any]:
        if hasattr(answer, "choice"):
            return {"value": answer.choice, "probabilities": dict(answer.probabilities), "confidence": getattr(answer, "confidence", None)}
        if hasattr(answer, "noul"):
            return {"value": float(answer.noul)}
        return {"value": float(answer.score), "confidence": getattr(answer, "confidence", None)}

    def _run(self, prefix: str, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        cache_path = self._cache_path(prefix, state, questions)
        if self.use_cache and cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            cached.setdefault("provenance", "jev" if cached.get("decision_source") == "typesafe_jev" else "local")
            self.telemetry.event("jev_cache_hit", {"prefix": prefix, "path": str(cache_path)})
            return cached
        if self.client is None:
            fallback = self._fallback(prefix, state)
            self.telemetry.event("jev_unavailable", {"prefix": prefix, "reason": "missing_typesafe_key_or_client", "decision_source": "policy_fallback"})
            return fallback
        started = time.perf_counter()
        try:
            response = self.client.system_one(state=state, questions=questions, model=TYPESAFE_MODEL, timeout=TYPESAFE_TIMEOUT_SECONDS)
        except Exception as exc:
            fallback = self._fallback(prefix, state)
            self.telemetry.event("jev_unavailable", {"prefix": prefix, "reason": type(exc).__name__, "decision_source": "policy_fallback"})
            return fallback
        latency = time.perf_counter() - started
        answers = {name: self._answer_payload(answer) for name, answer in response.answers.items()}
        cached_tokens = int(getattr(response.usage, "cached_input_tokens", getattr(response.usage, "cached_tokens", 0)) or 0)
        payload = {"answers": answers, "model": response.model, "decision_source": "typesafe_jev", "provenance": "jev", "usage": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "cached_tokens": cached_tokens}}
        self.telemetry.add_usage(Usage("jev", response.model, response.usage.input_tokens, response.usage.output_tokens, cached_tokens=cached_tokens, latency_seconds=latency, tier="jev", backend="typesafe"))
        self.telemetry.event("jev_decision", {"prefix": prefix, "answers": answers, "decision_source": "typesafe_jev"})
        cache_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    @staticmethod
    def _choice(value: str, confidence: float = 1.0) -> dict[str, Any]:
        return {"value": value, "probabilities": {value: confidence}, "confidence": confidence}

    @staticmethod
    def _noul(value: float) -> dict[str, Any]:
        return {"value": value}

    def _fallback(self, prefix: str, state: dict[str, Any]) -> dict[str, Any]:
        task = str(state.get("task", state.get("objective", ""))).lower()
        coding = any(word in task for word in ("code", "python", "repository", "debug", "test", "implement"))
        opportunity = any(word in task for word in ("subvención", "subvenciones", "grant", "funding", "convocatoria", "convocatorias", "premio", "premios", "concurso", "concursos", "presentación de proyecto", "project presentation", "award"))
        web = any(word in task for word in ("current", "latest", "today", "research", "source", "paper", "web")) or opportunity
        editorial_rights = any(word in task for word in ("copyright", "exclusiv", "contract", "licen", "isbn", "rights"))
        editorial_marketing = any(word in task for word in ("marketing", "ventas", "venta", "outreach", "reseña", "discoverability"))
        editorial = any(word in task for word in ("editorial", "libro", "novela", "bubok", "lulu", "publicar", "catálogo", "manuscrito"))
        if prefix == "initial":
            if opportunity:
                fallback_agent, fallback_skill, fallback_model = "luna_opportunity_scout", "opportunity_discovery", "luna"
                fallback_tool, fallback_method, fallback_work = "openai_web_search", "official_call_documents", "progressive_escalation"
                fallback_success = "application_ready" if any(word in task for word in ("solicitud", "aplicación", "application", "formulario", "submit", "enviar")) else "evidence_backed"
            elif editorial_rights:
                fallback_agent, fallback_skill, fallback_model = "luna_reader", "rights_and_contracts", "luna"
                fallback_tool, fallback_method, fallback_work, fallback_success = "openai_web_search" if web else "deterministic_local", "contract_review", "editorial_preflight", "rights_verified"
            elif editorial_marketing:
                fallback_agent, fallback_skill, fallback_model = "luna_editor", "book_marketing", "luna"
                fallback_tool, fallback_method, fallback_work, fallback_success = "openai_web_search" if web else "editorial_workspace", "market_scan", "editorial_preflight", "sales_pipeline_updated"
            elif editorial:
                fallback_agent, fallback_skill, fallback_model = "luna_editor", "editorial_operations", "luna"
                fallback_tool, fallback_method, fallback_work, fallback_success = "editorial_workspace", "progressive_disclosure", "editorial_preflight", "complete_workflow"
            else:
                fallback_agent = "luna_coder" if coding else "luna_scout"
                fallback_skill = "python_debugging" if coding else "general"
                fallback_model = "luna"
                fallback_tool, fallback_method, fallback_work, fallback_success = "openai_web_search" if web else "deterministic_local", "targeted_search" if web else "none", "progressive_escalation", "complete_workflow"
            values = {"agent": self._choice(fallback_agent), "tool": self._choice(fallback_tool), "skill": self._choice(fallback_skill), "research_method": self._choice(fallback_method), "work_method": self._choice(fallback_work), "model_level": self._choice(fallback_model), "deterministic": self._noul(0.0), "needs_web": self._noul(1.0 if web else 0.0), "complexity": {"value": 0.5, "confidence": 0.2}, "context_policy": self._choice("evidence_chain" if opportunity else "minimal"), "success_criteria": self._choice(fallback_success)}
        elif prefix == "supervise":
            values = {"next_action": self._choice("continue"), "handoff_mode": self._choice("continue_from_luna"), "on_track": self._noul(0.5), "need_more_research": self._noul(0.0), "ready_for_gate": self._noul(0.0)}
        elif prefix == "deliberation":
            risk = str(state.get("risk", "moderate")).lower()
            needs_human = risk in {"high", "critical"} or bool(state.get("irreversible"))
            values = {
                "mode": self._choice("single_worker"),
                "use_thinktank": self._noul(0.0),
                "critic_tier": self._choice("sol"),
                "human_checkpoint": self._noul(1.0 if needs_human else 0.0),
            }
        else:
            values = {"ready": self._noul(0.0), "needs_stronger_review": self._noul(1.0), "quality": {"value": 0.25, "confidence": 0.2}}
        return {"answers": values, "model": "policy-fallback", "decision_source": "policy_fallback", "provenance": "local", "usage": {"input_tokens": 0, "output_tokens": 0}}

    def initial(self, task: str, context_summary: str = "") -> dict[str, Any]:
        state = {
            "task": task,
            "context_summary": context_summary[:5000],
            "constraints": ["Resolve deterministic work before any LLM.", "Luna must attempt every LLM task first, including complex tasks.", "Use progressive disclosure.", "Escalate only when observable evidence supports it."],
            "resources": {"agents": list(AGENTS), "tools": list(TOOLS), "plugins": list(PLUGINS), "skills": list(SKILLS), "context_policies": list(CONTEXT_POLICIES), "success_criteria": list(SUCCESS_CRITERIA)},
        }
        questions = {
            "agent": Choice(instructions="Select the best initial role for Luna's first attempt. Do not select a Sol or Astra role for the initial attempt.", criteria=AGENTS),
            "tool": Choice(instructions="Select the first tool or application; prefer deterministic or host-integrated tools.", criteria=TOOLS),
            "skill": Choice(instructions="Select the skill to disclose first.", criteria=SKILLS),
            "research_method": Choice(instructions="Select the narrowest useful research method.", criteria=RESEARCH_METHODS),
            "work_method": Choice(instructions="Select the work method; Luna-first and event-driven supervision are mandatory for LLM work.", criteria=WORK_METHODS),
            "model_level": Choice(instructions="Select the initial capability knowing policy code will enforce Luna first; Sol and Astra are escalation tiers only.", criteria=MODEL_CHOICES),
            "deterministic": Noul(instructions="Can the core task be solved reliably with deterministic code or an exact specialized tool without a generative model?"),
            "needs_web": Noul(instructions="Does the task require current information from the web?"),
            "complexity": Score(instructions="Rate overall reasoning complexity after considering the task, not as a reason to skip Luna.", criteria=["Trivial", "Routine", "Moderate", "Complex", "Exceptional"]),
            "context_policy": Choice(instructions="Select the minimum context disclosure policy for the first action.", criteria=CONTEXT_POLICIES),
            "success_criteria": Choice(instructions="Select the most important completion criterion.", criteria=SUCCESS_CRITERIA),
        }
        return self._run("initial", state, questions)

    def local_initial_fallback(self, task: str) -> dict[str, Any]:
        """Return a conservative local Luna-first route when no checkpoint is available."""
        payload = self._fallback("initial", {"task": task})
        payload["decision_source"] = "budget_fallback"
        payload["provenance"] = "local"
        return payload

    def supervise(self, state: dict[str, Any]) -> dict[str, Any]:
        compact = {k: state[k] for k in state if k in {"objective", "phase", "agent", "model_level", "tool", "findings", "problems", "observed_failures", "round", "tokens_used", "candidate_next_actions", "success_criteria"}}
        questions = {
            "next_action": Choice(instructions="Choose the next bounded action. Continue Luna unless observable evidence supports escalation.", criteria={
                "continue": "Continue current plan.",
                "change_tool": "Change tool or application.",
                "change_agent": "Change specialist without increasing model tier.",
                "escalate_sol": "Escalate to Sol.",
                "escalate_astra": "Escalate to Astra.",
            "finish": "The objective is ready for the final gate.",
            }),
            "handoff_mode": Choice(instructions="If escalation becomes justified, choose whether Sol should use a compressed factual Luna handoff or restart from the objective.", criteria={"continue_from_luna": "Reuse only compact verified findings and failures.", "restart_with_sol": "Discard Luna's work and give Sol the objective and acceptance criteria only."}),
            "on_track": Noul(instructions="Is the current work on track to satisfy the original objective efficiently?"),
            "need_more_research": Noul(instructions="Is additional research necessary before completion?"),
            "ready_for_gate": Noul(instructions="Is the work mature enough for a final completion check?"),
        }
        return self._run("supervise", compact, questions)

    def gate(self, objective: str, result_summary: str, unresolved: list[str] | None = None) -> dict[str, Any]:
        state = {"objective": objective, "result_summary": result_summary[:7000], "unresolved": unresolved or []}
        questions = {
            "ready": Noul(instructions="Does the result satisfy the stated objective sufficiently to deliver, including its acceptance criteria?"),
            "needs_stronger_review": Noul(instructions="Would a stronger model materially improve correctness or completeness based on concrete gaps?"),
            "quality": Score(instructions="Rate completion quality using the evidence supplied.", criteria=["Incomplete", "Weak", "Acceptable", "Strong", "Excellent"]),
        }
        return self._run("gate", state, questions)

    def deliberation(self, state: dict[str, Any]) -> dict[str, Any]:
        """Decide whether a bounded independent-view panel justifies its cost."""
        compact = {
            key: state[key]
            for key in (
                "objective", "task", "risk", "uncertainty", "conflicting_evidence",
                "acceptance_criteria", "facts", "constraints",
            )
            if key in state
        }
        questions = {
            "mode": Choice(
                instructions="Choose the smallest useful deliberation mode; agreement is not evidence.",
                criteria={
                    "single_worker": "One Luna worker is sufficient; do not fan out.",
                    "two_independent_then_critic": "Use two independent views and one critic only for material uncertainty or disagreement.",
                    "three_role_debate": "Use a third role only for high-impact unresolved disagreement that needs a stronger critic.",
                },
            ),
            "use_thinktank": Noul(instructions="Would an independent-model panel materially improve this decision enough to justify its token and latency cost?"),
            "critic_tier": Choice(
                instructions="Select the least capable critic tier sufficient for the evidence and risk.",
                criteria={"sol": "Use a Sol-level critic.", "astra": "Use Astra only when high impact and unresolved complexity justify it."},
            ),
            "human_checkpoint": Noul(instructions="Does this task need a human checkpoint before an external, irreversible, financial, legal, or public action? This answer is advice, not authorization."),
        }
        return self._run("deliberation", compact, questions)
