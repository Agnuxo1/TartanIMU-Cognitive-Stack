"""Run a small real TypeSafe JEV request for one credential profile."""
from __future__ import annotations

import argparse

from jev_orchestrator.connection import CONNECTIVITY_OBJECTIVE, JEVConnectionError, system_one
from typesafe_sdk import Choice, Noul


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe TypeSafe JEV without printing credentials")
    parser.add_argument("--profile", help="credential profile alias or account email")
    args = parser.parse_args(argv)
    try:
        response = system_one(
            {
                "objective": CONNECTIVITY_OBJECTIVE,
                "task": "Connectivity probe for the JEV agent connector",
                "constraints": ["Return only the requested judgment."],
            },
            {
                "agent": Choice(
                    instructions="Which agent should handle this connectivity check?",
                    criteria={"luna_scout": "Cheap retrieval and initial research", "luna_coder": "Simple implementation work"},
                ),
                "reachable": Noul(instructions="Is the JEV decision service reachable and responding?"),
            },
            profile=args.profile,
        )
    except (JEVConnectionError, OSError, TimeoutError) as exc:
        print("JEV probe failed:", type(exc).__name__)
        return 2

    print("model=", response["model"])
    print("status=", response["status"])
    print("answers=", response["answers"])
    print("usage=", response["usage"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
