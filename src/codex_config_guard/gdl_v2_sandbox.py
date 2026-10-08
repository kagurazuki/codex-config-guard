from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import quote
from urllib.request import Request, urlopen

from .gdl_v2_agents import (
    _failure_message,
    _iter_sse_events,
    _session_id_from_event,
)
from .gdl_v2_router import ModelRoute, TaskClass, select_route, validate_route

AGENTS_API_SESSIONS_URL = "https://api.openai.com/v1/agents/sessions"
SOURCE_REPOSITORY = "https://github.com/kagurazuki/codex-config-guard.git"
SOURCE_SHA = "b6d18dffcfad5016f2f21ee760372a2cf0ab2bdc"
CANARY_PATH = "docs/gdl-v2-managed-agent-canary.txt"
CANARY_MARKER = "GDL_V2_MANAGED_AGENT_CANARY"
EXPECTED_FINAL_OUTPUT = "GDL_V2_SANDBOX_OK"
PATCH_ARTIFACT_PATH = "/workspace/outputs/change.patch"
RESULT_ARTIFACT_PATH = "/workspace/outputs/result.json"
REQUIRED_ARTIFACT_PATHS = (PATCH_ARTIFACT_PATH, RESULT_ARTIFACT_PATH)
PROJECT_INSTALL_COMMAND = "python -m pip install . --no-build-isolation --no-deps"
TEST_COMMAND = "python -m unittest discover -s tests -v"


def resolve_route(
    task_class: TaskClass,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> ModelRoute:
    if model is None and reasoning_effort is None:
        return select_route(task_class)
    if model is None or reasoning_effort is None:
        raise ValueError("model and reasoning_effort must be supplied together")
    return validate_route(task_class, model, reasoning_effort)


def build_sandbox_instruction() -> str:
    return f"""This is GDL V2 Phase 2, a bounded non-production canary.

Hard boundaries:
- Never use or request credentials.
- Never push, commit, open/update a pull request, release, deploy, or alter any remote state.
- Work only inside the OpenAI-hosted sandbox.
- The only intended source-tree change is `{CANARY_PATH}`.
- Finish only after tests and output artifacts are written.

Procedure:
1. Clone the public repository `{SOURCE_REPOSITORY}` into `/workspace/repo`.
2. In `/workspace/repo`, verify `git rev-parse HEAD` equals exactly `{SOURCE_SHA}`. If it does not, fail without editing.
3. Prepare the cloned project for its existing tests by running exactly `{PROJECT_INSTALL_COMMAND}`. Hosted setup already supplies the build backend and runtime dependency, so this command must not need runtime package-network access. Treat any nonzero exit as failure.
4. Verify `git status --porcelain` is still clean after installation. If installation changed or created any repo path, fail without continuing.
5. Create exactly `{CANARY_PATH}` containing exactly `{CANARY_MARKER}` plus one trailing newline.
6. Run exactly `{TEST_COMMAND}` from `/workspace/repo`. Treat any nonzero exit as failure.
7. Verify `git status --porcelain` shows only the expected new file and no other changed/untracked path.
8. Create `/workspace/outputs`.
9. Produce `{PATCH_ARTIFACT_PATH}` as a valid unified git-style patch that adds only `{CANARY_PATH}` with the exact marker content. A `git diff --no-index` command is acceptable; handle its expected exit status 1 without treating the diff itself as failure.
10. Write `{RESULT_ARTIFACT_PATH}` as JSON with exactly these evidence fields:
   - `source_sha`: `{SOURCE_SHA}`
   - `changed_path`: `{CANARY_PATH}`
   - `marker`: `{CANARY_MARKER}`
   - `test_command`: `{TEST_COMMAND}`
   - `test_status`: `pass`
   - `remote_write_attempted`: false
11. Re-read both output files and verify they match this contract.
12. Return exactly `{EXPECTED_FINAL_OUTPUT}` and nothing else.

If any required verification fails, do not fabricate PASS evidence and do not return the success marker."""


def build_sandbox_payload(
    task_class: TaskClass = "routine",
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    route = resolve_route(task_class, model, reasoning_effort)
    return {
        "agent": {
            "model": route.model,
            "instructions": (
                "Execute the bounded canary exactly. Prefer direct shell evidence over "
                "assumptions. Do not use credentials or mutate remote systems."
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
        "input": build_sandbox_instruction(),
        "metadata": {
            "gdl_version": "v2",
            "canary_phase": "sandbox_patch_artifact",
            "task_class": route.task_class,
            "source_sha": SOURCE_SHA,
        },
    }


def _final_output_text(
    completed_parts: Mapping[tuple[int, str], Mapping[int, str]],
) -> str:
    """Reconstruct the final saved text item from completed stream parts.

    Agents can emit multiple message items while they work. `output_index` orders those
    saved items and `content_index` orders text parts inside an item, so progress text
    must not be concatenated into the final response.
    """
    if not completed_parts:
        return ""
    highest_output_index = max(output_index for output_index, _ in completed_parts)
    candidates = [
        (item_id, parts)
        for (output_index, item_id), parts in completed_parts.items()
        if output_index == highest_output_index
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            "sandbox stream had ambiguous final output items at output_index "
            f"{highest_output_index}"
        )
    _, parts = candidates[0]
    return "".join(parts[index] for index in sorted(parts)).strip()


def run_sandbox_turn(
    payload: Mapping[str, Any],
    api_key: str,
    *,
    endpoint: str = AGENTS_API_SESSIONS_URL,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 300.0,
) -> dict[str, Any]:
    streamed_payload = dict(payload)
    streamed_payload["stream"] = True
    request = Request(
        endpoint,
        data=json.dumps(streamed_payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "OpenAI-Beta": "agents=v1",
        },
    )

    session_id: str | None = None
    root_turn_id: str | None = None
    completed_parts: dict[tuple[int, str], dict[int, str]] = {}
    completed = False

    with opener(request, timeout=timeout) as response:
        for event in _iter_sse_events(response):
            event_type = event.get("type")
            if event_type == "agent.session.created":
                session_id = session_id or _session_id_from_event(event)
                continue
            if event_type == "agent.session.turn.output_text.done":
                text = event.get("text")
                item_id = event.get("item_id")
                output_index = event.get("output_index")
                content_index = event.get("content_index")
                if not isinstance(text, str):
                    continue
                if not isinstance(item_id, str) or not item_id:
                    raise RuntimeError("sandbox output_text.done event had no item_id")
                if not isinstance(output_index, int) or not isinstance(content_index, int):
                    raise RuntimeError(
                        "sandbox output_text.done event had invalid output/content index"
                    )
                completed_parts.setdefault((output_index, item_id), {})[
                    content_index
                ] = text
                continue
            if event_type in {
                "agent.session.requires_action",
                "agent.session.action_required",
            }:
                raise RuntimeError("sandbox canary unexpectedly requires external action")
            if event_type in {
                "error",
                "agent.session.failed",
                "agent.session.environment.failed",
            }:
                raise RuntimeError(f"sandbox canary failed: {_failure_message(event)}")
            if event_type in {
                "agent.session.turn.failed",
                "agent.session.turn.cancelled",
            }:
                turn = event.get("turn")
                if isinstance(turn, Mapping) and turn.get("subagent_id") is not None:
                    continue
                raise RuntimeError(
                    f"sandbox root turn ended unsuccessfully: {_failure_message(event)}"
                )
            if event_type == "agent.session.turn.completed":
                turn = event.get("turn")
                if isinstance(turn, Mapping) and turn.get("subagent_id") is not None:
                    continue
                if isinstance(turn, Mapping):
                    value = turn.get("id")
                    if isinstance(value, str) and value:
                        root_turn_id = value
                completed = True
                break

    if not completed:
        raise RuntimeError("Agents API stream closed before the sandbox root turn completed")
    if not session_id:
        raise RuntimeError("sandbox turn completed without a session identity")
    if not root_turn_id:
        raise RuntimeError("sandbox turn completed without a root turn identity")

    output_text = _final_output_text(completed_parts)
    if output_text != EXPECTED_FINAL_OUTPUT:
        raise RuntimeError(
            f"sandbox final output mismatch: expected {EXPECTED_FINAL_OUTPUT!r}, "
            f"got {output_text!r}"
        )
    return {
        "session_id": session_id,
        "turn_id": root_turn_id,
        "turn_status": "completed",
        "output_text": output_text,
    }


def _api_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "agents=v1",
    }


def list_session_artifacts(
    session_id: str,
    api_key: str,
    *,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 60.0,
) -> list[dict[str, Any]]:
    sid = quote(session_id, safe="")
    request = Request(
        f"https://api.openai.com/v1/agents/sessions/{sid}/artifacts?limit=100",
        method="GET",
        headers=_api_headers(api_key),
    )
    with opener(request, timeout=timeout) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    data = parsed.get("data")
    if not isinstance(data, list):
        raise RuntimeError("artifact list response did not contain a data array")
    return [artifact for artifact in data if isinstance(artifact, dict)]


def download_artifact_content(
    session_id: str,
    artifact_id: str,
    api_key: str,
    *,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 60.0,
) -> bytes:
    sid = quote(session_id, safe="")
    aid = quote(artifact_id, safe="")
    request = Request(
        f"https://api.openai.com/v1/agents/sessions/{sid}/artifacts/{aid}/content",
        method="GET",
        headers=_api_headers(api_key),
    )
    with opener(request, timeout=timeout) as response:
        return response.read()


def fetch_required_artifacts(
    session_id: str,
    turn_id: str,
    api_key: str,
    destination: Path,
    *,
    list_opener: Callable[..., Any] = urlopen,
    content_opener: Callable[..., Any] = urlopen,
) -> dict[str, Path]:
    artifacts = list_session_artifacts(session_id, api_key, opener=list_opener)
    by_path: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        path = artifact.get("path")
        artifact_turn_id = artifact.get("turn_id")
        if (
            isinstance(path, str)
            and isinstance(artifact_turn_id, str)
            and artifact_turn_id == turn_id
        ):
            by_path[path] = artifact

    missing = [path for path in REQUIRED_ARTIFACT_PATHS if path not in by_path]
    if missing:
        raise RuntimeError(f"missing required sandbox artifacts: {missing!r}")

    destination.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Path] = {}
    for artifact_path in REQUIRED_ARTIFACT_PATHS:
        artifact = by_path[artifact_path]
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise RuntimeError(f"artifact {artifact_path!r} has no valid id")
        content = download_artifact_content(
            session_id,
            artifact_id,
            api_key,
            opener=content_opener,
        )
        local_path = destination / Path(artifact_path).name
        local_path.write_bytes(content)
        saved[artifact_path] = local_path
    return saved


def validate_patch_text(text: str) -> None:
    diff_headers = [line for line in text.splitlines() if line.startswith("diff --git ")]
    expected_header = f"diff --git a/{CANARY_PATH} b/{CANARY_PATH}"
    if diff_headers != [expected_header]:
        raise ValueError(f"patch changed unexpected paths: {diff_headers!r}")
    if f"+++ b/{CANARY_PATH}" not in text:
        raise ValueError("patch is missing the expected destination path")
    if f"+{CANARY_MARKER}" not in text:
        raise ValueError("patch is missing the exact canary marker")
    added_payload_lines = [
        line
        for line in text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    if added_payload_lines != [f"+{CANARY_MARKER}"]:
        raise ValueError(f"patch has unexpected added content: {added_payload_lines!r}")


def validate_result_text(text: str) -> dict[str, Any]:
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("result artifact is not valid JSON") from exc
    expected = {
        "source_sha": SOURCE_SHA,
        "changed_path": CANARY_PATH,
        "marker": CANARY_MARKER,
        "test_command": TEST_COMMAND,
        "test_status": "pass",
        "remote_write_attempted": False,
    }
    if result != expected:
        raise ValueError(f"result artifact did not match contract: {result!r}")
    return result


def validate_downloaded_artifacts(saved: Mapping[str, Path]) -> dict[str, Any]:
    patch_path = saved.get(PATCH_ARTIFACT_PATH)
    result_path = saved.get(RESULT_ARTIFACT_PATH)
    if patch_path is None or result_path is None:
        raise ValueError("downloaded artifact map is incomplete")
    validate_patch_text(patch_path.read_text(encoding="utf-8"))
    result = validate_result_text(result_path.read_text(encoding="utf-8"))
    return {
        "patch_verified": True,
        "result_verified": True,
        "source_sha": result["source_sha"],
        "changed_path": result["changed_path"],
        "test_status": result["test_status"],
    }
