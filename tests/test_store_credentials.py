from __future__ import annotations

from scripts import store_jev_credentials


class InteractiveInput:
    def isatty(self):
        return True


def test_interactive_credential_storage_hides_and_does_not_print_key(monkeypatch, capsys):
    stored = []
    monkeypatch.setattr(store_jev_credentials.sys, "stdin", InteractiveInput())
    monkeypatch.setattr(store_jev_credentials.getpass, "getpass", lambda prompt: "test-secret-value")
    monkeypatch.setattr(store_jev_credentials, "write_windows_credential", lambda *args, **kwargs: stored.append((args, kwargs)))

    assert store_jev_credentials.main(["--profile", "profile-b", "--account", "test label"]) == 0

    output = capsys.readouterr().out
    assert "profile-b" in output
    assert "test-secret-value" not in output
    assert stored[0][0] == ("profile-b", "test-secret-value")
