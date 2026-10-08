from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final, Literal

TaskClass = Literal["routine", "standard", "critical"]
ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]
RoutingPolicy = Literal["balanced", "astra-high-temporary"]


@dataclass(frozen=True)
class ModelRoute:
    model: str
    reasoning_effort: ReasoningEffort
    task_class: TaskClass

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


EFFORT_ORDER: Final[dict[str, int]] = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "xhigh": 4,
    "max": 5,
}

MODEL_CAPABILITY_ORDER: Final[dict[str, int]] = {
    "gpt-6-luna": 1,
    "gpt-6.1-sol": 2,
    "gpt-6-astra": 3,
}

MODEL_MIN_EFFORT: Final[dict[str, ReasoningEffort]] = {
    "gpt-6-luna": "max",
    "gpt-6.1-sol": "high",
    "gpt-6-astra": "high",
}

# Temporary usage-spend preference. Roll back to the prior behavior by changing
# only this selector to "balanced". The complete balanced policy remains below.
ACTIVE_ROUTE_POLICY: Final[RoutingPolicy] = "astra-high-temporary"

BALANCED_TASK_MIN_MODEL: Final[dict[TaskClass, str]] = {
    "routine": "gpt-6-luna",
    "standard": "gpt-6.1-sol",
    "critical": "gpt-6-astra",
}

ASTRA_HIGH_TASK_MIN_MODEL: Final[dict[TaskClass, str]] = {
    "routine": "gpt-6-astra",
    "standard": "gpt-6-astra",
    "critical": "gpt-6-astra",
}

TASK_MIN_MODEL_BY_POLICY: Final[dict[RoutingPolicy, dict[TaskClass, str]]] = {
    "balanced": BALANCED_TASK_MIN_MODEL,
    "astra-high-temporary": ASTRA_HIGH_TASK_MIN_MODEL,
}

BALANCED_DEFAULT_ROUTES: Final[dict[TaskClass, ModelRoute]] = {
    "routine": ModelRoute("gpt-6-luna", "max", "routine"),
    "standard": ModelRoute("gpt-6.1-sol", "high", "standard"),
    "critical": ModelRoute("gpt-6-astra", "high", "critical"),
}

ASTRA_HIGH_DEFAULT_ROUTES: Final[dict[TaskClass, ModelRoute]] = {
    "routine": ModelRoute("gpt-6-astra", "high", "routine"),
    "standard": ModelRoute("gpt-6-astra", "high", "standard"),
    "critical": ModelRoute("gpt-6-astra", "high", "critical"),
}

DEFAULT_ROUTES_BY_POLICY: Final[dict[RoutingPolicy, dict[TaskClass, ModelRoute]]] = {
    "balanced": BALANCED_DEFAULT_ROUTES,
    "astra-high-temporary": ASTRA_HIGH_DEFAULT_ROUTES,
}

# Keep these public compatibility names bound to the active policy.
TASK_MIN_MODEL: Final[dict[TaskClass, str]] = TASK_MIN_MODEL_BY_POLICY[ACTIVE_ROUTE_POLICY]
DEFAULT_ROUTES: Final[dict[TaskClass, ModelRoute]] = DEFAULT_ROUTES_BY_POLICY[ACTIVE_ROUTE_POLICY]


def select_route(task_class: TaskClass) -> ModelRoute:
    """Return the deterministic default route for a V2 task class."""
    try:
        return DEFAULT_ROUTES[task_class]
    except KeyError as exc:
        raise ValueError(f"unsupported task class: {task_class!r}") from exc


def validate_route(task_class: TaskClass, model: str, reasoning_effort: str) -> ModelRoute:
    """Validate that a proposed route meets the active policy floors.

    The active policy may raise a task's model floor above the balanced baseline.
    Capability upgrades remain allowed, but silent downgrades below the active task
    floor or below the chosen model's reasoning floor are rejected.
    """
    if task_class not in TASK_MIN_MODEL:
        raise ValueError(f"unsupported task class: {task_class!r}")
    if model not in MODEL_CAPABILITY_ORDER:
        raise ValueError(f"unsupported model: {model!r}")
    if reasoning_effort not in EFFORT_ORDER:
        raise ValueError(f"unsupported reasoning effort: {reasoning_effort!r}")

    minimum_model = TASK_MIN_MODEL[task_class]
    if MODEL_CAPABILITY_ORDER[model] < MODEL_CAPABILITY_ORDER[minimum_model]:
        raise ValueError(
            f"route below model floor for {task_class}: {model} < {minimum_model}"
        )

    minimum_effort = MODEL_MIN_EFFORT[model]
    if EFFORT_ORDER[reasoning_effort] < EFFORT_ORDER[minimum_effort]:
        raise ValueError(
            f"route below reasoning floor for {model}: "
            f"{reasoning_effort} < {minimum_effort}"
        )

    return ModelRoute(model, reasoning_effort, task_class)
