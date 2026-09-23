# Advanced Cognitive Architecture

JEV Orchestrator 2.0 is a policy-driven execution runtime for agents that
must reduce token use without weakening verification. JEV/TypeSafe is the
director and gatekeeper. It does not replace the worker that performs the
task.

## Runtime contract

1. Inspect the task and state with deterministic code first.
2. Resolve the tool, plugin, application, skill, research method, work method,
   minimal context, strategy, and success criteria through the initial JEV
   decision.
3. If an LLM is necessary, always start with Luna, regardless of initial task
   complexity.
4. Let JEV supervise bounded Luna rounds on meaningful events.
5. Ask for an independent view only when evidence, confidence, verification,
   or progress justifies it.
6. Escalate to Sol only after observable insufficiency. Select either
   `continue_from_luna` with a compact factual handoff or
   `restart_with_sol` without inherited reasoning noise.
7. Use Astra only when Sol is demonstrably insufficient or the risk gate
   requires it.
8. Apply a final evidence gate before delivery and require human confirmation
   for irreversible external actions.

## Event model

The supervisor can be called at the initial route and after:

- new evidence or a material assumption;
- a tool, test, or verification failure;
- completion of a subtask or change of phase;
- stagnation or a low-progress round;
- token-budget pressure;
- a planned escalation;
- the final delivery gate.

The event stream is intentionally bounded. A configurable `max_luna_rounds`
prevents open-ended retries, while JEV may stop earlier when another round is
unlikely to improve the result.

## Deliberation modes

The default is one Luna worker. A second opinion and a thinktank are separate
policies, not automatic fan-out:

- `single_worker`: one bounded Luna path with event supervision;
- `second_opinion`: one independent compact Luna view to resolve a concrete
  conflict or low-confidence claim;
- `thinktank`: two independent views followed by a critic/evidence gate for
  rare high-stakes ambiguity.

Consensus is never a vote detached from evidence. The gate compares claims to
acceptance criteria, test outcomes, source quality, and unresolved risks.

## Context and privacy

Progressive disclosure keeps the first prompt small and reveals plugins,
skills, files, and context only when the route requires them. Handoffs contain
facts, evidence, assumptions, failures, and acceptance criteria. They do not
copy full transcripts or hidden reasoning. Secrets are loaded from Windows
Credential Manager or process configuration and are excluded from Git.

## Observability

The runtime records structured JSONL events for model, provider, tokens,
cached tokens, latency, estimated cost, tools, plugins, skills, confidence,
rounds, escalation reason, handoff mode, and final gate result. Local raw
telemetry stays ignored; sanitized decision records may be committed under
`docs/decisions/`.

## Provider boundary

The project supports the authenticated Codex CLI path and the official OpenAI
SDK path where configured. The router verifies real model IDs before use,
handles quota and timeout failures as controlled provider outcomes, and never
prints credentials. TypeSafe JEV is accessed through the connector and
profile-based Windows Credential Manager setup; no fake plugin integration is
claimed when a tool lives only in a host application.
