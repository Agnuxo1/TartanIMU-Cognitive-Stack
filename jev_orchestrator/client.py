"""Dependency-free TypeSafe System One client.

The official HTTP contract is intentionally used directly so every agent can
connect without installing a particular SDK.  Responses and errors remain
structured and UTF-8 safe on Windows.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from http.client import HTTPResponse
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings, api_key_from_env


class JEVConnectionError(RuntimeError):
    """Base error for connection and protocol failures."""


class JEVNotConfigured(JEVConnectionError):
    """Raised when no environment API key is available."""


class JEVHTTPError(JEVConnectionError):
    """Raised when TypeSafe returns an unsuccessful HTTP status."""

    def __init__(self, status: int, message: str, payload: Any = None):
        super().__init__(f"TypeSafe HTTP {status}: {message}")
        self.status = status
        self.payload = payload


@dataclass(frozen=True)
class JEVResponse:
    """Normalized response while preserving the original API payload."""

    model: str
    answers: Mapping[str, Any]
    usage: Mapping[str, Any]
    raw: Mapping[str, Any]
    provenance: str = "jev"

    def as_dict(self) -> dict[str, Any]:
        return {
            "provenance": self.provenance,
            "model": self.model,
            "answers": dict(self.answers),
            "usage": dict(self.usage),
            "raw": dict(self.raw),
        }


def _validate_questions(questions: Mapping[str, Mapping[str, Any]]) -> None:
    if not questions:
        raise ValueError("questions must contain at least one typed question")
    for question_id, question in questions.items():
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError("question ids must be non-empty strings")
        if not isinstance(question, Mapping):
            raise ValueError(f"question {question_id!r} must be an object")
        question_type = question.get("type")
        if question_type not in {"choice", "score", "noul"}:
            raise ValueError(f"question {question_id!r} has unsupported type")
        if "instructions" not in question:
            raise ValueError(f"question {question_id!r} needs instructions")
        criteria = question.get("criteria")
        if question_type == "choice":
            if not isinstance(criteria, Mapping) or not criteria:
                raise ValueError(f"choice {question_id!r} needs a criteria map")
            if len(criteria) > 255:
                raise ValueError(f"choice {question_id!r} has more than 255 options")
        elif question_type == "score":
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
                raise ValueError(f"score {question_id!r} needs 2 to 10 levels")
        elif criteria is not None and not isinstance(criteria, Mapping):
            raise ValueError(f"noul {question_id!r} criteria must be an object")


def _decode_json(data: bytes) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JEVConnectionError("TypeSafe returned invalid UTF-8/JSON") from exc


class TypesafeJevClient:
    """Small stable client usable from Python, subprocesses, or any agent."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        settings: Settings | None = None,
        opener=urlopen,
        sleep=time.sleep,
    ) -> None:
        self.api_key = api_key if api_key is not None else api_key_from_env()
        self.settings = settings or Settings.from_env()
        self._opener = opener
        self._sleep = sleep

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def connection_status(self) -> dict[str, Any]:
        """Return local configuration status without making a billable request."""
        return {
            "connected": False,
            "configured": self.configured,
            "endpoint": self.settings.endpoint,
            "model": self.settings.model,
            "credential_source": "environment:TYPESAFE_API_KEY"
            if self.configured
            else None,
            "provenance": "local",
            "message": "ready for remote probe"
            if self.configured
            else "TYPESAFE_API_KEY is not configured",
        }

    def evaluate(
        self,
        state: Any,
        questions: Mapping[str, Mapping[str, Any]],
    ) -> JEVResponse:
        if not self.configured:
            raise JEVNotConfigured(
                "TYPESAFE_API_KEY is not configured; decision remains local"
            )
        _validate_questions(questions)
        body = {
            "state": state,
            "model": self.settings.model,
            "questions": questions,
        }
        payload = self._post(body)
        answers = payload.get("answers")
        if not isinstance(answers, Mapping):
            raise JEVConnectionError("TypeSafe response has no answers object")
        return JEVResponse(
            model=str(payload.get("model", self.settings.model)),
            answers=answers,
            usage=payload.get("usage") if isinstance(payload.get("usage"), Mapping) else {},
            raw=payload,
        )

    def probe(self) -> JEVResponse:
        """Perform a minimal typed request; this is the explicit remote check."""
        return self.evaluate(
            {"probe": "JEV connectivity", "purpose": "health check"},
            {
                "reachable": {
                    "type": "noul",
                    "instructions": "Is this state explicitly a JEV connectivity probe?",
                    "criteria": {
                        "true": "The state identifies a JEV connectivity probe.",
                        "false": "The state does not identify a JEV connectivity probe.",
                    },
                }
            },
        )

    def _post(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        request = Request(
            self.settings.endpoint,
            data=encoded,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": "jev-orchestrator/1.0",
            },
        )
        attempts = self.settings.max_retries + 1
        for attempt in range(attempts):
            try:
                response: HTTPResponse = self._opener(
                    request, timeout=self.settings.timeout_seconds
                )
                data = response.read()
                payload = _decode_json(data)
                if not isinstance(payload, Mapping):
                    raise JEVConnectionError("TypeSafe response must be a JSON object")
                return payload
            except HTTPError as exc:
                raw = exc.read()
                payload = _decode_json(raw) if raw else None
                if exc.code in {429, 529} and attempt + 1 < attempts:
                    self._sleep(min(2**attempt, 8))
                    continue
                detail = payload.get("message", "request rejected") if isinstance(payload, Mapping) else str(exc.reason)
                raise JEVHTTPError(exc.code, str(detail), payload) from exc
            except URLError as exc:
                if attempt + 1 < attempts:
                    self._sleep(min(2**attempt, 8))
                    continue
                raise JEVConnectionError(f"cannot reach TypeSafe: {exc.reason}") from exc
            except TimeoutError as exc:
                if attempt + 1 < attempts:
                    self._sleep(min(2**attempt, 8))
                    continue
                raise JEVConnectionError("TypeSafe request timed out") from exc
