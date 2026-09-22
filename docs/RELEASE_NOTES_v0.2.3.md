# v0.2.3 release notes

Codex Config Guard v0.2.3 is the first public alpha release candidate prepared in the public repository.

## Highlights

- Read-only `config.toml` validation against Codex JSON Schema.
- Version-aware migration reports between exact Codex releases.
- Detection of configured root/feature keys that disappear from the target schema.
- Support-safe Markdown output that omits configuration values.
- Stable finding IDs for automation and issue references.
- No telemetry, hosted backend, account, or API key requirement.

## Safety boundary

The tool does not edit `config.toml`, execute Codex sessions, run MCP servers/hooks, or upload config values.

## Validation

GitHub Actions passes on Python 3.11, 3.12, and 3.13 after the unittest discovery fix.

## Release gate

Create the GitHub release only after confirming the current commit's CI is green. Funding remains disabled until the maintainer completes and verifies a real GitHub Sponsors profile.
