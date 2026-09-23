---
name: typesafe-ai
description: Project-specific guidance for using TypeSafe System One and JEV as bounded typed decision services.
---

# TypeSafe/JEV project guidance

Use this note when changing JEV routing, supervision, typed questions, or the
credential connector in this repository. It is project guidance, not a substitute
for the live API documentation.

## Before changing an integration

1. Read the current [TypeSafe documentation index](https://docs.typesafe.ai/llms.txt)
   and the relevant official API or Python SDK page.
2. Confirm current question primitives, response types, model name, retry rules,
   and timeout behavior from those docs or the installed SDK.
3. Keep credentials in the OS credential manager or process environment. Never
   add tokens to source, prompts, telemetry, test fixtures, or sample output.

## Architecture rules

- Resolve deterministic work in code before calling a model.
- Use JEV only for bounded semantic judgments (route, event supervision,
  conditional deliberation, and completion gate); application code owns budgets,
  validation, and side effects.
- Ask independent typed questions together only when the same state supports
  them. Request only the smallest useful state and question pack.
- Treat probabilities as evidence for a decision, not as correctness guarantees
  or authorization.
- Require observable Luna insufficiency before Sol; require an attempted but
  insufficient Sol result before Astra. Never let a model tier override code
  budgets or safety checks.
- A JEV human-checkpoint answer is a recommendation. It cannot authorize
  purchases, submissions, public releases, or irreversible actions.
- Cache decisions only when the exact state, policy version, model, and questions
  match; omit user content and secrets from telemetry.

## Verification

Add deterministic fake-client tests for typed question shapes, fallbacks,
credential isolation, budgets, and provenance. Make at least one live JEV probe
manually when authorized credentials are configured, and label that result
separately from unit-test evidence. Never make ordinary CI depend on a user's
credential vault or live model service.
