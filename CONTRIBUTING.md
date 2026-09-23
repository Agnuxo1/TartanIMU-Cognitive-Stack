# Contributing

This project is a bounded cognitive-orchestration runtime plus a small,
synthetic-only TartanIMU contract scaffold. Contributions must preserve the
separation between model advice and deterministic policy.

## Development setup

Use Python 3.11 or newer. On Windows, prefer a virtual environment on a drive
with enough space:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m compileall -q jev_orchestrator tests competitions/tartanimu/src competitions/tartanimu/tests
.\.venv\Scripts\python.exe -m pytest -q
# Stage only files that have been reviewed for publication.
git diff --cached --check
.\.venv\Scripts\python.exe scripts\audit_public_release.py --staged
```

Tests must use deterministic fake clients and must not depend on a developer's
Credential Manager, Kaggle account, external model service, dataset, or private
workspace. Keep TartanIMU tests synthetic and leakage-safe unless data rights
and competition rules explicitly allow otherwise.

## Change requirements

- Keep Luna-first, Sol-before-Astra order and enforce budgets in code.
- Add tests for new decisions, failure paths, privacy behavior, and budget limits.
- Use official sources for time-sensitive challenge requirements; record dates
  and unknowns separately from verified facts.
- Never fabricate scores, receipts, model availability, or external execution.
- Do not add data, weights, credentials, or telemetry to a patch.
