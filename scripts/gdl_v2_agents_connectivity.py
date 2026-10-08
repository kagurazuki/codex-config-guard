from __future__ import annotations

import argparse
import json
import sys

from codex_config_guard.gdl_v2_agents import (
    AGENTS_API_SESSIONS_URL,
    build_connectivity_payload,
    require_api_key,
    run_connectivity_canary,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or explicitly run the GDL V2 Agents API connectivity canary."
    )
    parser.add_argument(
        "--task-class",
        choices=("routine", "standard", "critical"),
        default="routine",
    )
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Actually stream and verify one Agents API root turn. "
            "Without this flag the command is dry-run only."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_connectivity_payload(
            args.task_class,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        if not args.live:
            print(
                json.dumps(
                    {
                        "mode": "dry-run",
                        "endpoint": AGENTS_API_SESSIONS_URL,
                        "required_key_permissions": [
                            "api.agents.read",
                            "api.agents.write",
                            "api.responses.write",
                        ],
                        "payload": payload,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        api_key = require_api_key()
        result = run_connectivity_canary(payload, api_key)
        print(json.dumps({"mode": "live", **result}, indent=2, sort_keys=True))
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
