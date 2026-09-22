# Changelog

## 0.2.3 - 2026-09-22

- Published repository metadata now points to `kagurazuki/codex-config-guard`.
- Added GitHub Actions compatibility fix for unittest discovery.
- Verified CI passes on Python 3.11, 3.12, and 3.13.
- Kept funding links disabled until a real sponsorship channel is configured.

## 0.2.2 - 2026-09-22

- Added fail-closed one-time GitHub repository bootstrap helper (`scripts/publish_github.py`).
- Added Windows-friendly GitHub publication handoff documentation.
- Kept repository creation dry-run by default and refused to reuse an existing repository name.
- Added repository identity/visibility read-back after bootstrap.
- Updated outbound schema-fetch User-Agent strings to use the package version.

## 0.2.1 - 2026-09-22

- Added publication-readiness files: contributing guide, security policy, issue templates, pull-request template, and GitHub Actions CI.
- Added a release checklist and publication handoff guide.
- Added a sponsorship activation note without enabling a broken funding link.
- Removed placeholder repository URLs from package metadata until the real repository exists.
- No runtime behavior changes; the CLI remains read-only.

## 0.2.0 - 2026-09-22

- Added `migration-report` for version-aware Codex upgrades.
- Normalizes Codex releases to upstream `rust-vX.Y.Z` tags and resolves the matching generated schema.
- Reports root/feature key additions and removals across an upgrade range.
- Flags configured keys that disappear from the target schema with stable IDs `CG401` and `CG402`.
- Carries legacy rename hints as `CG403` with explicit `docs-only` evidence status.
- Marks exact release comparisons as `verified` and moving Git refs as `version-ambiguous`.
- Added support-safe Markdown reports that omit config values, plus structured JSON output.
- Remains read-only; no automatic config editing or migration.

## 0.1.0 - 2026-09-22

- Initial read-only `check` command.
- Official/local JSON Schema support.
- Compatibility warnings for selected renamed keys.
- Project-local ignored-setting warnings.
- Schema diff for root and feature keys.
- JSON output and stable finding IDs.
