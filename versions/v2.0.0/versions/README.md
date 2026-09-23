# Preserved versions

This repository keeps the recovered runtime and the advanced architecture in
Git history instead of deleting or overwriting earlier work.

- `v1-recovered`: recovered, tested JEV connector and baseline orchestrator.
- `v2.0.0-advanced`: current deterministic-first, Luna-first cognitive router.

The release notes for the advanced version are in
`docs/releases/v2.0.0.md`.

To inspect the preserved baseline locally:

```bat
git show v1-recovered:README.md
git diff v1-recovered..v2.0.0-advanced --stat
```

Runtime artifacts, credentials, caches, and local telemetry remain excluded by
`.gitignore`. Exported decision records under `docs/decisions/` are sanitized
and safe to review.
