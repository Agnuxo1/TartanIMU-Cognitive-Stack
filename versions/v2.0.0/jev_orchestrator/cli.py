"""Command-line entry point."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .orchestrator import JEVOrchestrator
from .runtime import ModelBackendUnavailable


def _emit(value: object) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    return 0


def _opportunity_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jev-orchestrator opportunities", description="AI awards, project presentations, and grants workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a blank project profile")
    init.add_argument("path")
    scan = sub.add_parser("scan", help="Discover current opportunities")
    scan.add_argument("--profile", required=True)
    scan.add_argument("--workspace", default="")
    scan.add_argument("--context", default="")
    prepare = sub.add_parser("prepare", help="Prepare an application package")
    prepare.add_argument("--profile", required=True)
    prepare.add_argument("--opportunity", required=True)
    prepare.add_argument("--workspace", default="")
    resume = sub.add_parser("resume", help="Supervise and gate an application")
    resume.add_argument("--application-dir", required=True)
    resume.add_argument("--workspace", default="")
    submit = sub.add_parser("submit", help="Submit through an explicit adapter")
    submit.add_argument("--application-dir", required=True)
    submit.add_argument("--workspace", default="")
    monitor = sub.add_parser("monitor", help="Run periodic scans")
    monitor.add_argument("--profile", required=True)
    monitor.add_argument("--workspace", default="")
    monitor.add_argument("--interval-seconds", type=int, default=86_400)
    monitor.add_argument("--cycles", type=int, default=1)
    monitor.add_argument("--auto-prepare", action="store_true")
    return parser


def _run_opportunities(argv: list[str]) -> int:
    from .opportunity_agent import OpportunityAgent, ProjectProfile, create_profile

    args = _opportunity_parser().parse_args(argv)
    if args.command == "init":
        return _emit({"profile": str(create_profile(Path(args.path)))})
    if args.command in {"scan", "prepare", "monitor"}:
        profile = ProjectProfile.from_path(Path(args.profile))
    workspace = Path(args.workspace) if getattr(args, "workspace", "") else None
    agent = OpportunityAgent(workspace=workspace)
    if args.command == "scan":
        return _emit(agent.scan(profile, args.context))
    if args.command == "prepare":
        return _emit(agent.prepare(profile, Path(args.opportunity)))
    if args.command == "resume":
        return _emit(agent.resume(Path(args.application_dir)))
    if args.command == "submit":
        return _emit(agent.submit(Path(args.application_dir)))
    if args.cycles == 1:
        return _emit(agent.monitor_once(profile, auto_prepare=args.auto_prepare))
    agent.monitor(profile, interval_seconds=args.interval_seconds, cycles=args.cycles, auto_prepare=args.auto_prepare)
    return _emit({"status": "completed", "cycles": args.cycles, "interval_seconds": args.interval_seconds})


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] == "opportunities":
        return _run_opportunities(args_list[1:])
    parser = argparse.ArgumentParser(description="JEV-directed token-efficient multi-agent orchestrator")
    parser.add_argument("task", help="Task to execute")
    parser.add_argument("--context", default="", help="Optional compact context")
    parser.add_argument("--no-cache", action="store_true", help="Disable JEV decision cache")
    args = parser.parse_args(args_list)
    orchestrator = JEVOrchestrator(run_name="cli", use_cache=not args.no_cache)
    try:
        result = orchestrator.execute(args.task, args.context)
    except ModelBackendUnavailable as exc:
        print("MODEL BACKENDS TEMPORARILY UNAVAILABLE")
        print(str(exc))
        print("\n--- TELEMETRY SO FAR ---")
        print(json.dumps(orchestrator.telemetry.summary(), indent=2))
        return 2
    print(result.output)
    print("\n--- TELEMETRY ---")
    print(json.dumps(result.telemetry, indent=2))
    print("\n--- ROUTE ---")
    print(json.dumps(result.route["answers"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
