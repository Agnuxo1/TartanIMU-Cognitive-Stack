"""Non-secret installation and end-to-end JEV diagnostics."""
from __future__ import annotations

import argparse
import subprocess

from jev_orchestrator.config import MODEL_IDS, OPENAI_KEY_FILE, TYPESAFE_KEY_FILE, TYPESAFE_MODEL, TYPESAFE_SKILL_FILE
from jev_orchestrator.connection import JEVConnectionError, doctor, probe
from jev_orchestrator.runtime import CODEX_CMD


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JEV Orchestrator diagnostics")
    parser.add_argument("--probe", action="store_true", help="make one minimal live TypeSafe request")
    parser.add_argument("--profile", help="credential profile alias or account email")
    args = parser.parse_args(argv)

    status = doctor(profile=args.profile)
    print("JEV ORCHESTRATOR DIAGNOSTICS")
    print("OpenAI API key file:", "PRESENT BUT UNUSED BY DEFAULT" if OPENAI_KEY_FILE.exists() else "MISSING")
    print("Legacy TypeSafe key file:", "PRESENT (vault takes precedence)" if TYPESAFE_KEY_FILE.exists() else "ABSENT")
    print("TypeSafe skill:", "OK" if TYPESAFE_SKILL_FILE.exists() else "MISSING")
    print("TypeSafe skill source:", TYPESAFE_SKILL_FILE)
    print("Codex executable:", "OK" if CODEX_CMD.exists() else "MISSING")
    if CODEX_CMD.exists():
        check = subprocess.run(
            ["cmd.exe", "/d", "/s", "/c", str(CODEX_CMD), "login", "status"],
            capture_output=True,
            text=True,
            shell=False,
            stdin=subprocess.DEVNULL,
            timeout=15,
        )
        raw = (check.stdout or check.stderr).lower()
        print("Codex auth:", "OK" if check.returncode == 0 and "not logged" not in raw else "NOT AUTHENTICATED")
    print("Configured model IDs:", ", ".join(f"{tier}={model}" for tier, model in MODEL_IDS.items()))
    print("Configured Jev model:", TYPESAFE_MODEL)
    print("Credential profile:", status["profile"], status.get("account") or "(custom profile)")
    print("Credential readiness:", "OK" if status["credential_available"] else "MISSING")
    print("Credential source:", status.get("credential_source") or "none")
    print("Known profiles:", ", ".join(status["known_profiles"]))

    if not args.probe:
        print("Network probe:", "SKIPPED (use --probe to test TypeSafe end to end)")
        print("No secret values are printed by this diagnostic.")
        return 0 if status["credential_available"] else 2

    try:
        result = probe(profile=args.profile)
    except (JEVConnectionError, OSError, TimeoutError) as exc:
        print("Network probe: FAILED", type(exc).__name__)
        print("No secret values are printed by this diagnostic.")
        return 2
    print("Network probe:", "OK" if result.get("status") == "connected" else "FAILED")
    print("Provider model:", result.get("model", "unknown"))
    print("No secret values are printed by this diagnostic.")
    return 0 if result.get("status") == "connected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
