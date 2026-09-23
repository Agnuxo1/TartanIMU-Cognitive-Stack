from __future__ import annotations

import json

import jev_orchestrator.telemetry as telemetry_module
from jev_orchestrator.telemetry import Telemetry


def test_telemetry_omits_prompt_content_and_redacts_secrets(monkeypatch, tmp_path):
    monkeypatch.setattr(telemetry_module, "TELEMETRY_DIR", tmp_path)
    telemetry = Telemetry("privacy-test")
    provider_token = "sk-" + "12345678901234567890"
    telemetry.event(
        "example",
        {
            "objective": "private project objective",
            "api_key": "do-not-write-this",
            "note": f"Bearer super-secret-token and {provider_token}",
            "contact": "person@example.org",
            "tokens_used": 42,
        },
    )

    stored = json.loads(telemetry.path.read_text(encoding="utf-8"))
    payload = stored["payload"]
    serialized = json.dumps(stored)

    assert payload["objective"] == {"omitted": True, "characters": 25}
    assert payload["api_key"] == "[REDACTED]"
    assert "do-not-write-this" not in serialized
    assert "super-secret-token" not in serialized
    assert provider_token not in serialized
    assert payload["contact"] == "[EMAIL]"
    assert payload["tokens_used"] == 42
