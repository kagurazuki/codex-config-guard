# Roadmap

## v0.1: read-only preflight

- TOML parse check
- Official-schema validation
- Project-scope ignored-key warnings
- High-confidence renamed-key warnings
- Root/feature schema diff
- JSON output and stable rule IDs

## v0.2: version-aware migration report

- Accept installed Codex version or release tag
- Resolve a schema pinned to that release
- Report key introduction/removal across a chosen upgrade range
- Mark evidence as `verified`, `version-ambiguous`, or `docs-only`
- Generate a sanitized Markdown report for issues/support
- Keep config values out of Markdown reports

## v0.3: effective-config evidence

Only after direct source validation against Codex behavior:

- Enumerate config layers and precedence
- Explain which layer wins for each supported setting
- Detect project settings ignored by scope
- Never expose secret values
- Remain read-only by default

## Revenue-compatible direction

If the tool earns real adoption, add GitHub Sponsors first. Consider an Open Source Maintenance Fee binary-release model only after separate legal and operational review. The OSS core should remain useful without payment.
