#!/usr/bin/env python3
"""Dry-run-first GDL V2 Current entry; GitHub write-back belongs to the control plane."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from codex_config_guard.gdl_v2_agents import require_api_key
from codex_config_guard.gdl_v2_production import build_work_unit_payload, validate_downloaded_artifacts
from codex_config_guard.gdl_v2_sandbox import REQUIRED_ARTIFACT_PATHS, fetch_required_artifacts, run_sandbox_turn
from codex_config_guard.gdl_v2_work_unit import branch_name, load_contract, run_marker, verify_git_trigger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare or run one bounded GDL V2 Current work unit.")
    parser.add_argument("contract_file", type=Path)
    parser.add_argument("--repository", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("gdl-v2-work-unit-artifacts"))
    parser.add_argument("--check-trigger", action="store_true", help="Validate exact branch/head/contract and complete trigger history.")
    parser.add_argument("--live", action="store_true", help="Explicitly dispatch one hosted turn; requires OPENAI_API_KEY and a valid trigger.")
    return parser


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dispatched = False
    try:
        contract = load_contract(args.contract_file)
        payload = build_work_unit_payload(contract)
        trigger = None
        if args.check_trigger or args.live:
            trigger = verify_git_trigger(
                contract, args.repository, run_attempt=int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
            )
        if not args.live:
            print(json.dumps({
                "mode": "dry-run", "work_unit": contract.work_unit,
                "branch": branch_name(contract.work_unit), "run_marker": run_marker(contract.work_unit),
                "route": contract.route.as_dict(), "payload": payload, "trigger": trigger,
                "required_artifacts": list(REQUIRED_ARTIFACT_PATHS),
            }, indent=2, sort_keys=True))
            return 0

        api_key = require_api_key()  # Caller process only; never part of payload.
        args.output_dir.mkdir(parents=True, exist_ok=True)
        receipt = {"status": "dispatch_pending", **trigger}
        # Durable local fence precedes the request. Do not retry a timed-out POST.
        receipt_path = args.output_dir / "dispatch.json"
        try:
            with receipt_path.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        except FileExistsError as exc:
            raise ValueError("dispatch receipt already exists; reconcile the original branch/head/session") from exc
        dispatched = True
        turn = run_sandbox_turn(payload, api_key)
        receipt.update(status="turn_completed", **turn)
        _write_json(receipt_path, receipt)  # Preserve session/turn before downloads.
        saved = fetch_required_artifacts(turn["session_id"], turn["turn_id"], api_key, args.output_dir)
        validation = validate_downloaded_artifacts(contract, saved)
        receipt.update(status="artifacts_verified", **validation)
        _write_json(receipt_path, receipt)
        print(json.dumps({"mode": "live", **receipt, "artifacts": {k: str(v) for k, v in sorted(saved.items())}}, indent=2, sort_keys=True))
        return 0
    except (RuntimeError, ValueError, OSError) as exc:
        # Remote error bodies are not trusted to be secret-free.
        message = "live outcome unverified; preserve dispatch.json and reconcile branch/head + Agents session/turn; do not retry" if dispatched else str(exc)
        print(f"error: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
