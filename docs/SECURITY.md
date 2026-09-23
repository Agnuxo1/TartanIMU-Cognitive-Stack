# Security and public-release boundary

## Secrets

- Store TypeSafe keys in Windows Credential Manager or pass them through a
  short-lived process environment. Never commit `.env`, plaintext key files,
  exported vault contents, API keys, or account recovery material.
- Do not put secrets in shell command arguments, prompts, logs, screenshots,
  issue reports, or test fixtures.
- Do not publish private Kaggle submissions, prediction files, challenge data,
  model weights, user telemetry, cache state, or application workspaces without
  explicit rights and a purpose-specific review.

## Local state intentionally excluded

`.gitignore` excludes `secrets/`, `.env*`, `cache/`, `telemetry/`, `.cognition/`,
test scratch, datasets, model checkpoints, outputs, and submission files. The
release audit checks staged files for common credential patterns,
personal account strings, and machine-specific paths. Ignore rules reduce risk;
they are not proof that every future file is safe.

Telemetry omits free-form task and result content and redacts common API-key,
bearer-token, and email patterns. Do not treat generic redaction as permission
to log private content. The exact JEV cache can contain the input state, so it
must remain local.

## Public repository checklist

Before publication:

1. Review the exact files Git will track and inspect the staged diff.
2. Run `scripts/audit_public_release.py --staged` and the full tests.
3. Confirm that no dataset, submission, checkpoint, telemetry, cache, credential,
   personal path, or private research artifact is staged.
4. State model/data/metric limitations explicitly; do not imply that tests on
   synthetic contracts are a competition result.
5. Obtain the owner's license choice before adding a license grant.
