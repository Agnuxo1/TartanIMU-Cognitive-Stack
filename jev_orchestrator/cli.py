"""Machine-readable entry point shared by local agents.

The typed commands emit one JSON document on stdout. The legacy task form
(``run.bat \"...\"``) remains available for the full model orchestrator.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path
from typing import Any

COMMANDS = {"connect", "route", "supervise", "gatekeep", "decide", "thinktank", "opportunities"}


def _json_input(value: str) -> Any:
    if value == "-":
        return json.load(sys.stdin)
    if value.lstrip().startswith(("{", "[")):
        return json.loads(value)
    from .connection import resolve_cli_input_path

    path = resolve_cli_input_path(value)
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        pass
    return json.loads(value)


def _emit(value: Any) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    return 0


def _error(exc: Exception, code: int = 3) -> int:
    error_name = "JEV_NOT_CONFIGURED" if type(exc).__name__ == "JEVNotConfigured" else type(exc).__name__
    print(json.dumps({"provenance": "local", "connected": False, "error": error_name}, ensure_ascii=False, indent=2))
    return code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jev-connect", description="Shared TypeSafe JEV connector and token-efficient orchestrator")
    sub = parser.add_subparsers(dest="command")
    connect = sub.add_parser("connect", help="inspect configuration or perform a remote probe")
    connect.add_argument("--remote", action="store_true", help="make the explicit typed probe")
    connect.add_argument("--profile", help="credential profile alias")
    route = sub.add_parser("route", help="run the shared JEV router")
    route.add_argument("task")
    route.add_argument("--context", default="{}", help="JSON object, JSON file, or -")
    supervise = sub.add_parser("supervise", help="run the JEV supervisor checkpoint")
    supervise.add_argument("state", help="JSON value, JSON file, or -")
    gatekeep = sub.add_parser("gatekeep", help="run the JEV completion gate")
    gatekeep.add_argument("state", help="JSON object, JSON file, or -")
    decide = sub.add_parser("decide", help="evaluate arbitrary typed questions")
    decide.add_argument("--state", required=True, help="JSON value, JSON file, or -")
    decide.add_argument("--questions", required=True, help="JSON object or JSON file")
    decide.add_argument("--profile", help="credential profile alias")
    thinktank = sub.add_parser("thinktank", help="ask JEV whether bounded independent model views are worthwhile")
    thinktank.add_argument("task")
    thinktank.add_argument("--context", default="", help="compact factual context")
    thinktank.add_argument("--risk", choices=("low", "moderate", "high", "critical"), default="moderate")
    thinktank.add_argument("--uncertainty", type=float, default=0.0)
    thinktank.add_argument("--conflicting-evidence", action="store_true")
    opportunities = sub.add_parser("opportunities", help="discover and process AI awards, presentations, and grants")
    opportunity_commands = opportunities.add_subparsers(dest="opportunity_command")
    init = opportunity_commands.add_parser("init", help="create an empty project profile")
    init.add_argument("path")
    scan = opportunity_commands.add_parser("scan", help="scan current opportunities and persist an inbox")
    scan.add_argument("--profile", required=True)
    scan.add_argument("--workspace", default="")
    scan.add_argument("--context", default="")
    prepare = opportunity_commands.add_parser("prepare", help="draft a complete application package")
    prepare.add_argument("--profile", required=True)
    prepare.add_argument("--opportunity", required=True)
    prepare.add_argument("--workspace", default="")
    resume = opportunity_commands.add_parser("resume", help="supervise and gate an application package")
    resume.add_argument("--application-dir", required=True)
    resume.add_argument("--workspace", default="")
    submit = opportunity_commands.add_parser("submit", help="submit through an explicitly configured adapter")
    submit.add_argument("--application-dir", required=True)
    submit.add_argument("--workspace", default="")
    monitor = opportunity_commands.add_parser("monitor", help="run one or more periodic opportunity scans")
    monitor.add_argument("--profile", required=True)
    monitor.add_argument("--workspace", default="")
    monitor.add_argument("--interval-seconds", type=int, default=86_400)
    monitor.add_argument("--cycles", type=int, default=1)
    monitor.add_argument("--auto-prepare", action="store_true")
    return parser


def _run_typed(args: argparse.Namespace) -> int:
    if args.command == "connect":
        from .connection import doctor, probe

        status = doctor(profile=args.profile)
        if not args.remote:
            return _emit({"configured": status["credential_available"], "provenance": "local", **status})
        if not status["credential_available"]:
            _emit({"provenance": "local", "connected": False, "error": "JEV_NOT_CONFIGURED"})
            return 2
        try:
            result = probe(profile=args.profile)
        except Exception as exc:
            print(json.dumps({"provenance": "local", "connected": False, "error": type(exc).__name__}, ensure_ascii=False, indent=2))
            return 2
        result["connected"] = True
        return _emit(result)
    if args.command == "decide":
        from .connection import questions_from_spec, system_one

        state = _json_input(args.state)
        questions = _json_input(args.questions)
        if not isinstance(state, dict) or not isinstance(questions, dict):
            raise ValueError("--state and --questions must each contain a JSON object")
        return _emit(system_one(state, questions_from_spec(questions), profile=args.profile))
    if args.command == "thinktank":
        from .orchestrator import JEVOrchestrator
        from .thinktank import Thinktank

        orchestrator = JEVOrchestrator(run_name="cli-thinktank", use_cache=True)
        result = Thinktank(orchestrator.router, orchestrator.runtime, orchestrator.telemetry, orchestrator.budget).run(
            args.task,
            args.context,
            risk=args.risk,
            uncertainty=args.uncertainty,
            conflicting_evidence=args.conflicting_evidence,
        )
        return _emit(asdict(result))
    if args.command == "opportunities":
        from .opportunity_agent import OpportunityAgent, ProjectProfile, create_profile

        if args.opportunity_command is None:
            return _emit({"provenance": "local", "message": "choose an opportunities subcommand"})
        if args.opportunity_command == "init":
            return _emit({"profile": str(create_profile(Path(args.path)))})
        if args.opportunity_command in {"scan", "prepare", "monitor"}:
            profile = ProjectProfile.from_path(Path(args.profile))
        workspace = Path(args.workspace) if getattr(args, "workspace", "") else None
        agent = OpportunityAgent(workspace=workspace)
        if args.opportunity_command == "scan":
            return _emit(agent.scan(profile, args.context))
        if args.opportunity_command == "prepare":
            return _emit(agent.prepare(profile, Path(args.opportunity)))
        if args.opportunity_command == "resume":
            return _emit(agent.resume(Path(args.application_dir)))
        if args.opportunity_command == "submit":
            return _emit(agent.submit(Path(args.application_dir)))
        if args.opportunity_command == "monitor":
            if args.cycles == 1:
                return _emit(agent.monitor_once(profile, auto_prepare=args.auto_prepare))
            agent.monitor(profile, interval_seconds=args.interval_seconds, cycles=args.cycles, auto_prepare=args.auto_prepare)
            return _emit({"status": "completed", "cycles": args.cycles, "interval_seconds": args.interval_seconds})
        return _emit({"provenance": "local", "message": f"unknown opportunities command: {args.opportunity_command}"})

    from .router import JevRouter
    from .telemetry import Telemetry

    router = JevRouter(Telemetry("cli-" + args.command), use_cache=True)
    if args.command == "route":
        context = _json_input(args.context)
        if not isinstance(context, dict):
            raise ValueError("--context must contain a JSON object")
        return _emit(router.initial(args.task, json.dumps(context, ensure_ascii=False)))
    state = _json_input(args.state)
    if not isinstance(state, dict):
        raise ValueError("state must contain a JSON object")
    if args.command == "supervise":
        return _emit(router.supervise(state))
    return _emit(router.gate(str(state.get("objective", "")), json.dumps(state, ensure_ascii=False), state.get("unresolved", [])))


def _run_legacy_task(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="JEV-directed token-efficient multi-agent orchestrator")
    parser.add_argument("task")
    parser.add_argument("--context", default="", help="Optional compact context")
    parser.add_argument("--no-cache", action="store_true", help="Disable JEV decision cache")
    parser.add_argument("--risk", choices=("low", "moderate", "high", "critical"), default="moderate")
    parser.add_argument("--uncertainty", type=float, default=0.0)
    parser.add_argument("--conflicting-evidence", action="store_true")
    parser.add_argument("--irreversible", action="store_true")
    args = parser.parse_args(argv)
    from .orchestrator import JEVOrchestrator
    from .runtime import ModelBackendUnavailable
    orchestrator = JEVOrchestrator(run_name="cli", use_cache=not args.no_cache)
    try:
        result = orchestrator.execute(
            args.task,
            args.context,
            risk=args.risk,
            uncertainty=args.uncertainty,
            conflicting_evidence=args.conflicting_evidence,
            irreversible=args.irreversible,
        )
    except ModelBackendUnavailable as exc:
        print("MODEL BACKENDS TEMPORARILY UNAVAILABLE")
        print(type(exc).__name__)
        print(json.dumps(orchestrator.telemetry.summary(), indent=2))
        return 2
    print(result.output)
    print("\n--- TELEMETRY ---")
    print(json.dumps(result.telemetry, indent=2))
    print("\n--- ROUTE ---")
    print(json.dumps(result.route["answers"], indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] not in COMMANDS and not args[0].startswith("-"):
        return _run_legacy_task(args)
    parser = _build_parser()
    parsed = parser.parse_args(args)
    if parsed.command is None:
        parser.print_help()
        return 0
    try:
        return _run_typed(parsed)
    except Exception as exc:
        from .client import JEVNotConfigured
        return _error(exc, 2 if isinstance(exc, JEVNotConfigured) else 3)


if __name__ == "__main__":
    raise SystemExit(main())
