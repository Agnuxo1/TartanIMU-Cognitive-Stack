"""Store TypeSafe JEV profiles from stdin without writing the input to disk.

Input is a JSON object such as:
{"profile": {"account": "label", "api_key": "..."}}

The command prints only profile labels and never echoes the JSON or secret
values. It is intentionally a one-shot helper for the local Windows vault.
"""
from __future__ import annotations

import json
import os
import sys
import ctypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jev_orchestrator.credentials import (  # noqa: E402
    CredentialStoreError,
    normalize_profile,
    profile_account,
    write_windows_credential,
)


def _disable_console_echo() -> tuple[object, int] | None:
    """Disable terminal echo while a one-shot secret payload is being read."""
    if os.name != "nt" or not sys.stdin.isatty():
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.GetStdHandle(-10)
    mode = ctypes.c_uint32()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return None
    previous = int(mode.value)
    if not kernel32.SetConsoleMode(handle, previous & ~0x0004):
        return None
    return kernel32, previous


def _restore_console_echo(state: tuple[object, int] | None) -> None:
    if state is not None:
        kernel32, previous = state
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), previous)


def main() -> int:
    echo_state = _disable_console_echo()
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict) or not payload:
            raise ValueError("input must be a non-empty JSON object")
        entries: list[tuple[str, str, str | None]] = []
        for raw_profile, raw_entry in payload.items():
            if not isinstance(raw_entry, dict):
                raise ValueError("each profile must contain an object")
            api_key = raw_entry.get("api_key")
            if not isinstance(api_key, str) or not api_key.strip():
                raise ValueError("each profile needs a non-empty api_key")
            profile = normalize_profile(str(raw_profile))
            account = raw_entry.get("account")
            if account is not None and not isinstance(account, str):
                raise ValueError("account labels must be strings")
            entries.append((profile, api_key, account or profile_account(profile)))
        for profile, api_key, account in entries:
            write_windows_credential(profile, api_key, account=account)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, CredentialStoreError):
        print("JEV credential storage failed; no secret value was printed.", file=sys.stderr)
        return 2
    finally:
        _restore_console_echo(echo_state)

    for profile, _api_key, account in entries:
        label = f" account={account}" if account else ""
        print(f"stored profile={profile}{label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
