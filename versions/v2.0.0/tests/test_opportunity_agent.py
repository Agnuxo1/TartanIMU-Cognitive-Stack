from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from jev_orchestrator.opportunity_agent import OpportunityAgent, Opportunity, ProjectProfile


class FakeRouter:
    def supervise(self, state):
        return {"provenance": "local", "answers": {"next_action": {"value": "finish"}}}

    def gate(self, objective, result_summary, unresolved=None):
        return {"provenance": "local", "answers": {"ready": {"value": 1.0}, "quality": {"value": 1.0}}}


class FakeOrchestrator:
    def __init__(self, output):
        self.output = output
        self.router = FakeRouter()

    def execute(self, task, context):
        return SimpleNamespace(
            output=self.output,
            route={"provenance": "local", "decision_source": "policy_fallback"},
            telemetry={"by_tier": {}, "telemetry_file": "fake.jsonl"},
        )


def profile() -> ProjectProfile:
    return ProjectProfile(
        project_name="JEV AI",
        organization="JEV Labs",
        legal_entity="JEV Labs SL",
        contact_email="team@example.invalid",
        github_repositories=("https://github.com/example/jev-ai",),
        arxiv_papers=("https://arxiv.org/abs/2501.00001",),
        capabilities=("machine learning",),
        default_budget_eur=25_000,
    )


def test_scan_excludes_kaggle_and_out_of_scope_items(tmp_path: Path):
    output = json.dumps({
        "opportunities": [
            {
                "title": "EU AI Impact Award",
                "organizer": "European Commission",
                "jurisdiction": "European Union",
                "kind": "award",
                "official_url": "https://commission.europa.eu/ai-award",
                "deadline": "2030-01-01",
                "eligibility": "EU projects using artificial intelligence",
                "ai_relevance": 0.95,
            },
            {
                "title": "Kaggle AI Prize",
                "organizer": "Kaggle",
                "jurisdiction": "Spain",
                "kind": "competition",
                "official_url": "https://kaggle.com/competitions/x",
                "ai_relevance": 1.0,
            },
            {
                "title": "Unrelated science grant",
                "organizer": "Other",
                "jurisdiction": "France",
                "kind": "grant",
                "official_url": "https://example.invalid/grant",
                "eligibility": "science",
            },
        ]
    })
    agent = OpportunityAgent(tmp_path, FakeOrchestrator(output), clock=lambda: "2030-01-01T00:00:00Z")
    result = agent.scan(profile())
    assert [item["title"] for item in result["opportunities"]] == ["EU AI Impact Award"]
    assert {item["reason"] for item in result["rejected"]} == {"excluded_kaggle", "outside_eu_spain_castilla_la_mancha_ai_scope"}
    assert (tmp_path / "latest_scan.json").exists()


def test_prepare_persists_evidence_forms_and_human_attestation_gate(tmp_path: Path, monkeypatch):
    drafted = json.dumps({
        "executive_summary": "A verified AI project.",
        "technical_approach": "Repository-backed approach.",
        "impact": "Impact supported by the cited sources.",
        "unresolved_questions": [],
    })
    agent = OpportunityAgent(tmp_path, FakeOrchestrator(drafted), clock=lambda: "2030-01-01T00:00:00Z")
    candidate = Opportunity(
        title="Castilla-La Mancha AI Grant",
        organizer="Junta de Comunidades de Castilla-La Mancha",
        jurisdiction="Castilla-La Mancha",
        kind="grant",
        official_url="https://docm.castillalamancha.es/ai-grant",
        submission_url="https://sede.jccm.es/ai-grant",
        deadline="2030-02-01",
        eligibility="AI projects by eligible entities in Castilla-La Mancha",
        description="Inteligencia artificial aplicada.",
        source_urls=["https://docm.castillalamancha.es/ai-grant"],
        id="clm-ai-grant",
    )
    state = agent.prepare(profile(), candidate)
    application_dir = Path(state["application_dir"])
    assert state["status"] == "ready_for_audit"
    assert state["evidence"]["github"] == list(profile().github_repositories)
    assert "signature_or_declaration" in state["human_attestation_required"]
    assert (application_dir / "narrative.md").exists()
    assert json.loads((application_dir / "form.json").read_text(encoding="utf-8"))["verified_fields"]["project_name"] == "JEV AI"
    monkeypatch.delenv("JEV_ALLOW_EXTERNAL_SUBMISSION", raising=False)
    submission = agent.submit(application_dir)
    assert submission["status"] == "ready_for_authorized_submission"
    assert (application_dir / "submission-request.json").exists()


def test_prepare_marks_missing_budget_and_profile_facts(tmp_path: Path):
    agent = OpportunityAgent(tmp_path, FakeOrchestrator("not-json"), clock=lambda: "2030-01-01T00:00:00Z")
    candidate = {
        "title": "Spain AI Funding",
        "organizer": "Official Spanish body",
        "jurisdiction": "Spain",
        "kind": "grant",
        "official_url": "https://example.invalid/spain-ai",
        "deadline": "2030-03-01",
        "eligibility": "AI entities",
        "submission_url": "https://example.invalid/submit",
        "description": "Inteligencia artificial.",
    }
    incomplete = ProjectProfile(project_name="Only project")
    state = agent.prepare(incomplete, candidate)
    assert state["status"] == "needs_review"
    assert {"organization", "legal_entity", "contact_email", "github_evidence", "arxiv_evidence", "budget"} <= set(state["missing_fields"])
