"""TypeSafe Jev director, supervisor, and completion gatekeeper."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from .catalog import AGENTS, CONSENSUS_RULES, CONTEXT_POLICIES, DELIBERATION_MODES, PLUGINS, RESEARCH_METHODS, SKILLS, SUCCESS_CRITERIA, TOOLS, WORK_METHODS
from .config import CACHE_DIR, POLICY_VERSION, TYPESAFE_MODEL, TYPESAFE_TIMEOUT_SECONDS
from .connection import JEVConnectionError, create_client, resolve_credentials
from .credentials import normalize_profile
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
        self.profile = normalize_profile()
        self.client = client
        self._credentials = resolve_credentials(profile=self.profile) if self.client is None else []
        self._credential_index = 0
        if self.client is None:
            try:
                self.client = create_client(profile=self.profile, credential=self._credentials[0] if self._credentials else None)
            except JEVConnectionError as exc:
                self.telemetry.event("jev_unavailable", {"reason": type(exc).__name__, "detail": str(exc)[:300]})

    def _cache_path(self, prefix: str, state: dict[str, Any], questions: dict[str, Any]) -> Path:
        material = {"policy_version": POLICY_VERSION, "typesafe_model": TYPESAFE_MODEL, "typesafe_profile": self.profile, "prefix": prefix, "state": state, "questions": json.dumps(questions, sort_keys=True, ensure_ascii=False, default=str)}
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
            self.telemetry.event("jev_cache_hit", {"prefix": prefix, "path": str(cache_path)})
            return cached
        if self.client is None:
            fallback = self._fallback(prefix, state)
            self.telemetry.event("jev_unavailable", {"prefix": prefix, "reason": "missing_typesafe_key_or_client", "decision_source": "policy_fallback"})
            return fallback
        started = time.perf_counter()
        response = None
        last_exc: Exception | None = None
        while self.client is not None:
            try:
                response = self.client.system_one(state=state, questions=questions, model=TYPESAFE_MODEL, timeout=TYPESAFE_TIMEOUT_SECONDS)
                break
            except Exception as exc:
                last_exc = exc
                detail = str(exc).lower()
                auth_failure = any(token in detail for token in ("401", "403", "unauthorized", "authentication", "invalid api key"))
                next_index = self._credential_index + 1
                if not auth_failure or next_index >= len(self._credentials):
                    break
                self._credential_index = next_index
                self.client = create_client(profile=self.profile, credential=self._credentials[self._credential_index])
        if response is None:
            exc = last_exc or RuntimeError("TypeSafe client unavailable")
            fallback = self._fallback(prefix, state)
            self.telemetry.event("jev_unavailable", {"prefix": prefix, "reason": type(exc).__name__, "detail": str(exc)[:300], "decision_source": "policy_fallback"})
            return fallback
        latency = time.perf_counter() - started
        answers = {name: self._answer_payload(answer) for name, answer in response.answers.items()}
        cached_tokens = int(getattr(response.usage, "cached_input_tokens", getattr(response.usage, "cached_tokens", 0)) or 0)
        payload = {"answers": answers, "model": response.model, "decision_source": "typesafe_jev", "usage": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "cached_tokens": cached_tokens}}
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
        web = any(word in task for word in ("current", "latest", "today", "research", "source", "paper", "web"))
        opportunity = any(word in task for word in ("subvención", "subvenciones", "grant", "funding", "convocatoria", "convocatorias", "premio", "premios", "concurso", "concursos", "presentación de proyecto", "project presentation", "award"))
        web = web or opportunity
        risk = str(state.get("risk", "moderate")).lower()
        uncertainty = float(state.get("uncertainty", 0.0) or 0.0)
        conflict = bool(state.get("conflicting_evidence") or state.get("observed_conflicts"))
        high_impact = risk in {"high", "critical"} or any(word in task for word in ("publish", "publication", "rights", "contract", "money", "payment", "security", "submit", "send", "irreversible"))
        editorial_rights = any(word in task for word in ("copyright", "exclusiv", "contract", "licen", "isbn", "rights"))
        editorial_marketing = any(word in task for word in ("marketing", "ventas", "venta", "outreach", "reseña", "discoverability"))
        editorial = any(word in task for word in ("editorial", "libro", "novela", "bubok", "lulu", "publicar", "catálogo", "manuscrito"))
        if prefix == "initial":
            if opportunity:
                fallback_agent, fallback_skill, fallback_model = "luna_opportunity_scout", "opportunity_discovery", "luna"
                fallback_tool, fallback_method, fallback_work, fallback_success = "openai_web_search", "official_call_documents", "progressive_escalation", "application_ready" if any(word in task for word in ("solicitud", "aplicación", "application", "formulario", "submit", "enviar")) else "evidence_backed"
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
            values = {"agent": self._choice(fallback_agent), "tool": self._choice(fallback_tool), "skill": self._choice(fallback_skill), "research_method": self._choice(fallback_method), "work_method": self._choice(fallback_work), "model_level": self._choice(fallback_model), "deterministic": self._noul(0.0), "needs_web": self._noul(1.0 if web else 0.0), "complexity": {"value": 0.5, "confidence": 0.2}, "context_policy": self._choice("evidence_chain" if opportunity else "minimal"), "success_criteria": self._choice(fallback_success), "jev_call_policy": self._choice("initial_and_events"), "delegation_policy": self._choice("staged_subtasks"), "second_opinion_trigger": self._choice("evidence_conflict_or_low_confidence"), "thinktank_trigger": self._choice("rare_high_stakes"), "thinktank_shape": self._choice("two_independent_then_critic"), "consensus_rule": self._choice("evidence_gate"), "handoff_context": self._choice("compact_facts"), "human_checkpoint": self._noul(0.9), "max_agents": {"value": 0.5, "confidence": 0.5}}
        elif prefix == "supervise":
            values = {"next_action": self._choice("continue"), "handoff_mode": self._choice("continue_from_luna"), "on_track": self._noul(0.5), "need_more_research": self._noul(0.0), "ready_for_gate": self._noul(0.0)}
        elif prefix == "deliberation":
            trigger = uncertainty >= 0.45 or conflict or high_impact
            values = {
                "use_thinktank": self._noul(1.0 if trigger else 0.0),
                "mode": self._choice("two_independent_then_critic" if trigger else "single_worker"),
                "critic_tier": self._choice("astra" if risk in {"high", "critical"} else "sol"),
                "context_policy": self._choice("compact_facts"),
                "human_checkpoint": self._noul(1.0 if high_impact else 0.0),
            }
        else:
            values = {"ready": self._noul(0.0), "needs_stronger_review": self._noul(1.0), "quality": {"value": 0.25, "confidence": 0.2}}
        return {"answers": values, "model": "policy-fallback", "decision_source": "policy_fallback", "usage": {"input_tokens": 0, "output_tokens": 0}}

    def initial(self, task: str, context_summary: str = "") -> dict[str, Any]:
        state = {
            "task": task,
            "context_summary": context_summary[:5000],
            "constraints": ["Resolve deterministic work before any LLM.", "Luna must attempt every LLM task first, including complex tasks.", "Use progressive disclosure.", "Escalate only when observable evidence supports it."],
            "resources": {"agents": list(AGENTS), "tools": list(TOOLS), "plugins": list(PLUGINS), "skills": list(SKILLS), "context_policies": list(CONTEXT_POLICIES), "success_criteria": list(SUCCESS_CRITERIA), "deliberation_modes": list(DELIBERATION_MODES), "consensus_rules": list(CONSENSUS_RULES)},
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
            "jev_call_policy": Choice(instructions="Choose when JEV should be consulted; prefer the initial plan plus evidence events, not every trivial step.", criteria={"initial_and_events": "Initial route plus new evidence, failed tools/tests, phase changes, budget pressure, escalation, and final gate.", "only_ambiguous": "Only when ambiguity or uncertainty appears.", "only_escalation": "Only before model escalation.", "every_step": "Before every tool and model action."}),
            "delegation_policy": Choice(instructions="Choose how other models may be assigned bounded work while preserving Luna-first.", criteria={"single_worker": "One worker unless evidence requests another view.", "staged_subtasks": "Delegate bounded subtasks to the cheapest suitable workers and synthesize compact facts.", "parallel_independent": "Run independent workers in parallel when state can be separated.", "full_panel": "Run Luna, Sol, and Astra from the beginning."}),
            "second_opinion_trigger": Choice(instructions="Choose when to request one independent second opinion.", criteria={"evidence_conflict_or_low_confidence": "Only after conflicting evidence, low confidence, failed tests, material unresolved assumptions, or stagnation.", "material_impact": "Before material legal, financial, safety, publication, access, or irreversible decisions.", "complexity_only": "Whenever the task is classified complex.", "never_automatically": "Only when the user explicitly asks."}),
            "thinktank_trigger": Choice(instructions="Choose when a small thinktank is justified.", criteria={"rare_high_stakes": "Only for high-impact ambiguity, rival hypotheses, conflicting evidence, repeated failure, or strategic choices.", "two_views_default": "Use two views for every non-trivial task.", "three_vote_high_risk": "Use three role-based views for high-risk disagreement.", "never": "Avoid thinktanks."}),
            "thinktank_shape": Choice(instructions="Choose the most token-efficient thinktank shape when triggered.", criteria={"two_independent_then_critic": "Two compact independent views followed by an evidence gatekeeper.", "sequential_rewrite": "One worker writes and another rewrites.", "three_role_debate": "Advocate, skeptic, and verifier with bounded positions.", "majority_vote": "Select the most common answer."}),
            "consensus_rule": Choice(instructions="Choose how consensus is accepted.", criteria=CONSENSUS_RULES),
            "handoff_context": Choice(instructions="Choose the context passed between workers.", criteria={"compact_facts": "Objective, criteria, observed facts, evidence, uncertainty, decisions, and concrete failures only.", "full_transcript": "Complete transcript.", "summary_only": "Unstructured summary.", "fresh_restart": "Discard prior work."}),
            "human_checkpoint": Noul(instructions="Should a human checkpoint remain before irreversible external actions, publication, rights, money, security, or access changes?"),
            "max_agents": Score(instructions="Rate the normal maximum number of generative workers in one task before stronger evidence or human review is required.", criteria=["1", "2", "3", "4", "5 or more"]),
        }
        return self._run("initial", state, questions)

    def supervise(self, state: dict[str, Any]) -> dict[str, Any]:
        compact = {k: state[k] for k in state if k in {"objective", "phase", "agent", "model_level", "tool", "findings", "problems", "observed_failures", "round", "tokens_used", "candidate_next_actions", "success_criteria"}}
        questions = {
            "next_action": Choice(instructions="Choose the next bounded action. Continue Luna unless observable evidence supports escalation.", criteria={
                "continue": "Continue current plan.",
                "change_tool": "Change tool or application.",
                "change_agent": "Change specialist without increasing model tier.",
                "thinktank": "Request a bounded independent-view thinktank because uncertainty, conflict, or impact justifies it.",
                "escalate_sol": "Escalate to Sol.",
                "escalate_astra": "Escalate to Astra.",
                "request_second_opinion": "Ask one independent low-cost worker for a compact second view because evidence or confidence warrants it.",
                "launch_thinktank": "Launch a bounded two-view thinktank because the decision is high-impact or hypotheses materially conflict.",
            "finish": "The objective is ready for the final gate.",
            }),
            "handoff_mode": Choice(instructions="If escalation becomes justified, choose whether Sol should use a compressed factual Luna handoff or restart from the objective.", criteria={"continue_from_luna": "Reuse only compact verified findings and failures.", "restart_with_sol": "Discard Luna's work and give Sol the objective and acceptance criteria only."}),
            "on_track": Noul(instructions="Is the current work on track to satisfy the original objective efficiently?"),
            "need_more_research": Noul(instructions="Is additional research necessary before completion?"),
            "ready_for_gate": Noul(instructions="Is the work mature enough for a final completion check?"),
        }
        return self._run("supervise", compact, questions)

    def deliberation(self, state: dict[str, Any]) -> dict[str, Any]:
        """Decide whether a bounded consensus panel is worth its token cost."""
        compact = {k: state[k] for k in state if k in {"objective", "task", "risk", "uncertainty", "conflicting_evidence", "observed_conflicts", "acceptance_criteria", "facts", "unresolved"}}
        questions = {
            "use_thinktank": Noul(instructions="Is an independent-view thinktank worth its token and latency cost for this objective?"),
            "mode": Choice(instructions="Choose the smallest useful deliberation mode.", criteria=DELIBERATION_MODES),
            "critic_tier": Choice(instructions="Choose the critic tier; prefer Sol and reserve Astra for high-risk or materially unresolved work.", criteria={"sol": "Use Sol as a compact critic for normal uncertainty.", "astra": "Use Astra only for high-risk or materially unresolved work."}),
            "context_policy": Choice(instructions="Choose the minimum context policy for independent views and critique.", criteria=CONTEXT_POLICIES),
            "human_checkpoint": Noul(instructions="Must a human review the result before an irreversible, legal, financial, publication, access, or security action?"),
        }
        return self._run("deliberation", compact, questions)

    def gate(self, objective: str, result_summary: str, unresolved: list[str] | None = None) -> dict[str, Any]:
        state = {"objective": objective, "result_summary": result_summary[:7000], "unresolved": unresolved or []}
        questions = {
            "ready": Noul(instructions="Does the result satisfy the stated objective sufficiently to deliver, including its acceptance criteria?"),
            "needs_stronger_review": Noul(instructions="Would a stronger model materially improve correctness or completeness based on concrete gaps?"),
            "quality": Score(instructions="Rate completion quality using the evidence supplied.", criteria=["Incomplete", "Weak", "Acceptable", "Strong", "Excellent"]),
        }
        return self._run("gate", state, questions)
