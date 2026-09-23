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
POLICY_VERSION = "2026-09-22-luna-first-subscription-opportunities-v5"
TYPESAFE_MODEL = "jev-1.13.0"
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


def api_key_from_env() -> str | None:
    """Read the explicit process credential without reading or printing secrets."""
    value = os.environ.get("TYPESAFE_API_KEY", "").strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    """Compatibility settings for the dependency-free TypeSafe HTTP client."""

    endpoint: str = "https://api.typesafe.ai/v1/systemone"
    model: str = TYPESAFE_MODEL
    timeout_seconds: float = TYPESAFE_TIMEOUT_SECONDS
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "Settings":
        endpoint = os.environ.get("TYPESAFE_ENDPOINT", cls.endpoint).strip() or cls.endpoint
        model = os.environ.get("TYPESAFE_DEFAULT_MODEL", os.environ.get("TYPESAFE_MODEL", cls.model)).strip() or cls.model
        timeout = float(os.environ.get("TYPESAFE_TIMEOUT_SECONDS", str(cls.timeout_seconds)))
        retries = int(os.environ.get("TYPESAFE_MAX_RETRIES", str(cls.max_retries)))
        return cls(endpoint=endpoint, model=model, timeout_seconds=timeout, max_retries=max(0, retries))

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
    escalation_on_low_confidence: float = 0.45
    gate_ready_threshold: float = 0.70
    gate_quality_threshold: float = 0.55

DEFAULT_BUDGET = Budget()
