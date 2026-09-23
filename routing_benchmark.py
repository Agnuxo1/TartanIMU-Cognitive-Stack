"""Real TypeSafe/Jev routing benchmark with token telemetry."""
from __future__ import annotations

import json
from pathlib import Path

from jev_orchestrator.router import JevRouter
from jev_orchestrator.telemetry import Telemetry

TASKS = {
    "exact_math": "Calculate exactly 123456789 * 98765 and return only the integer.",
    "current_web": "Find the current stable Python release and its release date using an official source.",
    "code_debug": "Diagnose a Python service that intermittently deadlocks after adding concurrent asyncio tasks. Identify the smallest safe investigation path.",
    "scientific_research": "Find recent peer-reviewed evidence on thermodynamic reservoir computing and identify the most relevant papers for a technical literature review.",
    "hard_architecture": "Design a novel GPU-native neuromorphic architecture without transformers or CNNs, with measurable latency, memory, training, validation, and deployment criteria.",
}

telemetry = Telemetry("routing-benchmark")
router = JevRouter(telemetry, use_cache=False)
results = {}
for name, task in TASKS.items():
    decision = router.initial(task)
    answers = decision["answers"]
    results[name] = {
        "agent": answers["agent"],
        "tool": answers["tool"],
        "skill": answers["skill"],
        "research_method": answers["research_method"],
        "work_method": answers["work_method"],
        "model_level": answers["model_level"],
        "deterministic": answers["deterministic"],
        "needs_web": answers["needs_web"],
        "complexity": answers["complexity"],
        "usage": decision["usage"],
    }

checkpoint = router.supervise({
    "objective": TASKS["code_debug"],
    "phase": "post_initial_inspection",
    "agent": "luna_coder",
    "tool": "desktop_commander",
    "findings": ["Basic syntax and unit tests pass", "Deadlock reproduces only under concurrent load"],
    "problems": ["Root cause not isolated"],
    "tokens_used": telemetry.summary()["total_tokens"],
    "candidate_next_actions": ["continue", "change_tool", "change_agent", "escalate_sol", "escalate_astra", "finish"],
})
results["supervisor_checkpoint"] = {"answers": checkpoint["answers"], "usage": checkpoint["usage"]}
summary = telemetry.summary()
report = {"results": results, "summary": summary}
out = Path("telemetry") / "routing-benchmark-latest.json"
out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(report, indent=2, ensure_ascii=False))
