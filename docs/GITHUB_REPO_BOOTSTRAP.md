# GitHub repository bootstrap

The current ChatGPT GitHub connector can maintain files/issues/branches in an existing repository, but it does not expose repository creation in this environment. The project therefore includes a **one-time, fail-closed bootstrap helper** for the maintainer.

## Lowest-effort path on Windows 11

From the extracted project directory:

```powershell
python scripts/publish_github.py
```

That is a dry run and changes nothing.

When the printed plan looks correct and GitHub CLI is installed/authenticated:

```powershell
python scripts/publish_github.py --apply
```

Apply mode:

- discovers the authenticated GitHub login;
- refuses to reuse an existing repository of the same name;
- adds the real repository URLs to `pyproject.toml`;
- initializes/commits Git if needed;
- creates `codex-config-guard` as a **public** repository;
- pushes the publication candidate;
- adds repository topics;
- reads back repository identity, URL, visibility, and description.

It does **not** create a release tag or activate GitHub Sponsors. Those remain behind post-CI and onboarding gates.

## If `gh` is not installed

Create one empty public repository named `codex-config-guard` in GitHub, then connect/install the GitHub integration for that repository. Once the repository is visible to ChatGPT, routine file publication and maintenance can continue through the connector without repeating this setup step.

## Current repository

The repository has been created at `https://github.com/kagurazuki/codex-config-guard`. The helper is retained for disaster recovery or reproducible bootstrap documentation; do not rerun `--apply` against an existing repository.
