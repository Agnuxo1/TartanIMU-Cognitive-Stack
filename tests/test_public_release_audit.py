from scripts.audit_public_release import findings_for_text


def test_audit_flags_secret_and_private_profile_without_echoing_values():
    fake_key = "sk-proj-" + "x" * 28
    private_alias = "lareli" + "quia"
    findings = findings_for_text(f"TYPESAFE_API_KEY={fake_key}; alias={private_alias}")

    assert findings == ["credential_assignment", "private_jev_profile", "provider_key"]
    assert fake_key not in " ".join(findings)


def test_audit_allows_reserved_test_email_domain():
    assert findings_for_text("fixture contact: test@example.com") == []


def test_audit_flags_non_reserved_contact_email():
    address = "person" + "@" + "private.example.org.uk"
    assert findings_for_text(address) == ["email_address"]
