from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .gdl_v2_router import ModelRoute, TaskClass
from .gdl_v2_sandbox import (
    EXPECTED_FINAL_OUTPUT,
    PATCH_ARTIFACT_PATH,
    PROJECT_INSTALL_COMMAND,
    REQUIRED_ARTIFACT_PATHS,
    RESULT_ARTIFACT_PATH,
    SOURCE_REPOSITORY,
    TEST_COMMAND,
    fetch_required_artifacts,
    resolve_route,
    run_sandbox_turn,
)

_ALLOWED_CONTRACT_KEYS = {
    "work_unit",
    "task_class",
    "source_sha",
    "changed_path",
    "content",
}
_WORK_UNIT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_PATH_RE = re.compile(r"^docs/[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.txt$")
_CONTENT_RE = re.compile(r"^[A-Z0-9_]{1,200}\n$")
EXPECTED_PHASE = "orchestrated_handoff"


@dataclass(frozen=True)
class HandoffContract:
    work_unit: str
    task_class: TaskClass
    source_sha: str
    changed_path: str
    content: str

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


def validate_contract_data(data: Mapping[str, Any]) -> HandoffContract:
    keys = set(data)
    if keys != _ALLOWED_CONTRACT_KEYS:
        missing = sorted(_ALLOWED_CONTRACT_KEYS - keys)
        extra = sorted(keys - _ALLOWED_CONTRACT_KEYS)
        raise ValueError(f"contract keys mismatch: missing={missing!r} extra={extra!r}")

    work_unit = data["work_unit"]
    task_class = data["task_class"]
    source_sha = data["source_sha"]
    changed_path = data["changed_path"]
    content = data["content"]

    if not isinstance(work_unit, str) or not _WORK_UNIT_RE.fullmatch(work_unit):
        raise ValueError("invalid work_unit")
    if task_class not in {"routine", "standard", "critical"}:
        raise ValueError("invalid task_class")
    if not isinstance(source_sha, str) or not _SHA_RE.fullmatch(source_sha):
        raise ValueError("invalid source_sha")
    if not isinstance(changed_path, str) or not _PATH_RE.fullmatch(changed_path):
        raise ValueError("changed_path must be one safe docs/*.txt path")
    if not isinstance(content, str) or not _CONTENT_RE.fullmatch(content):
        raise ValueError(
            "content must be exactly one uppercase ASCII marker line plus trailing newline"
        )

    return HandoffContract(
        work_unit=work_unit,
        task_class=task_class,
        source_sha=source_sha,
        changed_path=changed_path,
        content=content,
    )


def load_contract(path: Path) -> HandoffContract:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("contract is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("contract root must be an object")
    return validate_contract_data(parsed)


def expected_result(contract: HandoffContract, route: ModelRoute) -> dict[str, Any]:
    return {
        "work_unit": contract.work_unit,
        "task_class": route.task_class,
        "model": route.model,
        "reasoning_effort": route.reasoning_effort,
        "source_sha": contract.source_sha,
        "changed_path": contract.changed_path,
        "content_sha256": contract.content_sha256,
        "test_command": TEST_COMMAND,
        "test_status": "pass",
        "remote_write_attempted": False,
    }


def build_handoff_instruction(contract: HandoffContract, route: ModelRoute) -> str:
    marker = contract.content.rstrip("\n")
    evidence = json.dumps(expected_result(contract, route), sort_keys=True)
    return f"""This is GDL V2 Phase 4, a bounded non-production orchestrated-handoff canary.

Hard boundaries:
- Never use or request credentials.
- Never push, commit, open/update a pull request, release, deploy, or alter remote state.
- Work only inside the OpenAI-hosted sandbox.
- The only intended source-tree change is `{contract.changed_path}`.
- Do not change dependencies, tests, workflow files, configuration, or any other path.
- Finish only after tests and both output artifacts are written and re-read.

Procedure:
1. Clone the public repository `{SOURCE_REPOSITORY}` into `/workspace/repo`.
2. In `/workspace/repo`, verify `git rev-parse HEAD` equals exactly `{contract.source_sha}`. If not, fail without editing.
3. Prepare the cloned project by running exactly `{PROJECT_INSTALL_COMMAND}`. Hosted setup already supplies the build backend and runtime dependency; runtime package-network access is not needed. Treat any nonzero exit as failure.
4. Verify `git status --porcelain` is still clean. If installation changed or created any repository path, fail.
5. Verify `{contract.changed_path}` does not already exist.
6. Create exactly `{contract.changed_path}` containing exactly `{marker}` plus one trailing newline.
7. Run exactly `{TEST_COMMAND}` from `/workspace/repo`; any nonzero exit is failure.
8. Verify `git status --porcelain` shows only the expected new file and no other path.
9. Create `/workspace/outputs`.
10. Produce `{PATCH_ARTIFACT_PATH}` as a valid unified git-style patch adding only `{contract.changed_path}` with the exact content. A `git diff --no-index` command is acceptable; handle its expected exit status 1 without treating the diff itself as failure.
11. Write `{RESULT_ARTIFACT_PATH}` as JSON exactly equal to this object:
{evidence}
12. Re-read both output files and verify they exactly satisfy this contract.
13. Return exactly `{EXPECTED_FINAL_OUTPUT}` and nothing else.

If any required verification fails, do not fabricate PASS evidence and do not return the success marker."""


def build_handoff_payload(
    contract: HandoffContract,
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[dict[str, Any], ModelRoute]:
    route = resolve_route(
        contract.task_class,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    payload = {
        "agent": {
            "model": route.model,
            "instructions": (
                "Execute the bounded handoff canary exactly. Prefer direct shell evidence "
                "over assumptions. Do not use credentials or mutate remote systems."
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
        "input": build_handoff_instruction(contract, route),
        "metadata": {
            "gdl_version": "v2",
            "canary_phase": EXPECTED_PHASE,
            "work_unit": contract.work_unit,
            "task_class": route.task_class,
            "source_sha": contract.source_sha,
        },
    }
    return payload, route


def run_handoff_turn(
    contract: HandoffContract,
    api_key: str,
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[dict[str, Any], ModelRoute]:
    payload, route = build_handoff_payload(
        contract,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    return run_sandbox_turn(payload, api_key), route


def validate_patch_text(contract: HandoffContract, text: str) -> None:
    diff_headers = [line for line in text.splitlines() if line.startswith("diff --git ")]
    expected_header = (
        f"diff --git a/{contract.changed_path} b/{contract.changed_path}"
    )
    if diff_headers != [expected_header]:
        raise ValueError(f"patch changed unexpected paths: {diff_headers!r}")
    if f"+++ b/{contract.changed_path}" not in text:
        raise ValueError("patch is missing the expected destination path")

    marker = contract.content.rstrip("\n")
    added_payload_lines = [
        line
        for line in text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    if added_payload_lines != [f"+{marker}"]:
        raise ValueError(f"patch has unexpected added content: {added_payload_lines!r}")


def validate_result_text(
    contract: HandoffContract,
    route: ModelRoute,
    text: str,
) -> dict[str, Any]:
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("result artifact is not valid JSON") from exc
    expected = expected_result(contract, route)
    if result != expected:
        raise ValueError(f"result artifact did not match contract: {result!r}")
    return result


def validate_downloaded_artifacts(
    contract: HandoffContract,
    route: ModelRoute,
    saved: Mapping[str, Path],
) -> dict[str, Any]:
    patch_path = saved.get(PATCH_ARTIFACT_PATH)
    result_path = saved.get(RESULT_ARTIFACT_PATH)
    if patch_path is None or result_path is None:
        raise ValueError("downloaded artifact map is incomplete")

    validate_patch_text(contract, patch_path.read_text(encoding="utf-8"))
    result = validate_result_text(
        contract,
        route,
        result_path.read_text(encoding="utf-8"),
    )
    return {
        "patch_verified": True,
        "result_verified": True,
        "work_unit": result["work_unit"],
        "task_class": result["task_class"],
        "model": result["model"],
        "reasoning_effort": result["reasoning_effort"],
        "source_sha": result["source_sha"],
        "changed_path": result["changed_path"],
        "content_sha256": result["content_sha256"],
        "test_status": result["test_status"],
        "remote_write_attempted": result["remote_write_attempted"],
    }


__all__ = [
    "HandoffContract",
    "REQUIRED_ARTIFACT_PATHS",
    "build_handoff_payload",
    "fetch_required_artifacts",
    "load_contract",
    "run_handoff_turn",
    "validate_contract_data",
    "validate_downloaded_artifacts",
    "validate_patch_text",
    "validate_result_text",
]
