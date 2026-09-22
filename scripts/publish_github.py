#!/usr/bin/env python3
"""Bootstrap the public GitHub repository for Codex Config Guard.

Dry-run by default. Pass --apply to perform Git/GitHub mutations.
Requires `git` and GitHub CLI (`gh`) only in apply mode.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Sequence

REPO_NAME = "codex-config-guard"
DESCRIPTION = "Read-only validator and version-aware migration reports for Codex config.toml."
TOPICS = ["openai-codex", "codex", "config", "toml", "validator", "developer-tools", "migration"]


def run(cmd: Sequence[str], *, cwd: pathlib.Path, capture: bool = False) -> str:
    completed = subprocess.run(
        list(cmd),
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return (completed.stdout or "").strip()


def project_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def ensure_project(root: pathlib.Path) -> None:
    required = ["pyproject.toml", "README.md", "LICENSE", "src/codex_config_guard"]
    missing = [name for name in required if not (root / name).exists()]
    if missing:
        raise RuntimeError(f"not a Codex Config Guard project root; missing: {', '.join(missing)}")


def ensure_project_urls(root: pathlib.Path, repo_url: str) -> bool:
    path = root / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    desired = (
        "\n[project.urls]\n"
        f'Homepage = "{repo_url}"\n'
        f'Repository = "{repo_url}"\n'
        f'Issues = "{repo_url}/issues"\n'
    )
    if "[project.urls]" in text:
        # Avoid making a partial/ambiguous TOML edit automatically.
        if repo_url in text:
            return False
        raise RuntimeError("[project.urls] already exists with different values; review manually before publishing")
    path.write_text(text.rstrip() + desired + "\n", encoding="utf-8")
    return True


def git_has_commits(root: pathlib.Path) -> bool:
    try:
        run(["git", "rev-parse", "--verify", "HEAD"], cwd=root, capture=True)
        return True
    except subprocess.CalledProcessError:
        return False


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare and create the Codex Config Guard GitHub repository")
    parser.add_argument("--apply", action="store_true", help="Perform mutations. Without this flag, print a dry-run plan only.")
    parser.add_argument("--owner", help="GitHub login. In apply mode, defaults to the authenticated gh user.")
    parser.add_argument("--repo", default=REPO_NAME)
    args = parser.parse_args(argv)

    root = project_root()
    ensure_project(root)
    owner = args.owner or ("<YOUR_GITHUB_LOGIN>" if not args.apply else "")

    if not args.apply:
        repo_url = f"https://github.com/{owner}/{args.repo}"
        print("DRY RUN: no files, Git state, or GitHub resources will be changed.\n")
        print("Planned publication bootstrap:")
        print(f"1. Set [project.urls] to {repo_url}")
        print("2. Initialize Git locally if needed and commit the publication candidate")
        print(f"3. Create public GitHub repository: {owner}/{args.repo}")
        print("4. Push the initial commit")
        print(f"5. Add topics: {', '.join(TOPICS)}")
        print("6. Read back repository URL, visibility, and description")
        print("\nApply only after GitHub CLI is authenticated: python scripts/publish_github.py --apply")
        return 0

    for binary in ("git", "gh"):
        if not shutil.which(binary):
            print(f"ERROR: required command not found: {binary}", file=sys.stderr)
            return 2

    try:
        run(["gh", "auth", "status"], cwd=root)
        if not owner:
            owner = run(["gh", "api", "user", "--jq", ".login"], cwd=root, capture=True)
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner):
            raise RuntimeError(f"unexpected GitHub login: {owner!r}")

        repo_full = f"{owner}/{args.repo}"
        repo_url = f"https://github.com/{repo_full}"

        # Fail closed if the remote repository already exists. This prevents accidental overwrite/reuse.
        exists = subprocess.run(
            ["gh", "repo", "view", repo_full, "--json", "nameWithOwner"],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if exists:
            raise RuntimeError(f"repository already exists: {repo_full}; inspect it before re-running")

        ensure_project_urls(root, repo_url)

        if not (root / ".git").exists():
            run(["git", "init", "-b", "main"], cwd=root)
        run(["git", "add", "."], cwd=root)
        status = run(["git", "status", "--porcelain"], cwd=root, capture=True)
        if status:
            run(["git", "commit", "-m", "Initial public release candidate"], cwd=root)
        elif not git_has_commits(root):
            raise RuntimeError("no files available to create the initial commit")

        run(
            [
                "gh", "repo", "create", repo_full,
                "--public",
                "--description", DESCRIPTION,
                "--source", ".",
                "--remote", "origin",
                "--push",
            ],
            cwd=root,
        )
        edit_cmd = ["gh", "repo", "edit", repo_full]
        for topic in TOPICS:
            edit_cmd.extend(["--add-topic", topic])
        run(edit_cmd, cwd=root)

        readback = run(
            ["gh", "repo", "view", repo_full, "--json", "nameWithOwner,url,visibility,description"],
            cwd=root,
            capture=True,
        )
        print("PUBLICATION_BOOTSTRAP_PASS")
        print(readback)
        print("Next: wait for GitHub Actions CI to pass before tagging a public release.")
        return 0
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
