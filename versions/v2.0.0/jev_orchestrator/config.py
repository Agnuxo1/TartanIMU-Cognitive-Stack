"""Central configuration for models, pricing, paths, and budgets."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS_DIR = ROOT / "secrets"
CACHE_DIR = ROOT / "cache"
TELEMETRY_DIR = ROOT / "telemetry"
OPENAI_KEY_FILE = SECRETS_DIR / "openai_api_key.txt"
TYPESAFE_KEY_FILE = SECRETS_DIR / "typesafe_api_key.txt"
PROJECT_TYPESAFE_SKILL_FILE = ROOT / "skills" / "typesafe-ai" / "SKILL.md"
EXTERNAL_TYPESAFE_SKILL_FILE = Path(os.environ["JEV_TYPESAFE_SKILL_FILE"]) if os.environ.get("JEV_TYPESAFE_SKILL_FILE") else None
TYPESAFE_SKILL_FILE = next(
    (path for path in (PROJECT_TYPESAFE_SKILL_FILE, EXTERNAL_TYPESAFE_SKILL_FILE) if path is not None and path.is_file()),
    PROJECT_TYPESAFE_SKILL_FILE,
)
POLICY_VERSION = "2026-09-22-luna-first-event-consensus-v5"
TYPESAFE_MODEL = os.environ.get("TYPESAFE_MODEL", "jev-latest")
TYPESAFE_TIMEOUT_SECONDS = float(os.environ.get("JEV_TYPESAFE_TIMEOUT_SECONDS", "30"))
CODEX_TIMEOUT_SECONDS = float(os.environ.get("JEV_CODEX_TIMEOUT_SECONDS", "30"))
MODEL_BACKEND = os.environ.get("JEV_MODEL_BACKEND", "codex_subscription")
ALLOW_OPENAI_API = os.environ.get("JEV_ALLOW_OPENAI_API", "0") == "1"

MODEL_IDS = {
    "luna": "gpt-5.6-luna",
    "sol": "gpt-5.6-sol",
    "astra": "gpt-6-astra",
}
MODEL_PRICES_PER_MILLION = {
    "gpt-5.6-luna": {"input": 0.20, "output": 1.20},
    "gpt-5.6-sol": {"input": 4.00, "output": 20.00},
    "gpt-6-astra": {"input": 10.00, "output": 50.00},
}
JEV_INPUT_PRICE_PER_MILLION = 0.042

@dataclass(frozen=True)
class Budget:
    max_total_tokens: int = 50_000
    max_agent_calls: int = 6
    max_checkpoints: int = 6
    heartbeat_seconds: int = 60
    max_handoff_chars: int = 8_000
    max_luna_rounds: int = 3
    max_sol_calls: int = 1
    max_astra_calls: int = 1
    max_thinktank_views: int = 2
    max_thinktank_critics: int = 1
    thinktank_uncertainty_threshold: float = 0.45
    escalation_on_low_confidence: float = 0.45
    gate_ready_threshold: float = 0.70
    gate_quality_threshold: float = 0.55

DEFAULT_BUDGET = Budget()
