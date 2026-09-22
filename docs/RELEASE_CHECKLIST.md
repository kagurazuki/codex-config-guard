# Release checklist

Use this checklist before publishing a release.

## Code and tests

- [ ] Version updated in `pyproject.toml` and `src/codex_config_guard/__init__.py`.
- [ ] Changelog entry added.
- [ ] `python -m compileall -q src` passes.
- [ ] `python -m unittest discover -s tests -v` passes.
- [ ] CLI version/help smoke passes.
- [ ] Markdown migration report contains no config values.

## Evidence and safety

- [ ] Codex-specific claims are backed by a pinned schema/source/docs reference when possible.
- [ ] Exact release comparisons are labeled `verified` only when both sides are exact release tags.
- [ ] No auto-fix/config mutation has been added unintentionally.
- [ ] No telemetry, credential collection, or hosted dependency has been introduced.
- [ ] No private paths/tokens/endpoints appear in tests, examples, or issue templates.

## Repository publication

- [ ] Replace/add package project URLs only after the real repository URL exists.
- [ ] Enable private vulnerability reporting if available.
- [ ] Confirm issue templates and CI render/run correctly on GitHub.
- [ ] Create a signed/tagged release according to maintainer policy.
- [ ] Attach source archive/wheel only after final checksum verification.

## Funding

- [ ] Do not enable `.github/FUNDING.yml` until the maintainer's actual GitHub Sponsors profile exists and has been verified.
- [ ] Keep sponsorship optional; core OSS functionality remains available without payment.
