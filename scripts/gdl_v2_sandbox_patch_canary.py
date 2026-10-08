from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codex_config_guard.gdl_v2_agents import require_api_key
from codex_config_guard.gdl_v2_sandbox import (
    REQUIRED_ARTIFACT_PATHS,
    build_sandbox_payload,
    fetch_required_artifacts,
    run_sandbox_turn,
    validate_downloaded_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or run the GDL V2 OpenAI-hosted sandbox patch-artifact canary."
    )
    parser.add_argument(
        "--task-class",
        choices=("routine", "standard", "critical"),
        default="routine",
    )
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    parser.add_argument(
        "--output-dir",
        default="gdl-v2-sandbox-artifacts",
        help="Local destination for downloaded published artifacts.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one paid hosted-sandbox canary and verify its published artifacts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_sandbox_payload(
            args.task_class,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        if not args.live:
            print(
                json.dumps(
                    {
                        "mode": "dry-run",
                        "payload": payload,
                        "required_artifacts": list(REQUIRED_ARTIFACT_PATHS),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        api_key = require_api_key()
        turn = run_sandbox_turn(payload, api_key)
        saved = fetch_required_artifacts(
            turn["session_id"],
            turn["turn_id"],
            api_key,
            Path(args.output_dir),
        )
        validation = validate_downloaded_artifacts(saved)
        print(
            json.dumps(
                {
                    "mode": "live",
                    **turn,
                    **validation,
                    "artifacts": {
                        key: str(path) for key, path in sorted(saved.items())
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
