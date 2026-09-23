"""End-to-end opportunity discovery and application workflow.

The module keeps source evidence, drafting, form mapping, supervision, and
submission state in inspectable files.  It deliberately does not invent facts
or silently submit a legally binding declaration.  External submission is an
adapter boundary and is opt-in through ``JEV_ALLOW_EXTERNAL_SUBMISSION=1``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping, Protocol

from .config import ROOT
from .deterministic import compress_context
from .orchestrator import JEVOrchestrator


OPPORTUNITY_SCHEMA = "jev-opportunity/1"
REGIONS = {"eu", "european union", "union europea", "spain", "españa", "castilla-la mancha", "castilla la mancha", "castilla-la mancha, spain"}
KINDS = {"award", "premio", "competition", "concurso", "project_presentation", "presentación", "grant", "subvención", "funding", "convocatoria"}
AI_TERMS = {"ai", "artificial intelligence", "inteligencia artificial", "machine learning", "aprendizaje automático", "deep learning", "generative ai", "ia generativa", "neural", "computer vision", "nlp", "robotics", "robótica", "data science", "ciencia de datos"}
KAGGLE_TERMS = {"kaggle", "kaggle.com"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:80] or "opportunity"


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


@dataclass(frozen=True)
class ProjectProfile:
    """Verified project facts available to the application workflow."""

    project_name: str
    organization: str = ""
    legal_entity: str = ""
    contact_email: str = ""
    website: str = ""
    github_repositories: tuple[str, ...] = ()
    arxiv_papers: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    team: tuple[str, ...] = ()
    prior_projects: tuple[str, ...] = ()
    default_budget_eur: float | None = None
    extra_facts: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProjectProfile":
        def items(name: str) -> tuple[str, ...]:
            raw = value.get(name, ())
            if isinstance(raw, str):
                return (raw,) if raw.strip() else ()
            return tuple(str(item).strip() for item in raw if str(item).strip())

        budget = value.get("default_budget_eur")
        return cls(
            project_name=str(value.get("project_name", value.get("name", ""))).strip(),
            organization=str(value.get("organization", "")).strip(),
            legal_entity=str(value.get("legal_entity", "")).strip(),
            contact_email=str(value.get("contact_email", "")).strip(),
            website=str(value.get("website", "")).strip(),
            github_repositories=items("github_repositories"),
            arxiv_papers=items("arxiv_papers"),
            capabilities=items("capabilities"),
            team=items("team"),
            prior_projects=items("prior_projects"),
            default_budget_eur=float(budget) if budget not in (None, "") else None,
            extra_facts=dict(value.get("extra_facts", {})) if isinstance(value.get("extra_facts", {}), Mapping) else {},
        )

    @classmethod
    def from_path(cls, path: Path) -> "ProjectProfile":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("profile must be a JSON object")
        profile = cls.from_mapping(payload)
        if not profile.project_name:
            raise ValueError("profile.project_name is required")
        return profile

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"github_repositories": list(self.github_repositories), "arxiv_papers": list(self.arxiv_papers), "capabilities": list(self.capabilities), "team": list(self.team), "prior_projects": list(self.prior_projects)}

    def evidence_context(self) -> str:
        return json.dumps({
            "project_name": self.project_name,
            "organization": self.organization,
            "legal_entity": self.legal_entity,
            "contact_email": self.contact_email,
            "website": self.website,
            "github_repositories": list(self.github_repositories),
            "arxiv_papers": list(self.arxiv_papers),
            "capabilities": list(self.capabilities),
            "team": list(self.team),
            "prior_projects": list(self.prior_projects),
            "default_budget_eur": self.default_budget_eur,
            "extra_facts": dict(self.extra_facts),
        }, ensure_ascii=False, indent=2, default=str)


@dataclass
class Opportunity:
    title: str
    organizer: str
    jurisdiction: str
    kind: str
    official_url: str
    deadline: str = ""
    eligibility: str = ""
    description: str = ""
    submission_url: str = ""
    source_urls: list[str] = field(default_factory=list)
    ai_relevance: float = 0.0
    fit_score: float = 0.0
    status: str = "new"
    id: str = ""
    fit_reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    rejected_reason: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Opportunity":
        def text(name: str, default: str = "") -> str:
            return str(value.get(name, default) or "").strip()

        def urls(name: str) -> list[str]:
            raw = value.get(name, [])
            if isinstance(raw, str):
                return [raw] if raw.strip() else []
            return [str(item).strip() for item in raw if str(item).strip()]

        title = text("title")
        url = text("official_url", text("url"))
        identifier = text("id") or hashlib.sha256(f"{title}|{url}".encode("utf-8")).hexdigest()[:16]
        return cls(
            title=title,
            organizer=text("organizer"),
            jurisdiction=text("jurisdiction"),
            kind=text("kind").lower(),
            official_url=url,
            deadline=text("deadline"),
            eligibility=text("eligibility"),
            description=text("description"),
            submission_url=text("submission_url"),
            source_urls=urls("source_urls") or ([url] if url else []),
            ai_relevance=float(value.get("ai_relevance", 0.0) or 0.0),
            fit_score=float(value.get("fit_score", 0.0) or 0.0),
            status=text("status", "new"),
            id=_slug(identifier),
            fit_reasons=[str(item) for item in value.get("fit_reasons", [])],
            missing_fields=[str(item) for item in value.get("missing_fields", [])],
            rejected_reason=text("rejected_reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SubmissionAdapter(Protocol):
    """Adapter for a real portal, mailbox, or authorized submission system."""

    def submit(self, application: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


class OpportunityAgent:
    """JEV-directed opportunity scout, drafter, reviewer, and submission coordinator."""

    def __init__(self, workspace: Path | None = None, orchestrator: JEVOrchestrator | None = None, clock: Callable[[], str] = _now) -> None:
        self.workspace = Path(workspace or ROOT / "opportunity_workspace")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.orchestrator = orchestrator or JEVOrchestrator(run_name="opportunities")

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _read_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _extract_json(output: str) -> Any | None:
        text = output.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        for opening, closing in (("[", "]"), ("{", "}")):
            start, end = text.find(opening), text.rfind(closing)
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    continue
        return None

    @staticmethod
    def _is_kaggle(candidate: Opportunity) -> bool:
        haystack = " ".join((candidate.title, candidate.organizer, candidate.official_url, candidate.submission_url, *candidate.source_urls)).lower()
        return any(term in haystack for term in KAGGLE_TERMS)

    @staticmethod
    def _is_expired(deadline: str) -> bool:
        value = deadline.strip()
        if not value or value.lower() in {"rolling", "ongoing", "open until filled", "continuous"}:
            return False
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value[:10], fmt).date() < datetime.now(timezone.utc).date()
            except ValueError:
                continue
        return False

    @staticmethod
    def _in_scope(candidate: Opportunity) -> bool:
        region = candidate.jurisdiction.lower()
        kind = candidate.kind.lower()
        haystack = " ".join((candidate.title, candidate.description, candidate.eligibility)).lower()
        region_ok = any(item in region for item in REGIONS) or any(item in haystack for item in REGIONS)
        kind_ok = kind in KINDS or any(item in kind for item in KINDS)
        explicit_ai = bool(re.search(r"\b(ai|ia)\b", haystack))
        ai_ok = candidate.ai_relevance >= 0.5 or explicit_ai or any(term in haystack for term in AI_TERMS if term not in {"ai"})
        return region_ok and kind_ok and ai_ok

    def _normalize(self, raw: Mapping[str, Any]) -> tuple[Opportunity | None, str | None]:
        candidate = Opportunity.from_mapping(raw)
        if self._is_kaggle(candidate):
            candidate.rejected_reason = "excluded_kaggle"
            return None, candidate.rejected_reason
        if self._is_expired(candidate.deadline):
            candidate.rejected_reason = "expired_deadline"
            return None, candidate.rejected_reason
        if not candidate.title or not candidate.official_url:
            candidate.rejected_reason = "missing_title_or_official_url"
            return None, candidate.rejected_reason
        if not self._in_scope(candidate):
            candidate.rejected_reason = "outside_eu_spain_castilla_la_mancha_ai_scope"
            return None, candidate.rejected_reason
        if not candidate.source_urls:
            candidate.source_urls = [candidate.official_url]
        candidate.source_urls = list(dict.fromkeys(candidate.source_urls))
        candidate.ai_relevance = max(0.0, min(1.0, candidate.ai_relevance or 0.7))
        candidate.fit_score = max(0.0, min(1.0, candidate.fit_score or candidate.ai_relevance))
        if not candidate.deadline:
            candidate.missing_fields.append("deadline")
        if not candidate.eligibility:
            candidate.missing_fields.append("eligibility")
        if not candidate.submission_url:
            candidate.missing_fields.append("submission_url")
        return candidate, None

    def scan(self, profile: ProjectProfile, extra_context: str = "") -> dict[str, Any]:
        task = """Discover current AI opportunities outside Kaggle: awards, competitions, project-presentation calls, and grants in the European Union, Spain, or Castilla-La Mancha. Use official call pages, bases, annexes, FAQs, and submission portals as primary sources. Use the project's GitHub repositories and arXiv papers only as fit evidence. Return JSON only with an object containing opportunities[], where each item has title, organizer, jurisdiction, kind, official_url, submission_url, deadline, eligibility, description, source_urls, ai_relevance, fit_score, and fit_reasons. Do not include Kaggle or opportunities outside scope."""
        context = compress_context("PROFILE:\n" + profile.evidence_context() + "\n\nCONSTRAINTS:\nExclude Kaggle. Scope: EU, Spain, Castilla-La Mancha. AI only. Current official sources required.\n\nEXTRA CONTEXT:\n" + extra_context, 12000)
        result = self.orchestrator.execute(task, context)
        payload = self._extract_json(result.output)
        raw_items = payload.get("opportunities", []) if isinstance(payload, Mapping) else payload if isinstance(payload, list) else []
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, str]] = []
        for raw in raw_items:
            if not isinstance(raw, Mapping):
                rejected.append({"reason": "item_not_object"})
                continue
            candidate, reason = self._normalize(raw)
            if candidate is None:
                rejected.append({"title": str(raw.get("title", "")), "reason": reason or "rejected"})
            else:
                accepted.append(candidate.to_dict())
        stamp = self.clock().replace(":", "").replace("-", "")
        record = {
            "schema": OPPORTUNITY_SCHEMA,
            "generated_at": self.clock(),
            "profile": profile.to_dict(),
            "provenance": result.route.get("provenance", "local"),
            "decision_source": result.route.get("decision_source", "unknown"),
            "model_path": result.telemetry.get("by_tier", {}),
            "opportunities": accepted,
            "rejected": rejected,
            "raw_output_parseable": payload is not None,
            "telemetry_file": result.telemetry.get("telemetry_file"),
        }
        self._write_json(self.workspace / "scans" / f"{stamp}.json", record)
        self._write_json(self.workspace / "latest_scan.json", record)
        return record

    def prepare(self, profile: ProjectProfile, opportunity: Opportunity | Mapping[str, Any] | Path) -> dict[str, Any]:
        if isinstance(opportunity, Path):
            opportunity = self._read_json(opportunity)
        candidate = opportunity if isinstance(opportunity, Opportunity) else Opportunity.from_mapping(opportunity)
        application_dir = self.workspace / "applications" / candidate.id
        evidence = {"github": list(profile.github_repositories), "arxiv": list(profile.arxiv_papers), "official_opportunity": candidate.official_url, "official_sources": candidate.source_urls}
        task = """Prepare an evidence-backed application package for this opportunity. Return JSON only with executive_summary, technical_approach, novelty, impact, workplan, team, budget_narrative, answers, and unresolved_questions. Every claim must be supported by the supplied GitHub/arXiv or official-call evidence. Use null or an explicit unresolved question instead of inventing a fact."""
        context = compress_context("PROFILE:\n" + profile.evidence_context() + "\n\nOPPORTUNITY:\n" + json.dumps(candidate.to_dict(), ensure_ascii=False) + "\n\nEVIDENCE INDEX:\n" + json.dumps(evidence, ensure_ascii=False), 14000)
        result = self.orchestrator.execute(task, context)
        drafted = self._extract_json(result.output)
        if not isinstance(drafted, Mapping):
            drafted = {"executive_summary": result.output, "unresolved_questions": ["Model output was not structured JSON; human review required."]}
        missing = list(dict.fromkeys(candidate.missing_fields))
        for label, value in (("organization", profile.organization), ("legal_entity", profile.legal_entity), ("contact_email", profile.contact_email), ("github_evidence", profile.github_repositories), ("arxiv_evidence", profile.arxiv_papers)):
            if not value:
                missing.append(label)
        if candidate.kind in {"grant", "subvención", "funding", "convocatoria"} and profile.default_budget_eur is None:
            missing.append("budget")
        missing = list(dict.fromkeys(missing))
        state = {
            "schema": OPPORTUNITY_SCHEMA,
            "application_id": candidate.id,
            "created_at": self.clock(),
            "updated_at": self.clock(),
            "status": "needs_review" if missing else "ready_for_audit",
            "opportunity": candidate.to_dict(),
            "profile": profile.to_dict(),
            "evidence": evidence,
            "draft": dict(drafted),
            "missing_fields": missing,
            "human_attestation_required": ["signature_or_declaration", "final_legal_attestation"],
            "submission": {"status": "not_submitted", "receipt": None},
            "provenance": result.route.get("provenance", "local"),
            "decision_source": result.route.get("decision_source", "unknown"),
        }
        checklist = {
            "official_call_and_bases_saved": bool(candidate.official_url and candidate.source_urls),
            "eligibility_reviewed": bool(candidate.eligibility),
            "github_evidence_cited": bool(profile.github_repositories),
            "arxiv_evidence_cited": bool(profile.arxiv_papers),
            "all_required_attachments": False,
            "budget_verified": profile.default_budget_eur is not None or candidate.kind not in {"grant", "subvención", "funding", "convocatoria"},
            "declarations_signed": False,
            "portal_submission_receipt": False,
        }
        state["checklist"] = checklist
        self._write_json(application_dir / "state.json", state)
        self._write_json(application_dir / "form.json", {"opportunity": candidate.to_dict(), "verified_fields": profile.to_dict(), "missing_fields": missing, "human_attestation_required": state["human_attestation_required"]})
        self._write_json(application_dir / "checklist.json", checklist)
        self._write_json(application_dir / "evidence.json", evidence)
        (application_dir / "narrative.md").write_text(self._render_narrative(candidate, profile, drafted), encoding="utf-8")
        return state | {"application_dir": str(application_dir)}

    @staticmethod
    def _render_narrative(candidate: Opportunity, profile: ProjectProfile, drafted: Mapping[str, Any]) -> str:
        sections = [f"# {profile.project_name} — {candidate.title}", "", f"Official opportunity: {candidate.official_url}", f"Deadline: {candidate.deadline or 'UNRESOLVED'}", "", "## Evidence", *[f"- GitHub: {url}" for url in profile.github_repositories], *[f"- arXiv: {url}" for url in profile.arxiv_papers], ""]
        labels = {"executive_summary": "Executive summary", "technical_approach": "Technical approach", "novelty": "Novelty", "impact": "Impact", "workplan": "Workplan", "team": "Team", "budget_narrative": "Budget narrative", "unresolved_questions": "Unresolved questions"}
        for key, label in labels.items():
            value = drafted.get(key)
            if value is None or value == "":
                continue
            sections.extend([f"## {label}", str(value), ""])
        return "\n".join(sections).rstrip() + "\n"

    def resume(self, application_dir: Path) -> dict[str, Any]:
        state_path = application_dir / "state.json"
        state = self._read_json(state_path)
        supervision = self.orchestrator.router.supervise(state)
        unresolved = list(state.get("missing_fields", [])) + list(state.get("human_attestation_required", []))
        gate = self.orchestrator.router.gate(str(state.get("opportunity", {}).get("title", "")), json.dumps(state.get("draft", {}), ensure_ascii=False), unresolved)
        state["updated_at"] = self.clock()
        state["supervision"] = supervision
        state["gate"] = gate
        state["next_action"] = supervision.get("answers", {}).get("next_action", {}).get("value", "finish")
        self._write_json(state_path, state)
        return state

    def submit(self, application_dir: Path, adapter: SubmissionAdapter | None = None) -> dict[str, Any]:
        state_path = application_dir / "state.json"
        state = self._read_json(state_path)
        missing = list(state.get("missing_fields", []))
        if missing:
            return {"status": "blocked", "reason": "missing_fields", "missing_fields": missing, "application_dir": str(application_dir)}
        if os.environ.get("JEV_ALLOW_EXTERNAL_SUBMISSION", "0") != "1":
            request = {"status": "ready_for_authorized_submission", "created_at": self.clock(), "application_dir": str(application_dir), "reason": "External submission is disabled by default; set JEV_ALLOW_EXTERNAL_SUBMISSION=1 and provide an adapter."}
            self._write_json(application_dir / "submission-request.json", request)
            return request
        if adapter is None:
            return {"status": "blocked", "reason": "submission_adapter_not_configured", "application_dir": str(application_dir)}
        response = dict(adapter.submit(state))
        state["submission"] = response
        state["updated_at"] = self.clock()
        self._write_json(state_path, state)
        self._write_json(application_dir / "submission-result.json", response)
        return response

    def monitor_once(self, profile: ProjectProfile, extra_context: str = "", auto_prepare: bool = False, min_fit_score: float = 0.65) -> dict[str, Any]:
        scan = self.scan(profile, extra_context)
        prepared: list[str] = []
        if auto_prepare:
            for item in scan["opportunities"]:
                if float(item.get("fit_score", 0.0)) >= min_fit_score:
                    state = self.prepare(profile, item)
                    prepared.append(str(state["application_id"]))
        return {"scan": scan, "prepared": prepared, "next_poll_seconds": 86_400}

    def monitor(self, profile: ProjectProfile, interval_seconds: int = 86_400, cycles: int | None = None, auto_prepare: bool = False) -> None:
        count = 0
        while cycles is None or count < cycles:
            self.monitor_once(profile, auto_prepare=auto_prepare)
            count += 1
            if cycles is None or count < cycles:
                time.sleep(max(1, interval_seconds))


def profile_template() -> dict[str, Any]:
    return {
        "project_name": "",
        "organization": "",
        "legal_entity": "",
        "contact_email": "",
        "website": "",
        "github_repositories": [],
        "arxiv_papers": [],
        "capabilities": [],
        "team": [],
        "prior_projects": [],
        "default_budget_eur": None,
        "extra_facts": {},
    }


def create_profile(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"profile already exists: {path}")
    path.write_text(json.dumps(profile_template(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
