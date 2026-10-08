from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codex_config_guard.gdl_v2_agents import require_api_key
from codex_config_guard.gdl_v2_handoff import (
    REQUIRED_ARTIFACT_PATHS,
    build_handoff_payload,
    fetch_required_artifacts,
    load_contract,
    run_handoff_turn,
    validate_downloaded_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or run the GDL V2 Phase 4 orchestrated-handoff canary."
    )
    parser.add_argument("contract_file", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    parser.add_argument(
        "--output-dir",
        default="gdl-v2-orchestrated-artifacts",
        help="Local destination for downloaded published artifacts.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one paid hosted-sandbox turn and verify its published artifacts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        contract = load_contract(args.contract_file)
        payload, route = build_handoff_payload(
            contract,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        if not args.live:
            print(
                json.dumps(
                    {
                        "mode": "dry-run",
                        "work_unit": contract.work_unit,
                        "route": route.as_dict(),
                        "payload": payload,
                        "required_artifacts": list(REQUIRED_ARTIFACT_PATHS),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        api_key = require_api_key()
        turn, route = run_handoff_turn(
            contract,
            api_key,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        saved = fetch_required_artifacts(
            turn["session_id"],
            turn["turn_id"],
            api_key,
            Path(args.output_dir),
        )
        validation = validate_downloaded_artifacts(contract, route, saved)
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
