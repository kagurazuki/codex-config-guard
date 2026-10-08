from __future__ import annotations

import json
import os
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

from .gdl_v2_router import ModelRoute, TaskClass, select_route, validate_route

AGENTS_API_SESSIONS_URL = "https://api.openai.com/v1/agents/sessions"
CONNECTIVITY_INPUT = (
    "This is a non-destructive GDL V2 connectivity canary. "
    "Do not access or modify repositories or external systems. "
    "Return exactly: GDL_V2_CONNECTIVITY_OK"
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
