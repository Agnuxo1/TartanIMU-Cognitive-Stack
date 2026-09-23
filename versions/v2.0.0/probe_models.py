"""Inspect or verify subscription model IDs through the authenticated Codex CLI."""
from __future__ import annotations

import argparse
import json
import subprocess

from jev_orchestrator.config import CODEX_TIMEOUT_SECONDS, MODEL_IDS, ROOT
from jev_orchestrator.runtime import AgentRuntime


def _status(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=CODEX_TIMEOUT_SECONDS, shell=False)
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    raw = (result.stdout + "\n" + result.stderr).lower()
    if "not logged" in raw or "unauthenticated" in raw:
        return "not_authenticated"
    return "ok" if result.returncode == 0 else "unavailable"


def _verify_model(command: list[str], model: str) -> str:
    args = [*command, "exec", "-m", model, "--json", "--skip-git-repo-check", "--ephemeral", "-"]
    try:
        result = subprocess.run(args, input="Reply only with MODEL_PROBE_OK.", capture_output=True, text=True, cwd=ROOT, timeout=CODEX_TIMEOUT_SECONDS, shell=False)
    except subprocess.TimeoutExpired:
        return "timeout"
    if result.returncode != 0:
        return "unavailable"
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.failed":
            return "unavailable"
    return "ok"


def main() -> None:
    parser = argparse.ArgumentParser(description="Check ChatGPT subscription model access through Codex CLI")
    parser.add_argument("--verify", action="store_true", help="Run one minimal subscription probe per configured model")
    args = parser.parse_args()
    command = AgentRuntime._codex_executable()
    report = {"backend": "codex_subscription", "configured": MODEL_IDS, "authentication": "unavailable"}
    if command:
        report["authentication"] = _status([*command, "login", "status"])
        if args.verify and report["authentication"] == "ok":
            report["verification"] = {tier: _verify_model(command, model) for tier, model in MODEL_IDS.items()}
        else:
            report["verification"] = "performed on successful runtime execution; use --verify for explicit probes"
    else:
        report["verification"] = "codex_cli_missing"
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
