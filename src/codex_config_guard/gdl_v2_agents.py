from __future__ import annotations

import json
import os
from typing import Any, Callable, Iterable, Mapping
from urllib.request import Request, urlopen

from .gdl_v2_router import ModelRoute, TaskClass, select_route, validate_route

AGENTS_API_SESSIONS_URL = "https://api.openai.com/v1/agents/sessions"
EXPECTED_CONNECTIVITY_OUTPUT = "GDL_V2_CONNECTIVITY_OK"
CONNECTIVITY_INPUT = (
    "This is a non-destructive GDL V2 connectivity canary. "
    "Do not access or modify repositories or external systems. "
    f"Return exactly: {EXPECTED_CONNECTIVITY_OUTPUT}"
)
CONNECTIVITY_INSTRUCTIONS = (
    "Perform only the requested connectivity check. Do not use tools, do not access "
    "external systems, and do not claim success unless the task completes."
)


def resolve_route(
    task_class: TaskClass,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> ModelRoute:
    """Resolve either the deterministic default or an explicit validated override."""
    if model is None and reasoning_effort is None:
        return select_route(task_class)
    if model is None or reasoning_effort is None:
        raise ValueError("model and reasoning_effort must be supplied together")
    return validate_route(task_class, model, reasoning_effort)


def build_connectivity_payload(
    task_class: TaskClass = "routine",
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    """Build a repository-independent, non-destructive Agents API canary payload."""
    route = resolve_route(task_class, model, reasoning_effort)
    return {
        "agent": {
            "model": route.model,
            "instructions": CONNECTIVITY_INSTRUCTIONS,
            "reasoning": {"effort": route.reasoning_effort},
        },
        "environment": {"type": "none"},
        "input": CONNECTIVITY_INPUT,
        "metadata": {
            "gdl_version": "v2",
            "canary_phase": "agents_connectivity",
            "task_class": route.task_class,
        },
    }


def require_api_key(environ: Mapping[str, str] | None = None) -> str:
    """Fail closed unless the application API key is present outside the payload."""
    source = os.environ if environ is None else environ
    api_key = source.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required for --live. Keep it outside source control."
        )
    return api_key


def create_connectivity_session(
    payload: Mapping[str, Any],
    api_key: str,
    *,
    endpoint: str = AGENTS_API_SESSIONS_URL,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Create one Agents API session and return only non-secret response metadata."""
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "agents=v1",
        },
    )
    with opener(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw)
    return {
        "session_id": parsed.get("id") or parsed.get("session_id"),
        "status": parsed.get("status"),
        "environment_id": (
            parsed.get("environment", {}).get("id")
            if isinstance(parsed.get("environment"), dict)
            else None
        ),
    }


def _iter_sse_events(response: Iterable[bytes | str]) -> Iterable[dict[str, Any]]:
    """Yield JSON events from the Agents API text/event-stream response."""
    for raw_line in response:
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        line = line.strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if not data or data == "[DONE]":
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Agents API returned a malformed SSE event") from exc
        if not isinstance(event, dict):
            raise RuntimeError("Agents API returned a non-object SSE event")
        yield event


def _session_id_from_event(event: Mapping[str, Any]) -> str | None:
    for key in ("session", "data"):
        value = event.get(key)
        if isinstance(value, Mapping):
            session_id = value.get("id")
            if isinstance(session_id, str) and session_id:
                return session_id
    session_id = event.get("session_id")
    return session_id if isinstance(session_id, str) and session_id else None


def _failure_message(event: Mapping[str, Any]) -> str:
    candidates = [event.get("error")]
    for key in ("turn", "session", "environment"):
        value = event.get(key)
        if isinstance(value, Mapping):
            candidates.append(value.get("error"))
    for error in candidates:
        if isinstance(error, Mapping):
            message = error.get("message") or error.get("code") or error.get("type")
            if message:
                return str(message)
    return str(event.get("type", "Agents API failure"))


def run_connectivity_canary(
    payload: Mapping[str, Any],
    api_key: str,
    *,
    endpoint: str = AGENTS_API_SESSIONS_URL,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 120.0,
    expected_output: str = EXPECTED_CONNECTIVITY_OUTPUT,
) -> dict[str, Any]:
    """Run and verify one complete non-destructive root turn over the event stream."""
    streamed_payload = dict(payload)
    streamed_payload["stream"] = True
    body = json.dumps(streamed_payload).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
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
    output_parts: list[str] = []
    completed = False

    with opener(request, timeout=timeout) as response:
        for event in _iter_sse_events(response):
            event_type = event.get("type")

            if event_type == "agent.session.created":
                session_id = session_id or _session_id_from_event(event)
                continue

            if event_type == "agent.session.turn.output_text.done":
                text = event.get("text")
                if isinstance(text, str):
                    output_parts.append(text)
                continue

            if event_type in {
                "agent.session.requires_action",
                "agent.session.action_required",
            }:
                raise RuntimeError(
                    "connectivity canary unexpectedly requires external action"
                )

            if event_type in {
                "error",
                "agent.session.failed",
                "agent.session.environment.failed",
            }:
                raise RuntimeError(
                    f"connectivity canary failed: {_failure_message(event)}"
                )

            if event_type in {
                "agent.session.turn.failed",
                "agent.session.turn.cancelled",
            }:
                turn = event.get("turn")
                if isinstance(turn, Mapping) and turn.get("subagent_id") is not None:
                    continue
                raise RuntimeError(
                    f"connectivity root turn ended unsuccessfully: {_failure_message(event)}"
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
        raise RuntimeError("Agents API stream closed before the root turn completed")
    if not session_id:
        raise RuntimeError("Agents API stream completed without a session identity")

    output_text = "".join(output_parts).strip()
    if output_text != expected_output:
        raise RuntimeError(
            "connectivity output mismatch: "
            f"expected {expected_output!r}, got {output_text!r}"
        )

    return {
        "session_id": session_id,
        "turn_id": root_turn_id,
        "turn_status": "completed",
        "output_text": output_text,
        "verified_output": True,
    }
