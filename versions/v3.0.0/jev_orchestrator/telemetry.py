"""Append-only telemetry and token-cost accounting."""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from typing import Any

from .config import JEV_INPUT_PRICE_PER_MILLION, MODEL_PRICES_PER_MILLION, TELEMETRY_DIR

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
        row = {"ts": time.time(), "kind": kind, "payload": payload}
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
