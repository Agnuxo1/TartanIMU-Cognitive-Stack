# Architecture v4

JEV-Orchestrator is a control plane around bounded model calls. It does not
replace model internals; deterministic application code owns routing limits,
validation, escalation order, and side effects.

![JEV-Orchestrator v4 control flow](../assets/architecture-v4.svg)

## Execution path

1. **Deterministic short-circuit.** Exact arithmetic and other supported
   deterministic tasks finish without an LLM.
2. **Typed initial route.** JEV selects among catalogued Luna roles, tools,
   skills, context policies, and success criteria in one bounded request. If
   JEV is unavailable or the checkpoint budget is zero, a local Luna-first
   fallback is used.
3. **Luna first.** Every task requiring generation starts at Luna. A route cannot
   skip directly to Sol or Astra.
4. **Reflex supervision.** A deterministic pre-gate takes the local fast path
   when a Luna round is routine. Failure, uncertainty, ambiguity, risk,
   conflicting evidence, irreversibility, and phase change justify semantic
   supervision, subject to budgets.
5. **Evidence gate.** Code checks JEV's readiness and quality values against
   configured thresholds. A failed gate is evidence of insufficiency, not a
   license for unlimited retries.
6. **Progressive escalation.** Sol can run only after observable Luna
   insufficiency. Astra can run only after a Sol attempt is still insufficient
   or has failed. Each tier and the whole run have independent call limits.
7. **Final result.** The output includes the route, latest supervisor result,
   final gate, and token/cost telemetry summary. It does not authorize external
   actions.

## Budgets

`Budget` limits total observed tokens, total model-agent calls, JEV checkpoints,
Luna rounds, Sol/Astra calls, thinktank views, and handoff size. A run starts
with fresh counters; JEV checkpoint calls are counted separately from worker
calls. Before each optional call the orchestrator checks the relevant counters.
If no checkpoint remains, a local non-ready gate is returned and no further
model-tier escalation is permitted.

Token usage is a guard against starting another request once the observed usage
reaches the cap. A provider may return more tokens than expected for a request;
the cap is therefore not a provider-enforced hard generation limit.

## Thinktank

The optional `Thinktank` asks JEV whether independent views justify the extra
latency and token cost. The panel is bounded to Luna-level independent views,
then a Sol-level critic. It records missing views and failures as unresolved
evidence; it does not use majority vote. `force` is an explicit caller override,
but budgets still apply. The panel is advisory and does not supersede the
orchestrator's ordinary evidence or authorization checks.

## Provenance and privacy

JEV responses, cached decisions, local fallbacks, and deterministic results are
tagged separately. Cache keys include the policy version, model, state, and
question schema. Telemetry omits free-form task/result/context fields, redacts
common credential patterns and email addresses, and is never included in the
public repository. Local cache files may still contain decision inputs; keep
`cache/`, `.cognition/`, `telemetry/`, and user data out of commits.
