"""Backend-selection tests for subscription-first model execution."""
from __future__ import annotations

import json

from jev_orchestrator import runtime as runtime_module
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


def test_codex_runtime_sends_utf8_prompt_and_decodes_utf8_output(monkeypatch):
    runtime = AgentRuntime(Telemetry("utf8-prompt"), validate_models=False)
    runtime._codex_executable = lambda: ["fake-codex"]
    captured = {}

    class Completed:
        returncode = 0
        stdout = (json.dumps(
            {"item": {"type": "agent_message", "text": "respuesta correcta"}, "usage": {"input_tokens": 3, "output_tokens": 2}},
            ensure_ascii=False,
        ) + "\n").encode("utf-8")
        stderr = b""

    def fake_run(args, **kwargs):
        captured.update(kwargs)
        return Completed()

    monkeypatch.setattr(runtime_module.subprocess, "run", fake_run)
    result = runtime._run_codex("luna_scout", "Responde únicamente con una comprobación.", "")

    assert isinstance(captured["input"], bytes)
    assert captured["input"].decode("utf-8").endswith("Responde únicamente con una comprobación.\n\nKeep the final answer under 180 words unless essential.")
    assert captured["text"] is False
    assert result.output == "respuesta correcta"
