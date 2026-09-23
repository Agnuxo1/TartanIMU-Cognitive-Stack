# Changelog

## 2.0.0 - Advanced Cognitive Architecture

- Added deterministic-first execution and mandatory Luna-first routing.
- Added event-driven JEV checkpoints for evidence, tests, phase changes, budget pressure, escalation, and final delivery.
- Added bounded Luna rounds with early-stop supervision.
- Added evidence-gated second opinions and conditional thinktanks.
- Added compact `continue_from_luna` and clean `restart_with_sol` handoffs.
- Kept Sol as the first escalation tier and Astra as the final escalation tier.
- Added model-inventory verification, quota-safe provider fallback, decision caching, and JSONL observability.
- Added real TypeSafe JEV connector diagnostics and Windows Credential Manager integration.
- Added generated architecture visuals and an expanded operational README.

## 1.0.0 - Recovered Runtime

The recovered runtime is preserved as the first Git commit and the `v1-recovered`
tag. It remains available through Git history; no previous source files are
deleted by the advanced release.

## 4.0.0 — 2026-09-23

- Enforced per-run token, agent-call, and semantic-checkpoint budgets across the full escalation chain.
- Kept the first attempt on Luna and made Astra eligible only after an observed Sol attempt is insufficient or fails.
- Added JEV-guided uncertainty/risk signaling and bounded, Luna-first independent views.
- Reduced telemetry exposure by omitting prompt/result fields and redacting common credential formats and email addresses.
- Added regression tests for escalation budgets, JEV deliberation, and telemetry privacy.
- Added reproducible TartanIMU contract tests to the default test and CI suites; no challenge model or score is claimed.

## 3.0.0 — 2026-09-22

- Added deterministic `ReflexFabric` value-of-information gate for event-driven JEV checkpoints.
- Preserved v2.0.0 under `versions/v2.0.0/` before changing the architecture.
- Changed routine Luna supervision to a deterministic fast path unless semantic review is justified.
- Retained evidence-gated Sol/Astra escalation and conditional think-tank consensus.
- Increased the default Codex CLI timeout from 30 to 90 seconds.
- Added v3 Reflex Fabric tests and upgraded README visual documentation.
- Added four architecture visuals under `assets/` based on the OpenAI-generated visual concept for this release.
