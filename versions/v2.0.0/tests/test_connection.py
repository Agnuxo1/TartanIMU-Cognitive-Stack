"""Tests for the portable JEV connection contract without network calls."""
from __future__ import annotations

import json

from jev_orchestrator.connection import CONNECTIVITY_OBJECTIVE, doctor, questions_from_spec, resolve_credential, resolve_credentials


def test_environment_credential_has_precedence(monkeypatch, tmp_path):
    key_file = tmp_path / "typesafe_api_key.txt"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.setenv("TYPESAFE_API_KEY", "environment-key")
    monkeypatch.setenv("JEV_TYPESAFE_KEY_FILE", str(key_file))

    credential = resolve_credential(root=tmp_path)

    assert credential is not None
    assert credential.value == "environment-key"
    assert credential.source == "environment:TYPESAFE_API_KEY"


def test_environment_credential_does_not_mix_local_accounts(monkeypatch, tmp_path):
    key_file = tmp_path / "typesafe_api_keys.txt"
    key_file.write_text("file-key-1\nfile-key-2\n", encoding="utf-8")
    monkeypatch.setenv("TYPESAFE_API_KEY", "environment-key")
    credentials = __import__("jev_orchestrator.connection", fromlist=["resolve_credentials"]).resolve_credentials(root=tmp_path)
    assert [credential.value for credential in credentials] == ["environment-key"]


def test_file_credential_and_doctor_are_non_secret(monkeypatch, tmp_path):
    key_file = tmp_path / "secrets" / "typesafe_api_key.txt"
    key_file.parent.mkdir()
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_TYPESAFE_KEY_FILE", raising=False)
    monkeypatch.setenv("JEV_ALLOW_LEGACY_SECRET_FILE", "1")

    credential = resolve_credential(root=tmp_path)
    status = doctor(root=tmp_path)

    assert credential is not None
    assert status["status"] == "ready"
    assert status["credential_available"] is True
    assert "file-key" not in json.dumps(status)


def test_profile_selects_one_entry_from_multikey_file(monkeypatch, tmp_path):
    key_file = tmp_path / "secrets" / "typesafe_api_keys.txt"
    key_file.parent.mkdir()
    key_file.write_text("apikey_one\napikey_two\napikey_three\n", encoding="utf-8")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_TYPESAFE_KEY_FILE", raising=False)
    monkeypatch.setenv("JEV_ALLOW_LEGACY_SECRET_FILE", "1")

    credential = resolve_credential(root=tmp_path, profile="profile-b")

    assert credential is not None
    assert credential.value == "apikey_two"
    assert credential.profile == "profile-b"


def test_general_utilities_file_is_a_bounded_typesafe_source(monkeypatch, tmp_path):
    utility = tmp_path / "UTILIDADES_HERRAMIENTAS_APIs.txt"
    utility.write_text(
        "TypeSafe AI JEV\n"
        "apikey_first\n"
        "apikey_second\n"
        "Nuevo Github Token\n"
        "apikey_other\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("JEV_TYPESAFE_KEY_FILE", str(utility))
    monkeypatch.setenv("JEV_ALLOW_LEGACY_SECRET_FILE", "1")
    monkeypatch.setattr("jev_orchestrator.connection.resolve_profile_credential", lambda **_: None)

    credentials = resolve_credentials(root=tmp_path)

    assert [credential.value for credential in credentials[:2]] == ["apikey_first", "apikey_second"]
    status = doctor(root=tmp_path)
    assert status["credential_count"] == 1
    assert "apikey_first" not in json.dumps(status)


def test_portable_question_schema_builds_sdk_questions():
    questions = questions_from_spec(
        {
            "route": {"type": "choice", "instructions": "Choose one", "criteria": ["a", "b"]},
            "risk": {"type": "noul", "instructions": "Is this risky?"},
            "quality": {"type": "score", "instructions": "Rate quality", "criteria": ["low", "high"]},
        }
    )

    assert set(questions) == {"route", "risk", "quality"}


def test_connectivity_probe_uses_a_generic_objective(monkeypatch):
    import jev_orchestrator.connection as connection

    captured = {}

    def fake_system_one(state, questions, **kwargs):
        captured["state"] = state
        return {"status": "connected", "model": "test", "answers": {}, "usage": {}}

    monkeypatch.setattr(connection, "system_one", fake_system_one)
    result = connection.probe()

    assert result["probe"] is True
    assert captured["state"]["objective"] == CONNECTIVITY_OBJECTIVE
    assert "UMUD" not in captured["state"]["objective"]
