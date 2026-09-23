"""Audit staged Git content before a public release without printing findings."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys


PRIVATE_PROFILES = ("nautilus" + "kit", "lareli" + "quia")
PRIVATE_PROFILE_PATTERN = re.compile(r"(?i)\b(?:" + "|".join(PRIVATE_PROFILES) + r")\b")
RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("provider_key", re.compile(r"(?i)\b(?:sk|rk)-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(?:TYPESAFE_API_KEY|OPENAI_API_KEY|GITHUB_TOKEN)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{20,}"
        ),
    ),
    ("local_user_path", re.compile(r"(?i)[A-Z]:\\Users\\Windows-500GB(?:\\[^\s\"'<>]*)?")),
    ("recovery_workspace_path", re.compile(r"(?i)[A-Z]:\\Rescate-C-2026-09-21(?:\\[^\s\"'<>]*)?")),
    ("private_jev_profile", PRIVATE_PROFILE_PATTERN),
)
EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b")
PUBLIC_TEST_DOMAINS = {"example.com", "example.org", "example.net", "example.test", "test.invalid"}


def findings_for_text(text: str) -> list[str]:
    """Return rule identifiers only; never return the matched source text."""
    findings = [rule for rule, pattern in RULES if pattern.search(text)]
    if any(
        match.group(1).lower() not in PUBLIC_TEST_DOMAINS
        and not match.group(1).lower().endswith((".invalid", ".example"))
        for match in EMAIL.finditer(text)
    ):
        findings.append("email_address")
    return sorted(set(findings))


def staged_paths() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [name.decode("utf-8", errors="surrogateescape") for name in result.stdout.split(b"\0") if name]


def staged_file(path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f":{path}"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check staged files for common public-release leaks.")
    parser.add_argument(
        "--staged",
        action="store_true",
        help="explicitly confirm that the Git index (not the whole working tree) is audited",
    )
    args = parser.parse_args(argv)
    if not args.staged:
        parser.error("stage the intended release files, review `git diff --cached`, then pass --staged")
    try:
        paths = staged_paths()
        if not paths:
            print("No staged files found; nothing was audited.", file=sys.stderr)
            return 2
        problems: list[tuple[str, str]] = []
        for path in paths:
            content = staged_file(path)
            if b"\0" in content:
                continue
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                continue
            problems.extend((path, rule) for rule in findings_for_text(text))
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Release audit could not read the Git index ({type(exc).__name__}).", file=sys.stderr)
        return 2
    if problems:
        for path, rule in sorted(problems):
            print(f"REVIEW {path}: {rule}")
        print("Audit failed; matched values were deliberately not printed.", file=sys.stderr)
        return 1
    print(f"Public-release scan passed for {len(paths)} staged files (text files only).")
    print("Review ignored/binary files and staged changes separately; this is a heuristic, not a guarantee.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
