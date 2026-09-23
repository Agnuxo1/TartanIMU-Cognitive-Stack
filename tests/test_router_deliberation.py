from __future__ import annotations

from types import SimpleNamespace

from jev_orchestrator.router import JevRouter
from jev_orchestrator.telemetry import Telemetry


class FakeTypesafeClient:
    def __init__(self):
        self.calls = []

    def system_one(self, **kwargs):
        self.calls.append(kwargs)
        answers = {
            "mode": SimpleNamespace(choice="two_independent_then_critic", probabilities={}, confidence=0.9),
            "use_thinktank": SimpleNamespace(noul=1.0),
            "critic_tier": SimpleNamespace(choice="sol", probabilities={}, confidence=0.9),
            "human_checkpoint": SimpleNamespace(noul=0.0),
        }
        return SimpleNamespace(
            answers=answers,
            model="jev-test",
            usage=SimpleNamespace(input_tokens=31, output_tokens=7, cached_input_tokens=0),
        )


def test_deliberation_uses_typed_jev_questions_and_compact_state(tmp_path, monkeypatch):
    import jev_orchestrator.telemetry as telemetry_module

    monkeypatch.setattr(telemetry_module, "TELEMETRY_DIR", tmp_path / "telemetry")
    client = FakeTypesafeClient()
    router = JevRouter(Telemetry("router-test"), use_cache=False, client=client)

    result = router.deliberation({
        "objective": "Compare two plans",
        "risk": "high",
        "uncertainty": 0.8,
        "private_field": "must not be transmitted",
    })

    request = client.calls[0]
    assert result["provenance"] == "jev"
    assert result["answers"]["use_thinktank"]["value"] == 1.0
    assert set(request["questions"]) == {"mode", "use_thinktank", "critic_tier", "human_checkpoint"}
    assert request["state"] == {"objective": "Compare two plans", "risk": "high", "uncertainty": 0.8}
    assert "private_field" not in request["state"]


def test_router_fallback_does_not_persist_provider_exception_text(tmp_path, monkeypatch):
    import jev_orchestrator.telemetry as telemetry_module

    monkeypatch.setattr(telemetry_module, "TELEMETRY_DIR", tmp_path / "telemetry")

    class FailingClient:
        def system_one(self, **kwargs):
            raise RuntimeError("api_key=secret-value person@example.org")

    telemetry = Telemetry("router-error")
    router = JevRouter(telemetry, use_cache=False, client=FailingClient())
    result = router.deliberation({"objective": "Compare plans", "risk": "moderate"})

    assert result["decision_source"] == "policy_fallback"
    serialized = telemetry.path.read_text(encoding="utf-8")
    assert "secret-value" not in serialized
    assert "person@example.org" not in serialized
