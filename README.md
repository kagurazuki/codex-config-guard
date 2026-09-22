# Codex Config Guard

**Unofficial community tool. Not affiliated with or endorsed by OpenAI.**

A local, read-only CLI for recurring Codex configuration problems:

1. Validate `config.toml` against a Codex JSON Schema while surfacing migration/scope mistakes that plain schema validation can miss.
2. Compare two schemas.
3. Build a **version-aware migration report** for a Codex upgrade, including configured keys that disappear from the target schema.

The project is intentionally local-first: no account, hosted backend, telemetry, or API key is required.

**Status:** public alpha. GitHub Actions passes on Python 3.11, 3.12, and 3.13. Runtime behavior is intentionally narrow and read-only.

## Install for development

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e .
```

## Validate a user config

```bash
codex-config-guard check ~/.codex/config.toml
```

By default, `check` fetches the current official schema from:

`https://developers.openai.com/codex/config-schema.json`

Use a local schema for reproducible/offline checks:

```bash
codex-config-guard check ~/.codex/config.toml --schema ./config.schema.json --require-schema
```

## Validate project-local config

```bash
codex-config-guard check ./.codex/config.toml --scope project
```

Project scope additionally warns about root settings that current Codex docs say are ignored when placed in project-local config.

## Compare two schemas

```bash
codex-config-guard diff-schema ./v0.135.schema.json ./v0.150.schema.json
```

## Version-aware migration report

Exact Codex releases in the upstream repository use `rust-vX.Y.Z` tags. You can pass a plain version and the CLI normalizes it automatically:

```bash
codex-config-guard migration-report \
  --from-version 0.135.0 \
  --to-version 0.150.0 \
  --config ~/.codex/config.toml \
  --output migration-report.md
```

The command resolves the generated config schema pinned to each release, compares root and feature keys, validates the supplied config against the target schema, and writes a support-safe Markdown report.

For reproducible/offline runs, override both schemas:

```bash
codex-config-guard migration-report \
  --from-version 0.135.0 \
  --to-version 0.150.0 \
  --from-schema ./0.135.0.schema.json \
  --to-schema ./0.150.0.schema.json \
  --config ~/.codex/config.toml
```

Structured output:

```bash
codex-config-guard migration-report \
  --from-version 0.135.0 \
  --to-version 0.150.0 \
  --config ~/.codex/config.toml \
  --json
```

### Evidence labels

- `verified`: comparison is pinned to exact `rust-vX.Y.Z` release schemas.
- `version-ambiguous`: at least one side is a moving/non-release Git ref such as `main`.
- `docs-only`: migration hint is retained from documentation/current guidance but is not inferred from schema removal alone.

### Privacy / sanitization

Markdown migration reports contain key paths and rule IDs, **not config values**. This is deliberate because config values can contain tokens, endpoints, local paths, or other sensitive material.

## Stable finding IDs

- `CG001`: TOML parse/read failure
- `CG101`: JSON Schema validation failure
- `CG201`: legacy/renamed root key detected
- `CG202`: project-local setting that current docs say is ignored
- `CG301`: schema fetch/load failure
- `CG401`: configured root key removed from the target release schema
- `CG402`: configured feature key removed from the target release schema
- `CG403`: docs-only legacy/rename migration hint in a version report

## Safety boundaries

Codex Config Guard is read-only. It does **not**:

- edit or auto-fix `config.toml`
- claim that a removed key is safe to delete without release-specific review
- execute Codex sessions, hooks, MCP servers, or project code
- upload configuration contents
- render config values in Markdown support reports

## Contributing and security

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md). Please never post real tokens, private endpoints, or full production configs in public issues.

## Publication / funding

Publication guidance lives in [`docs/PUBLISHING_HANDOFF.md`](docs/PUBLISHING_HANDOFF.md). Sponsorship is intentionally not activated with a placeholder link; see [`docs/SPONSORING.md`](docs/SPONSORING.md).

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Repository bootstrap

The public repository is `kagurazuki/codex-config-guard`. The one-time bootstrap helper is retained for reproducibility and recovery documentation. It does not tag a release or enable funding.
