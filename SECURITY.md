# Security Policy

Codex Config Guard reads configuration files that may contain sensitive values. Its public support surfaces are designed to avoid printing those values.

## Supported security boundary

The project should remain safe to run as a local, read-only diagnostic tool:

- no telemetry;
- no account or API key requirement;
- no config mutation by default;
- no execution of Codex sessions, hooks, MCP servers, or project code;
- sanitized Markdown reports omit config values.

## Reporting a vulnerability

Please avoid filing a public issue containing real credentials, tokens, private endpoints, home-directory paths, or full production config files.

Until a dedicated private security-reporting channel is configured on the repository, report only a minimal reproduction with synthetic values. If a vulnerability cannot be described safely without secrets, wait for the repository maintainer to enable a private reporting channel rather than publishing the secret.

## High-priority classes

- accidental secret/value disclosure;
- unsafe path handling;
- unexpected network access;
- configuration mutation;
- command execution triggered by input;
- Markdown/JSON output that leaks sensitive values.
