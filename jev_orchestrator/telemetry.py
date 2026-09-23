"""Append-only telemetry and token-cost accounting."""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from typing import Any

from .config import JEV_INPUT_PRICE_PER_MILLION, MODEL_PRICES_PER_MILLION, TELEMETRY_DIR

_SECRET_KEYS = {"api_key", "typesafe_api_key", "openai_api_key", "authorization", "password", "secret", "credential", "credentials", "access_token", "refresh_token"}
_PRIVATE_CONTENT_KEYS = {"objective", "task", "context", "context_summary", "result", "result_summary", "output", "findings", "facts", "prompt", "stderr", "stdout", "detail", "error_message"}
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|ts_[A-Za-z0-9_-]{16,})\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*[^\s,;]+"),
)


def _sanitize(value: Any, key: str = "") -> Any:
    normalized_key = key.lower().replace("-", "_")
    if normalized_key in _SECRET_KEYS or normalized_key.endswith("_api_key") or normalized_key.endswith("_secret"):
        return "[REDACTED]"
    if normalized_key in _PRIVATE_CONTENT_KEYS:
        if isinstance(value, str):
            return {"omitted": True, "characters": len(value)}
        if isinstance(value, (list, tuple)):
            return {"omitted": True, "items": len(value)}
        if isinstance(value, dict):
            return {"omitted": True, "fields": len(value)}
    if isinstance(value, dict):
        return {str(child_key): _sanitize(child_value, str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        cleaned = value
        for pattern in _SECRET_PATTERNS:
            cleaned = pattern.sub("[REDACTED]", cleaned)
        cleaned = re.sub(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[EMAIL]", cleaned)
        cleaned = re.sub(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+", "[LOCAL_USER_PATH]", cleaned)
        if normalized_key in {"path", "cache_path", "events_file", "telemetry_file"}:
            return "[LOCAL_PATH]"
        return cleaned
    return value

@dataclass
class Usage:
    source: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    latency_seconds: float = 0.0
    tier: str | None = None
    backend: str | None = None
    billing_mode: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        if self.billing_mode == "subscription" or self.backend == "codex" or self.source == "codex":
            return 0.0
        if self.source == "jev":
            return self.input_tokens * JEV_INPUT_PRICE_PER_MILLION / 1_000_000
        price = MODEL_PRICES_PER_MILLION.get(self.model)
        if not price:
            return 0.0
        billable_input = max(0, self.input_tokens - self.cached_tokens)
        cached_price = price["input"] * 0.1
        return (billable_input * price["input"] + self.cached_tokens * cached_price + self.output_tokens * price["output"]) / 1_000_000

class Telemetry:
    def __init__(self, run_name: str) -> None:
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_name).strip("-") or "run"
        self.path = TELEMETRY_DIR / f"{stamp}-{os.getpid()}-{time.time_ns() % 1_000_000_000:09d}-{safe_name}.jsonl"
        self.usage: list[Usage] = []

    def event(self, kind: str, payload: dict[str, Any]) -> None:
        row = {"ts": time.time(), "kind": kind, "payload": _sanitize(payload)}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def add_usage(self, usage: Usage) -> None:
        self.usage.append(usage)
        payload = asdict(usage) | {"total_tokens": usage.total_tokens, "estimated_cost_usd": usage.estimated_cost_usd}
        self.event("usage", payload)

    def summary(self) -> dict[str, Any]:
        sources = sorted({u.source for u in self.usage})
        tiers = sorted({u.tier or u.source for u in self.usage})
        by_tier: dict[str, dict[str, float | int]] = {}
        for tier in tiers:
            rows = [u for u in self.usage if (u.tier or u.source) == tier]
            by_tier[tier] = {
                "input_tokens": sum(u.input_tokens for u in rows),
                "output_tokens": sum(u.output_tokens for u in rows),
                "cached_tokens": sum(u.cached_tokens for u in rows),
                "total_tokens": sum(u.total_tokens for u in rows),
                "estimated_cost_usd": sum(u.estimated_cost_usd for u in rows),
                "latency_seconds": sum(u.latency_seconds for u in rows),
            }
        return {
            "input_tokens": sum(u.input_tokens for u in self.usage),
            "output_tokens": sum(u.output_tokens for u in self.usage),
            "total_tokens": sum(u.total_tokens for u in self.usage),
            "estimated_cost_usd": sum(u.estimated_cost_usd for u in self.usage),
            "by_source": {source: sum(u.total_tokens for u in self.usage if u.source == source) for source in sources},
            "by_tier": by_tier,
            "events_file": str(self.path),
            "telemetry_file": str(self.path),
        }
