"""Unit tests for deterministic routing helpers and accounting."""
from jev_orchestrator.config import MODEL_IDS, PROJECT_TYPESAFE_SKILL_FILE, TYPESAFE_MODEL, TYPESAFE_SKILL_FILE
from jev_orchestrator.deterministic import compress_context, try_exact_math
from jev_orchestrator.telemetry import Usage


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
    usage = Usage("jev", TYPESAFE_MODEL, 1_000_000, 100)
    assert abs(usage.estimated_cost_usd - 0.042) < 1e-12


def test_luna_cost() -> None:
    usage = Usage("openai", "gpt-5.6-luna", 1_000_000, 1_000_000)
    assert abs(usage.estimated_cost_usd - 1.40) < 1e-12
