# Publication handoff

Codex Config Guard is currently prepared as a local publication candidate. No repository creation is assumed by this document.

## Proposed public repository

Suggested repository name: `codex-config-guard`.

Suggested short description:

> Read-only validator and version-aware migration reports for Codex `config.toml`.

Suggested topics:

- `openai-codex`
- `codex`
- `config`
- `toml`
- `validator`
- `developer-tools`
- `migration`

## Initial publication sequence

1. Create an empty public repository under the chosen maintainer account.
2. Upload the project contents without changing runtime behavior.
3. Confirm GitHub Actions passes on Python 3.11, 3.12, and 3.13.
4. Confirm issue templates do not invite users to paste secrets.
5. Add the real repository URL to `[project.urls]` in `pyproject.toml`.
6. Tag the first public release only after a clean CI/read-back.
7. Enable GitHub Sponsors later, after the maintainer's Sponsors onboarding/profile is actually ready.

## First public release positioning

Lead with the narrow problem, not a generic "AI agent doctor" claim:

- validate Codex configuration locally;
- compare generated config schemas between releases;
- identify configured keys that disappear in a target release;
- generate support-safe reports without config values.

Avoid claims that the tool can prove the complete effective runtime config until v0.3 effective-config evidence is implemented and directly validated.

## Human gate

The public repository now exists at `https://github.com/kagurazuki/codex-config-guard`. The fail-closed bootstrap helper remains in the repository as recovery/documentation tooling; routine maintenance should use the connected GitHub surface when available.
