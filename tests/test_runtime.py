"""Backend-selection tests for subscription-first model execution."""
from __future__ import annotations

from jev_orchestrator.runtime import AgentResult, AgentRuntime
from jev_orchestrator.telemetry import Telemetry, Usage


def test_runtime_defaults_to_codex_subscription_without_api_inventory_call():
    runtime = AgentRuntime(Telemetry("subscription-policy"), validate_models=True)
    assert runtime.model_backend == "codex_subscription"
    assert runtime.allow_openai_api is False

    def fake_codex(agent_name, task, context):
        return AgentResult("subscription result", agent_name, "gpt-5.6-luna", 4, 2, 1, 0.01, "codex")

    def forbidden_api(*args, **kwargs):
        raise AssertionError("OpenAI API must not be called by the default backend")

    runtime._run_codex = fake_codex
    runtime._run_api = forbidden_api
    result = runtime.run("luna_scout", "Give a short answer")
    assert result.backend == "codex"
    assert result.output == "subscription result"


def test_subscription_usage_has_no_api_cost_estimate():
    usage = Usage("codex", "gpt-5.6-luna", 1_000_000, 1_000_000, backend="codex", billing_mode="subscription")
    assert usage.estimated_cost_usd == 0.0
