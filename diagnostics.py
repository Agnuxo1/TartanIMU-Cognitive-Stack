"""Non-secret installation diagnostics."""
from __future__ import annotations

import subprocess
from pathlib import Path

from jev_orchestrator.config import MODEL_IDS, OPENAI_KEY_FILE, TYPESAFE_MODEL, TYPESAFE_SKILL_FILE
from jev_orchestrator.connection import JevConnectionError, resolve_jev_keys
from jev_orchestrator.runtime import CODEX_CMD

print("JEV ORCHESTRATOR DIAGNOSTICS")
print("OpenAI API key file:", "PRESENT BUT UNUSED BY DEFAULT" if OPENAI_KEY_FILE.exists() else "MISSING")
print("TypeSafe credential source:", "process environment only (TYPESAFE_API_KEY)")
try:
    print("TypeSafe credentials configured:", len(resolve_jev_keys()))
except JevConnectionError:
    print("TypeSafe credentials configured: 0")
print("TypeSafe skill:", "OK" if TYPESAFE_SKILL_FILE.exists() else "MISSING")
print("TypeSafe skill source:", TYPESAFE_SKILL_FILE)
print("Codex executable:", "OK" if CODEX_CMD.exists() else "MISSING")
if CODEX_CMD.exists():
    check = subprocess.run(["cmd.exe", "/d", "/s", "/c", str(CODEX_CMD), "login", "status"], capture_output=True, text=True, shell=False, stdin=subprocess.DEVNULL, timeout=15)
    raw = (check.stdout or check.stderr).lower()
    print("Codex auth:", "OK" if check.returncode == 0 and "not logged" not in raw else "NOT AUTHENTICATED")
print("Configured model IDs:", ", ".join(f"{tier}={model}" for tier, model in MODEL_IDS.items()))
print("Configured Jev model:", TYPESAFE_MODEL)
print("Model backend:", "ChatGPT subscription via Codex CLI")
print("Subscription model IDs:", ", ".join(f"{tier}={model}" for tier, model in MODEL_IDS.items()))
print("Model verification:", "performed on successful Codex execution; no OpenAI API inventory call is made")
print("No secret values are printed by this diagnostic.")
