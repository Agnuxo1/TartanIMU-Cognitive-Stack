"""Unit tests for deterministic routing helpers and accounting."""

from jev_orchestrator.config import MODEL_IDS, PROJECT_TYPESAFE_SKILL_FILE, TYPESAFE_SKILL_FILE
from jev_orchestrator.connection import create_jev_client, resolve_jev_keys
from jev_orchestrator.deterministic import compress_context, try_exact_math
from jev_orchestrator.telemetry import Usage


def _isolate_jev_credentials(monkeypatch) -> None:
    for name in (
        "TYPESAFE_API_KEY", "TYPESAFE_API_KEY_1", "TYPESAFE_API_KEY_2", "TYPESAFE_API_KEY_3",
        "TYPESAFE_API_KEY_PROFILE_A", "TYPESAFE_API_KEY_PROFILE_B", "TYPESAFE_API_KEY_PROFILE_C",
        "JEV_TYPESAFE_KEY_FILE", "JEV_ALLOW_LEGACY_SECRET_FILE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_exact_math_requires_operator() -> None:
    assert try_exact_math("Answer in under 80 words") is None
    assert try_exact_math("Calculate 123 * 456") == "56088"


def test_context_compression_bound() -> None:
    text = "x" * 20_000
    result = compress_context(text, 1_000)
    assert len(result) < 1_100
    assert "deterministically truncated" in result


def test_model_ids() -> None:
    assert MODEL_IDS == {"luna": "gpt-5.6-luna", "sol": "gpt-5.6-sol", "astra": "gpt-6-astra"}


def test_project_typesafe_skill_is_selected() -> None:
    assert PROJECT_TYPESAFE_SKILL_FILE.exists()
    assert TYPESAFE_SKILL_FILE == PROJECT_TYPESAFE_SKILL_FILE


def test_jev_cost() -> None:
    usage = Usage("jev", "jev-1.13.0", 1_000_000, 100)
    assert abs(usage.estimated_cost_usd - 0.042) < 1e-12


def test_luna_cost() -> None:
    usage = Usage("openai", "gpt-5.6-luna", 1_000_000, 1_000_000)
    assert abs(usage.estimated_cost_usd - 1.40) < 1e-12


def test_shared_jev_connector_uses_process_configuration_without_mutating_it(monkeypatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only-key")
    client = create_jev_client()
    keys = resolve_jev_keys()
    assert keys[0] == "test-only-key"
    assert client.credential_count >= 1
    client.close()


def test_shared_jev_connector_does_not_read_project_secret_files(monkeypatch) -> None:
    _isolate_jev_credentials(monkeypatch)
    import jev_orchestrator.connection as connection

    monkeypatch.setattr(connection, "resolve_profile_credential", lambda **kwargs: None)
    assert resolve_jev_keys() == ()


def test_router_marks_missing_remote_connection_as_local(monkeypatch) -> None:
    _isolate_jev_credentials(monkeypatch)
    from jev_orchestrator.router import JevRouter
    from jev_orchestrator.telemetry import Telemetry
    import jev_orchestrator.connection as connection

    monkeypatch.setattr(connection, "resolve_profile_credential", lambda **kwargs: None)

    result = JevRouter(Telemetry("test-local-provenance"), use_cache=False).initial("Classify a local task")
    assert result["provenance"] == "local"
    assert result["decision_source"] == "policy_fallback"


def test_router_fallback_selects_opportunity_scout_for_grants(monkeypatch) -> None:
    _isolate_jev_credentials(monkeypatch)
    from jev_orchestrator.router import JevRouter
    from jev_orchestrator.telemetry import Telemetry
    import jev_orchestrator.connection as connection

    monkeypatch.setattr(connection, "resolve_profile_credential", lambda **kwargs: None)

    result = JevRouter(Telemetry("test-opportunity-route"), use_cache=False).initial("Buscar subvenciones de inteligencia artificial en Castilla-La Mancha")
    assert result["answers"]["agent"]["value"] == "luna_opportunity_scout"
    assert result["answers"]["skill"]["value"] == "opportunity_discovery"
    assert result["provenance"] == "local"
