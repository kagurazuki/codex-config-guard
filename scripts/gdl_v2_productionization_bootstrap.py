from __future__ import annotations

import argparse
import json
from pathlib import Path

from codex_config_guard.gdl_v2_agents import require_api_key
from codex_config_guard.gdl_v2_router import validate_route
from codex_config_guard.gdl_v2_sandbox import (
    EXPECTED_FINAL_OUTPUT,
    SOURCE_REPOSITORY,
    fetch_required_artifacts,
    run_sandbox_turn,
)

SOURCE_SHA = "8adf1f8fbd4a13437657e5e177d8e0defcc8f213"
TASK_FILE = Path("docs/gdl-v2-productionization-bootstrap-task.md")
MODEL = "gpt-6.1-sol"
REASONING = "high"


def build_payload(task_text: str) -> dict[str, object]:
    route = validate_route("standard", MODEL, REASONING)
    instruction = f"""You are implementing GitHub Issue #16 for GDL V2 productionization.

Hard boundaries:
- Never use or request credentials.
- Never push, commit, open/update a pull request, close issues, release, deploy, or alter remote state.
- Work only in the OpenAI-hosted sandbox.
- Clone `{SOURCE_REPOSITORY}` into `/workspace/repo` and verify HEAD is exactly `{SOURCE_SHA}` before editing.
- Runtime network is intentionally restricted to github.com.
- Do not weaken existing model-route guards or safety boundaries.
- Keep GDL v0.2 Current. Do not label V2 Current.
- Bootstrap-only files from the caller branch are not part of the source tree and must not appear in your patch.

Canonical implementation requirements follow:

{task_text}

Execution procedure:
1. Clone the public repository and verify exact source SHA.
2. Install the project with `python -m pip install . --no-build-isolation --no-deps` and require a clean git status afterwards.
3. Implement the complete productionization task with the smallest coherent design that satisfies Issue #16.
4. Run `python -m unittest discover -s tests -v` and require PASS.
5. Inspect `git status --porcelain` and `git diff --check`; reject unrelated or generated-file churn.
6. Create `/workspace/outputs/change.patch` with the complete textual git diff for every intended source-tree change. Include untracked new source files by staging them locally if needed, but do not commit and do not contact any remote.
7. Create `/workspace/outputs/result.json` as valid JSON containing at least:
   - `issue_number`: 16
   - `source_sha`: `{SOURCE_SHA}`
   - `model`: `{route.model}`
   - `reasoning_effort`: `{route.reasoning_effort}`
   - `test_command`: `python -m unittest discover -s tests -v`
   - `test_status`: `pass`
   - `remote_write_attempted`: false
   - `changed_paths`: sorted list of every changed path represented by the patch
8. Re-read the patch/result and verify they match the actual git diff and successful test evidence.
9. Return exactly `{EXPECTED_FINAL_OUTPUT}` and nothing else.

If any verification fails, do not fabricate PASS evidence and do not return the success marker."""
    return {
        "agent": {
            "model": route.model,
            "instructions": (
                "Implement the bounded productionization task exactly. Use direct shell and "
                "test evidence. Do not mutate remote systems or request credentials."
            ),
            "reasoning": {"effort": route.reasoning_effort},
        },
        "environment": {
            "type": "openai_hosted",
            "container_size": "small",
            "network": {
                "access": "restricted",
                "allowed_domains": ["github.com"],
            },
            "packages": {
                "python": ["hatchling>=1.25", "jsonschema>=4.23,<5"],
                "npm": [],
                "system": [],
            },
        },
        "input": instruction,
        "metadata": {
            "gdl_version": "v2",
            "gate": "productionization_bootstrap",
            "issue_number": "16",
            "task_class": "standard",
            "source_sha": SOURCE_SHA,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output-dir", default="gdl-v2-productionization-artifacts")
    args = parser.parse_args()

    task_text = TASK_FILE.read_text(encoding="utf-8")
    payload = build_payload(task_text)
    route = payload["agent"]

    if not args.live:
        print(
            json.dumps(
                {
                    "live": False,
                    "source_sha": SOURCE_SHA,
                    "model": route["model"],
                    "reasoning_effort": route["reasoning"]["effort"],
                    "task_file": str(TASK_FILE),
                },
                sort_keys=True,
            )
        )
        return 0

    api_key = require_api_key()
    run = run_sandbox_turn(payload, api_key, timeout=900.0)
    saved = fetch_required_artifacts(
        run["session_id"],
        run["turn_id"],
        api_key,
        Path(args.output_dir),
    )
    print(
        json.dumps(
            {
                "session_id": run["session_id"],
                "turn_id": run["turn_id"],
                "turn_status": run["turn_status"],
                "output_text": run["output_text"],
                "model": route["model"],
                "reasoning_effort": route["reasoning"]["effort"],
                "artifacts": sorted(str(path) for path in saved.values()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
