"""Compare one batched JEV routing call with equivalent separate calls."""
from __future__ import annotations

import json
from pathlib import Path

from typesafe_sdk import Choice, Noul, Score
from jev_orchestrator.catalog import AGENTS, RESEARCH_METHODS, SKILLS, TOOLS, WORK_METHODS
from jev_orchestrator.config import JEV_INPUT_PRICE_PER_MILLION, TYPESAFE_MODEL, TYPESAFE_TIMEOUT_SECONDS
from jev_orchestrator.connection import create_client
from jev_orchestrator.router import MODEL_CHOICES

client = create_client()
state = {
    "task": "Diagnose a Python asyncio service that intermittently deadlocks under concurrent load.",
    "constraints": ["Minimize tokens and cost.", "Prefer deterministic tools.", "Escalate only when justified."],
    "resources": {"agents": list(AGENTS), "tools": list(TOOLS), "skills": list(SKILLS)},
}
questions = {
    "agent": Choice(instructions="Select the best primary agent.", criteria=AGENTS),
    "tool": Choice(instructions="Select the best first tool or application.", criteria=TOOLS),
    "skill": Choice(instructions="Select the most useful skill.", criteria=SKILLS),
    "research_method": Choice(instructions="Select the best research method.", criteria=RESEARCH_METHODS),
    "work_method": Choice(instructions="Select the best work method.", criteria=WORK_METHODS),
    "model_level": Choice(instructions="Select the minimum model capability.", criteria=MODEL_CHOICES),
    "deterministic": Noul(instructions="Can the core task be solved reliably without a generative model?"),
    "needs_web": Noul(instructions="Does this task require current web information?"),
    "complexity": Score(instructions="Rate reasoning complexity.", criteria=["Trivial", "Routine", "Moderate", "Complex", "Exceptional"]),
}

try:
    batched = client.system_one(state=state, questions=questions, model=TYPESAFE_MODEL, timeout=TYPESAFE_TIMEOUT_SECONDS)
    separate_in = separate_out = 0
    for name, question in questions.items():
        response = client.system_one(state=state, questions={name: question}, model=TYPESAFE_MODEL, timeout=TYPESAFE_TIMEOUT_SECONDS)
        separate_in += response.usage.input_tokens
        separate_out += response.usage.output_tokens
    batched_in = batched.usage.input_tokens
    batched_out = batched.usage.output_tokens
    report = {
        "status": "completed",
        "batched": {"input_tokens": batched_in, "output_tokens": batched_out, "cost_usd": batched_in * JEV_INPUT_PRICE_PER_MILLION / 1_000_000},
        "separate": {"input_tokens": separate_in, "output_tokens": separate_out, "cost_usd": separate_in * JEV_INPUT_PRICE_PER_MILLION / 1_000_000},
        "input_token_reduction_percent": 100.0 * (1.0 - batched_in / separate_in),
        "input_token_ratio": separate_in / batched_in,
    }
except Exception as exc:
    report = {"status": "unavailable", "reason": f"{type(exc).__name__}: {str(exc)[:300]}"}
Path("telemetry/batching-benchmark-latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
