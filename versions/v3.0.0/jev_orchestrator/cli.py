"""Machine-readable entry point shared by local agents.

The typed commands emit one JSON document on stdout. The legacy task form
(``run.bat \"...\"``) remains available for the full model orchestrator.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

COMMANDS = {"connect", "route", "supervise", "gatekeep", "decide", "opportunities"}


def _json_input(value: str) -> Any:
    if value == "-":
        return json.load(sys.stdin)
    path = Path(value)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(value)


def _emit(value: Any) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    return 0


def _error(exc: Exception, code: int = 3) -> int:
    error_name = "JEV_NOT_CONFIGURED" if type(exc).__name__ == "JEVNotConfigured" else type(exc).__name__
    print(json.dumps({"provenance": "local", "connected": False, "error": error_name, "message": str(exc)}, ensure_ascii=False, indent=2))
    return code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jev-connect", description="Shared TypeSafe JEV connector and token-efficient orchestrator")
    sub = parser.add_subparsers(dest="command")
    connect = sub.add_parser("connect", help="inspect configuration or perform a remote probe")
    connect.add_argument("--remote", action="store_true", help="make the explicit typed probe")
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
    from .client import TypesafeJevClient

    if args.command == "connect":
        client = TypesafeJevClient()
        if not args.remote:
            return _emit(client.connection_status())
        result = client.probe().as_dict()
        result["connected"] = True
        return _emit(result)
    if args.command == "decide":
        return _emit(TypesafeJevClient().evaluate(_json_input(args.state), _json_input(args.questions)).as_dict())
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
    args = parser.parse_args(argv)
    from .orchestrator import JEVOrchestrator
    from .runtime import ModelBackendUnavailable
    orchestrator = JEVOrchestrator(run_name="cli", use_cache=not args.no_cache)
    try:
        result = orchestrator.execute(args.task, args.context)
    except ModelBackendUnavailable as exc:
        print("MODEL BACKENDS TEMPORARILY UNAVAILABLE")
        print(str(exc))
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
