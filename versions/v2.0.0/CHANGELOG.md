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
