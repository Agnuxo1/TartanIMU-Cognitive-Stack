"""Stable, provider-facing connection helpers for any JEV-enabled agent.

This module keeps credential discovery in one place. The key is passed directly
to the SDK and is never returned by the CLI or written to telemetry.
"""
from __future__ import annotations

import importlib.metadata
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from .config import ROOT, TYPESAFE_KEY_FILE, TYPESAFE_MODEL, TYPESAFE_TIMEOUT_SECONDS
from .credentials import Credential, known_profiles, normalize_profile, profile_account, resolve_credential as resolve_profile_credential


KEY_RE = re.compile(r"\b(apikey_[A-Za-z0-9_]+)")
CONNECTIVITY_OBJECTIVE = "Bounded JEV typed-decision connectivity health check"


class JEVConnectionError(RuntimeError):
    """Raised when a usable TypeSafe JEV connection cannot be created."""


def _unique_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def credential_candidates(root: Path | None = None) -> list[Path]:
    """Return explicit, bounded credential locations in precedence order."""
    configured_root = os.environ.get("JEV_ORCHESTRATOR_ROOT", "").strip()
    candidates: list[Path] = []
    if root is None and configured_root:
        candidates.extend(
            [
                Path(configured_root) / "secrets" / "typesafe_api_keys.txt",
                Path(configured_root) / "secrets" / "typesafe_api_key.txt",
            ]
        )
    explicit_key_file = os.environ.get("JEV_TYPESAFE_KEY_FILE", "").strip()
    if explicit_key_file:
        candidates.insert(0, Path(explicit_key_file))
    active_root = root or ROOT
    candidates.append(active_root / "secrets" / "typesafe_api_keys.txt")
    candidates.append(active_root / "secrets" / "typesafe_api_key.txt")
    if root is None and TYPESAFE_KEY_FILE != active_root / "secrets" / "typesafe_api_key.txt":
        candidates.append(TYPESAFE_KEY_FILE)
    return _unique_paths(candidates)


def _values_from_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return []
    if path.name.lower().startswith("utilidades_"):
        marker = re.search(r"TypeSafe\s+AI\s+JEV", text, flags=re.IGNORECASE)
        if not marker:
            return []
        block = text[marker.end() :]
        boundary = re.search(
            r"(?:^|\n)\s*(?:Nuevo\s+Github\s+Token|OpenAI\s+API|Anthropic|Google\s+AI)\b",
            block,
            flags=re.IGNORECASE,
        )
        if boundary:
            block = block[: boundary.start()]
        return KEY_RE.findall(block)
    lines = text.splitlines()
    if path.name.casefold() == "utilidades_herramientas_apis.txt":
        marker = next(
            (index for index, line in enumerate(lines) if re.search(r"typesafe\s+ai\s+jev", line, re.IGNORECASE)),
            None,
        )
        if marker is None:
            return []
        lines = lines[marker + 1 :]
        boundary = re.compile(r"^(?:nuevo\s+github\s+token|openai\s+api|anthropic|google\s+ai)\b", re.IGNORECASE)
        values: list[str] = []
        for line in lines:
            value = line.strip()
            if boundary.search(value):
                break
            if re.fullmatch(r"apikey_[A-Za-z0-9_]+", value):
                values.append(value)
        return values
    values = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    return values or ([text.strip()] if text.strip() else [])


def resolve_credential(root: Path | None = None, profile: str | None = None) -> Credential | None:
    """Resolve one profile from environment, Windows vault, or local recovery."""
    credentials = resolve_credentials(root, profile)
    return credentials[0] if credentials else None


def resolve_credentials(root: Path | None = None, profile: str | None = None) -> list[Credential]:
    """Resolve unique credentials, mapping multi-key files to known profiles."""
    environment_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if environment_key:
        canonical = normalize_profile(profile)
        return [Credential(environment_key, "environment:TYPESAFE_API_KEY", canonical, profile_account(canonical))]

    # A normal agent run uses the selected/default profile. Multi-key file
    # enumeration is retained only for explicit hermetic recovery roots.
    requested = normalize_profile(profile) if (profile or root is None) else None
    profile_names = list(known_profiles())
    selected_names = [requested] if requested else profile_names
    credentials: list[Credential] = []
    seen_values: set[str] = set()

    # Profile-specific environment variables and Windows Credential Manager.
    # An explicit root makes resolution hermetic for embedding agents and
    # tests; never leak credentials from the current Windows user into it.
    if root is None:
        for profile_name in selected_names:
            vault_credential = resolve_profile_credential(profile=profile_name, legacy_candidates=[])
            if vault_credential is not None and vault_credential.value not in seen_values:
                credentials.append(vault_credential)
                seen_values.add(vault_credential.value)

    # A profile-specific vault entry is authoritative. Do not append an old
    # single-key recovery file that could belong to a different account.
    if requested and credentials:
        return credentials
    if not requested and len(credentials) >= len(selected_names):
        return credentials

    # Legacy and recovery files remain supported, including the portable
    # multi-key file generated by sync_jev_credentials.py, but only when an
    # agent explicitly opts into plaintext recovery.
    if os.environ.get("JEV_ALLOW_LEGACY_SECRET_FILE", "0") != "1" and not os.environ.get("JEV_TYPESAFE_KEY_FILE", "").strip():
        return credentials
    for path in credential_candidates(root):
        if not path.exists():
            continue
        values = _values_from_file(path)
        if requested:
            index = profile_names.index(requested) if requested in profile_names else 0
            values = values[index : index + 1] if len(values) > index else values[:1]
        for index, value in enumerate(values):
            if not value or value in seen_values:
                continue
            profile_name = requested or (profile_names[index] if index < len(profile_names) else normalize_profile())
            credentials.append(Credential(value, f"file:{path}", profile_name, profile_account(profile_name)))
            seen_values.add(value)
    return credentials


def create_client(
    *,
    root: Path | None = None,
    profile: str | None = None,
    model: str = TYPESAFE_MODEL,
    timeout: float = TYPESAFE_TIMEOUT_SECONDS,
    credential: Credential | None = None,
) -> TypeSafeClient:
    """Create a real TypeSafe client without relying on ambient environment state."""
    credential = credential or resolve_credential(root, profile)
    if credential is None:
        raise JEVConnectionError(
            "TypeSafe API key not found for the selected profile. Set TYPESAFE_API_KEY, "
            "store a Windows Credential Manager profile, or set JEV_TYPESAFE_KEY_FILE for recovery."
        )
    try:
        return TypeSafeClient(api_key=credential.value, model=model, timeout=timeout)
    except Exception as exc:  # SDK errors must not expose credential material.
        raise JEVConnectionError(f"TypeSafe client initialization failed: {type(exc).__name__}") from exc


def _answer_payload(answer: Any) -> dict[str, Any]:
    if hasattr(answer, "choice"):
        return {
            "value": answer.choice,
            "probabilities": dict(answer.probabilities),
            "confidence": getattr(answer, "confidence", None),
        }
    if hasattr(answer, "noul"):
        return {"value": float(answer.noul)}
    return {"value": float(answer.score), "confidence": getattr(answer, "confidence", None)}


def response_payload(response: Any) -> dict[str, Any]:
    """Convert a TypeSafe response into JSON-safe data for agents and audit logs."""
    usage = getattr(response, "usage", None)
    return {
        "status": "connected",
        "provider": "TypeSafe JEV",
        "model": str(getattr(response, "model", TYPESAFE_MODEL)),
        "answers": {name: _answer_payload(answer) for name, answer in response.answers.items()},
        "usage": {
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "cached_tokens": int(
                getattr(usage, "cached_input_tokens", getattr(usage, "cached_tokens", 0)) or 0
            ),
        },
    }


def system_one(
    state: Mapping[str, Any],
    questions: Mapping[str, Any],
    *,
    client: TypeSafeClient | None = None,
    root: Path | None = None,
    profile: str | None = None,
    model: str = TYPESAFE_MODEL,
    timeout: float = TYPESAFE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Execute one bounded System One request and return a stable JSON contract."""
    if client is not None:
        response = client.system_one(state=dict(state), questions=questions, model=model, timeout=timeout)
        return response_payload(response)

    credentials = resolve_credentials(root, profile)
    if not credentials:
        raise JEVConnectionError(
            "TypeSafe API key not found for the selected profile. Set TYPESAFE_API_KEY, "
            "use Windows Credential Manager, or set JEV_TYPESAFE_KEY_FILE for recovery."
        )
    last_error: Exception | None = None
    for index, credential in enumerate(credentials):
        try:
            active_client = create_client(model=model, timeout=timeout, credential=credential, profile=profile)
            response = active_client.system_one(state=dict(state), questions=questions, model=model, timeout=timeout)
            return response_payload(response)
        except Exception as exc:
            last_error = exc
            if index + 1 >= len(credentials) or not _is_auth_failure(exc):
                break
    raise JEVConnectionError(f"TypeSafe request failed: {type(last_error).__name__ if last_error else 'unknown_error'}") from last_error


class JevClient:
    """Typed SDK facade used by the router, backed by the shared credential resolver."""

    def __init__(self, keys: tuple[str, ...] | None = None, *, timeout: float = TYPESAFE_TIMEOUT_SECONDS, profile: str | None = None) -> None:
        if keys is None:
            credentials = resolve_credentials(profile=profile)
        else:
            canonical = normalize_profile(profile)
            credentials = [Credential(value, "injected", canonical, profile_account(canonical)) for value in keys if value]
        if not credentials:
            raise JEVConnectionError("No TypeSafe credential is configured for the selected profile.")
        self._credentials = tuple(credentials)
        self._timeout = timeout
        self._clients = tuple(
            create_client(credential=credential, profile=profile, timeout=timeout)
            for credential in self._credentials
        )

    @property
    def credential_count(self) -> int:
        return len(self._clients)

    def system_one(self, *, state: Any, questions: Mapping[str, Any], model: str | None = None, timeout: float | None = None, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for index, client in enumerate(self._clients):
            try:
                return client.system_one(
                    state=state,
                    questions=questions,
                    model=model or TYPESAFE_MODEL,
                    timeout=timeout or self._timeout,
                    **kwargs,
                )
            except Exception as exc:
                last_error = exc
                if index + 1 >= len(self._clients) or not _is_auth_failure(exc):
                    raise JEVConnectionError(f"TypeSafe request failed: {type(exc).__name__}") from exc
        raise JEVConnectionError(f"TypeSafe request failed: {type(last_error).__name__ if last_error else 'unknown_error'}") from last_error

    def close(self) -> None:
        for client in self._clients:
            close = getattr(client, "close", None)
            if callable(close):
                close()


JevConnectionError = JEVConnectionError


def resolve_jev_keys() -> tuple[str, ...]:
    """Return configured key values only to an in-process compatibility caller."""
    return tuple(credential.value for credential in resolve_credentials())


def create_jev_client(*, timeout: float = TYPESAFE_TIMEOUT_SECONDS, profile: str | None = None) -> JevClient:
    return JevClient(timeout=timeout, profile=profile)


@lru_cache(maxsize=1)
def get_jev_client() -> JevClient:
    return create_jev_client()


def _is_auth_failure(exc: Exception) -> bool:
    status = getattr(exc, "status_code", getattr(exc, "status", None))
    name = type(exc).__name__.lower()
    return status in {401, 403} or any(token in name for token in ("auth", "unauthor", "forbidden"))


def _sdk_version() -> str:
    try:
        return importlib.metadata.version("typesafe-sdk")
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def doctor(*, root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Return non-secret local readiness information without making a network call."""
    canonical = normalize_profile(profile)
    credentials = resolve_credentials(root, canonical)
    credential = credentials[0] if credentials else None
    return {
        "status": "ready" if credential else "blocked",
        "provider": "TypeSafe JEV",
        "sdk_version": _sdk_version(),
        "model": TYPESAFE_MODEL,
        "profile": canonical,
        "account": credential.account if credential else known_profiles().get(canonical),
        "credential_available": credential is not None,
        "credential_source": credential.source if credential else None,
        "credential_count": len(credentials),
        "credential_sources": [item.source for item in credentials],
        "known_profiles": sorted(known_profiles()),
        "network_call": False,
    }


def probe(*, root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Make one minimal real provider call to verify end-to-end connectivity."""
    result = system_one(
        {
            "objective": CONNECTIVITY_OBJECTIVE,
            "task": "Connectivity probe for the JEV agent connector",
            "constraints": ["Return only the requested judgment."],
        },
        {"reachable": Noul(instructions="Is the JEV decision service reachable and responding?")},
        root=root,
        profile=profile,
    )
    result["probe"] = True
    return result


def questions_from_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Build SDK question objects from the portable JSON question schema."""
    result: dict[str, Any] = {}
    for name, raw in spec.items():
        if not isinstance(raw, Mapping):
            raise ValueError(f"Question {name!r} must be an object")
        kind = str(raw.get("type", raw.get("kind", ""))).lower()
        instructions = str(raw.get("instructions", "")).strip()
        if not instructions:
            raise ValueError(f"Question {name!r} needs non-empty instructions")
        if kind == "choice":
            criteria = raw.get("criteria")
            if not isinstance(criteria, (list, dict)) or not criteria:
                raise ValueError(f"Choice question {name!r} needs criteria")
            if isinstance(criteria, list):
                criteria = {str(option): str(option) for option in criteria}
            result[name] = Choice(instructions=instructions, criteria=criteria)
        elif kind == "noul":
            result[name] = Noul(instructions=instructions)
        elif kind == "score":
            criteria = raw.get("criteria")
            if not isinstance(criteria, list) or not criteria:
                raise ValueError(f"Score question {name!r} needs a non-empty criteria list")
            result[name] = Score(instructions=instructions, criteria=criteria)
        else:
            raise ValueError(f"Unsupported question type for {name!r}: {kind!r}")
    if not result:
        raise ValueError("At least one question is required")
    return result


def resolve_cli_input_path(value: str) -> Path:
    """Resolve a CLI data path relative to the invoking agent when supplied."""
    path = Path(value)
    if path.is_absolute():
        return path
    caller_cwd = os.environ.get("JEV_CALLER_CWD", "").strip()
    base = Path(caller_cwd) if caller_cwd else Path.cwd()
    return (base / path).resolve()


def _json_file(path: str, label: str) -> dict[str, Any]:
    resolved = resolve_cli_input_path(path)
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read {label}: {resolved}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Portable JEV connection for any local agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor", help="Check local SDK and credential readiness without a network call")
    doctor_parser.add_argument("--profile", help="Credential profile alias")
    probe_parser = subparsers.add_parser("probe", help="Make one minimal real JEV request")
    probe_parser.add_argument("--profile", help="Credential profile alias")
    query_parser = subparsers.add_parser("query", help="Run one bounded request from JSON files")
    query_parser.add_argument("--state-file", required=True, help="JSON object containing the task state")
    query_parser.add_argument("--questions-file", required=True, help="Portable JSON question specification")
    query_parser.add_argument("--profile", help="Credential profile alias")
    args = parser.parse_args(argv)

    try:
        if args.command == "doctor":
            result = doctor(profile=args.profile)
        elif args.command == "probe":
            result = probe(profile=args.profile)
        else:
            state = _json_file(args.state_file, "state")
            questions = questions_from_spec(_json_file(args.questions_file, "questions"))
            result = system_one(state, questions, profile=args.profile)
    except Exception as exc:
        # Provider/SDK exceptions are deliberately reduced to their type. Some
        # HTTP clients include request headers or response bodies in ``str(exc)``.
        result = {
            "status": "blocked",
            "provider": "TypeSafe JEV",
            "error": type(exc).__name__,
            "network_call": args.command != "doctor",
        }
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 2

    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("status") in {"ready", "connected"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
