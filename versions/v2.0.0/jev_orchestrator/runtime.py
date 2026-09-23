"""Model runtime using the ChatGPT subscription through Codex CLI by default."""
from __future__ import annotations

import json
import os
import subprocess
import time
import shutil
from dataclasses import dataclass
from pathlib import Path

from agents import Agent, Runner, WebSearchTool
from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError

from .catalog import AGENT_MODELS
from .config import ALLOW_OPENAI_API, CODEX_TIMEOUT_SECONDS, MODEL_BACKEND, MODEL_IDS, OPENAI_KEY_FILE, ROOT
from .telemetry import Telemetry, Usage

AGENT_INSTRUCTIONS = {
    "luna_scout": "You are Luna Scout. Retrieve or triage efficiently. Be concise and evidence-focused.",
    "luna_coder": "You are Luna Coder. Inspect code carefully, prefer minimal changes, and report concrete findings.",
    "luna_reader": "You are Luna Reader. Extract only information needed for the objective.",
    "luna_opportunity_scout": "You are Luna Opportunity Scout. Find current official AI awards, project presentations, competitions, and grants in the EU, Spain, and Castilla-La Mancha, excluding Kaggle. Return only traceable opportunities with official URLs, dates, eligibility, and source evidence.",
    "luna_application_writer": "You are Luna Application Writer. Draft concise, evidence-backed application answers from verified GitHub and arXiv material. Mark unknowns explicitly and never invent eligibility, metrics, budget, partners, or declarations.",
    "luna_form_filler": "You are Luna Form Filler. Map verified project and organization facts into application fields, preserving exact values, missing-field status, source URLs, and deadline constraints.",
    "luna_editor": "You are Luna Editor. Triage editorial work, production files, and release checklists precisely; never invent rights or platform facts.",
    "luna_metadata": "You are Luna Metadata. Reconcile catalogue records, ISBNs, editions, formats, and platform metadata from evidence.",
    "sol_engineer": "You are Sol Engineer. Solve complex engineering and debugging tasks rigorously.",
    "sol_researcher": "You are Sol Researcher. Compare evidence, resolve conflicts, and synthesize concisely.",
    "sol_scientist": "You are Sol Scientist. Use rigorous scientific reasoning and distinguish evidence from inference.",
    "sol_grants_researcher": "You are Sol Grants Researcher. Analyze official call bases, eligibility, aid intensity, state-aid constraints, budgets, deadlines, and required annexes for AI opportunities; distinguish facts, assumptions, and blockers.",
    "sol_application_reviewer": "You are Sol Application Reviewer. Audit a grant, award, or project-presentation dossier against official requirements and identify every substantive gap before submission.",
    "sol_rights": "You are Sol Rights. Analyse copyright, exclusivity, licences, contracts, ISBN constraints, and distribution risk from evidence.",
    "sol_marketing": "You are Sol Marketing. Build evidence-based author positioning, outreach, discoverability, and sales plans.",
    "astra_architect": "You are Astra Architect. Handle exceptionally difficult end-to-end reasoning.",
    "astra_reviewer": "You are Astra Reviewer. Critically review high-stakes work and identify substantive gaps.",
    "astra_submission_auditor": "You are Astra Submission Auditor. Perform the final high-stakes audit of eligibility, source evidence, forms, attachments, budget, declarations, portal state, and submission receipt. Never fabricate or sign on behalf of a person.",
    "astra_publisher": "You are Astra Publisher. Resolve exceptionally difficult portfolio-level publishing and channel strategy problems.",
}
CODEX_CMD = Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming"))) / "npm" / "codex.cmd"

class ModelBackendUnavailable(RuntimeError):
    """Raised when all configured model backends are temporarily unavailable."""

class ModelAvailabilityError(ModelBackendUnavailable):
    """Raised when a configured model ID cannot be verified before use."""

@dataclass
class AgentResult:
    output: str
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    latency_seconds: float
    backend: str

class AgentRuntime:
    def __init__(self, telemetry: Telemetry, validate_models: bool = True, api_client: object | None = None) -> None:
        self.telemetry = telemetry
        self.model_backend = MODEL_BACKEND
        self.allow_openai_api = ALLOW_OPENAI_API
        self.available_models: set[str] | None = None
        if validate_models and self.allow_openai_api:
            api_key = OPENAI_KEY_FILE.read_text(encoding="utf-8").strip() if OPENAI_KEY_FILE.exists() else ""
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
            self.available_models = self._list_model_ids(api_client)

    def _list_model_ids(self, api_client: object | None = None) -> set[str]:
        try:
            client = api_client or OpenAI()
            models = client.models.list().data
            available = {str(model.id) for model in models}
            self.telemetry.event("model_inventory", {"configured": MODEL_IDS, "available_tiers": {tier: MODEL_IDS[tier] in available for tier in MODEL_IDS}})
            return available
        except Exception as exc:
            self.telemetry.event("model_inventory_failed", {"reason": type(exc).__name__, "detail": str(exc)[:300]})
            raise ModelAvailabilityError("Unable to verify configured OpenAI model IDs before use.") from exc

    def _verified_model(self, agent_name: str) -> str:
        model = MODEL_IDS[AGENT_MODELS[agent_name]]
        if self.allow_openai_api and self.available_models is None:
            self.available_models = self._list_model_ids()
        if self.available_models is not None and model not in self.available_models:
            raise ModelAvailabilityError(f"Configured model ID is not available: {model}")
        return model

    def run(self, agent_name: str, task: str, context: str = "", use_web: bool = False) -> AgentResult:
        if self.model_backend == "openai_api":
            if not self.allow_openai_api:
                raise ModelBackendUnavailable("OpenAI API backend is disabled. Use JEV_ALLOW_OPENAI_API=1 only when API billing is intended.")
            return self._run_api_with_fallback(agent_name, task, context, use_web)
        try:
            result = self._run_codex(agent_name, task, context)
            self.telemetry.event("subscription_model_verified", {"backend": "codex", "agent": agent_name, "model": result.model, "verification": "successful_subscription_execution"})
            return result
        except ModelBackendUnavailable as subscription_error:
            self.telemetry.event("subscription_backend_failed", {"agent": agent_name, "detail": str(subscription_error)[:300], "api_fallback_enabled": self.allow_openai_api})
            if not self.allow_openai_api:
                raise
            return self._run_api_with_fallback(agent_name, task, context, use_web)

    def _run_api_with_fallback(self, agent_name: str, task: str, context: str, use_web: bool) -> AgentResult:
        try:
            return self._run_api(agent_name, task, context, use_web)
        except (RateLimitError, APIConnectionError, APITimeoutError, AuthenticationError, APIError, TimeoutError) as exc:
            self.telemetry.event("api_unavailable", {"reason": self._backend_reason(exc), "detail": str(exc)[:300]})
            raise ModelBackendUnavailable("OpenAI API backend is unavailable and no usable model result was produced.") from exc

    @staticmethod
    def _backend_reason(exc: Exception) -> str:
        status = getattr(exc, "status_code", None)
        if isinstance(exc, RateLimitError) or status == 429:
            return "rate_limit_or_quota"
        if status in {401, 403}:
            return "authentication_or_permission"
        return "api_unavailable"

    def _run_api(self, agent_name: str, task: str, context: str, use_web: bool) -> AgentResult:
        model = self._verified_model(agent_name)
        tools = [WebSearchTool(search_context_size="low")] if use_web else []
        agent = Agent(name=agent_name, instructions=AGENT_INSTRUCTIONS[agent_name] + " Keep the final answer under 180 words unless essential.", model=model, tools=tools)
        prompt = task if not context else f"OBJECTIVE:\n{task}\n\nCOMPACT CONTEXT:\n{context}"
        started = time.perf_counter()
        result = Runner.run_sync(agent, prompt, max_turns=4)
        latency = time.perf_counter() - started
        usage = result.context_wrapper.usage
        cached = int(getattr(usage.input_tokens_details, "cached_tokens", 0) or 0)
        tier = AGENT_MODELS[agent_name]
        self.telemetry.add_usage(Usage("openai", model, int(usage.input_tokens), int(usage.output_tokens), cached_tokens=cached, latency_seconds=latency, tier=tier, backend="api", billing_mode="openai_api"))
        self.telemetry.event("agent_completed", {"backend": "api", "agent": agent_name, "model": model, "use_web": use_web})
        return AgentResult(str(result.final_output), agent_name, model, int(usage.input_tokens), int(usage.output_tokens), cached, latency, "api")

    def _run_codex(self, agent_name: str, task: str, context: str) -> AgentResult:
        codex = self._codex_executable()
        if codex is None:
            raise ModelBackendUnavailable("ChatGPT subscription backend is unavailable because Codex CLI is not installed.")
        model = self._verified_model(agent_name)
        prompt = AGENT_INSTRUCTIONS[agent_name] + "\n\nOBJECTIVE:\n" + task
        if context:
            prompt += "\n\nCOMPACT CONTEXT:\n" + context
        prompt += "\n\nKeep the final answer under 180 words unless essential."
        args = [*codex, "exec", "-m", model, "--json", "--skip-git-repo-check", "--ephemeral", "-"]
        started = time.perf_counter()
        try:
            # Codex CLI reads UTF-8 from stdin. Passing a Python str with
            # text=True lets Windows choose the active code page, which breaks
            # agent tasks containing accents or other non-ASCII characters.
            completed = subprocess.run(
                args,
                input=prompt.encode("utf-8"),
                text=False,
                capture_output=True,
                cwd=ROOT,
                shell=False,
                timeout=CODEX_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            self.telemetry.event("codex_unavailable", {"detail": "Codex CLI timed out", "timeout_seconds": CODEX_TIMEOUT_SECONDS})
            raise ModelBackendUnavailable(f"Codex CLI timed out after {CODEX_TIMEOUT_SECONDS:g} seconds.") from exc
        latency = time.perf_counter() - started
        output = ""
        in_tokens = out_tokens = cached = 0
        failure = ""
        stdout = completed.stdout.decode("utf-8", errors="replace") if isinstance(completed.stdout, bytes) else str(completed.stdout or "")
        stderr = completed.stderr.decode("utf-8", errors="replace") if isinstance(completed.stderr, bytes) else str(completed.stderr or "")
        for raw in stdout.splitlines():
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "turn.failed":
                failure = str(event.get("error", {}).get("message", "Codex turn failed"))
            item = event.get("item", {})
            if item.get("type") in {"agent_message", "message"}:
                output = str(item.get("text") or item.get("content") or output)
            usage = event.get("usage") or event.get("turn", {}).get("usage") or {}
            in_tokens = max(in_tokens, int(usage.get("input_tokens", 0) or 0))
            out_tokens = max(out_tokens, int(usage.get("output_tokens", 0) or 0))
            cached = max(cached, int(usage.get("cached_input_tokens", usage.get("cached_tokens", 0)) or 0))
        if failure or completed.returncode != 0:
            detail = failure or stderr.strip() or "Codex CLI failed."
            self.telemetry.event("codex_unavailable", {"detail": detail[:500]})
            raise ModelBackendUnavailable(detail)
        if not output:
            output = stdout.strip()
        tier = AGENT_MODELS[agent_name]
        self.telemetry.add_usage(Usage("codex", model, in_tokens, out_tokens, cached_tokens=cached, latency_seconds=latency, tier=tier, backend="codex", billing_mode="subscription"))
        self.telemetry.event("agent_completed", {"backend": "codex", "agent": agent_name, "model": model})
        return AgentResult(output, agent_name, model, in_tokens, out_tokens, cached, latency, "codex")

    @staticmethod
    def _codex_executable() -> list[str] | None:
        found = shutil.which("codex")
        if found:
            return [found]
        if CODEX_CMD.exists():
            return ["cmd.exe", "/d", "/s", "/c", str(CODEX_CMD)]
        return None
