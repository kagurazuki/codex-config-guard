"""Bounded V2 candidate contracts and read-only GitHub trigger validation."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .gdl_v2_agents import resolve_route
from .gdl_v2_router import ModelRoute, TaskClass

SCHEMA_VERSION = 1
CONTRACT_PATH = ".gdl/work-unit.json"
MAX_CONTRACT_BYTES = 32768
TEST_PROFILES = MappingProxyType({"unit": ("python", "-m", "unittest", "discover", "-s", "tests", "-v")})
_WORK_UNIT = re.compile(r"[a-z0-9][a-z0-9-]{2,63}")
_SHA = re.compile(r"[0-9a-f]{40}")
_COMPONENT = re.compile(r"[A-Za-z0-9_.][A-Za-z0-9_.-]{0,63}")
_KEYS = {
    "schema_version", "work_unit", "issue_number", "task_class", "source_sha",
    "summary", "instructions", "allowed_paths", "max_changed_files", "test_profile",
}


def strict_json(text: str, *, limit: int = MAX_CONTRACT_BYTES) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("invalid JSON constant")

    try:
        if len(text.encode("utf-8")) > limit:
            raise ValueError("JSON exceeds size bound")
        return json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON") from exc


def valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA.fullmatch(value)) and value != "0" * 40


def validate_path(value: Any, *, scope: bool = False) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 240:
        raise ValueError("invalid path size")
    path = value[:-1] if scope and value.endswith("/") else value
    parts = path.split("/")
    if any(
        not _COMPONENT.fullmatch(part) or part in {".", ".."}
        or part.lower() == ".git" or part.endswith(".")
        for part in parts
    ):
        raise ValueError("path must be bounded, relative, and free of traversal or .git")
    return value


def _text(value: Any, name: str, limit: int, *, multiline: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid {name}")
    try:
        oversized = len(value.encode("utf-8")) > limit
    except UnicodeError as exc:
        raise ValueError(f"invalid {name}") from exc
    allowed_controls = "\n\t" if multiline else ""
    if oversized or any((ord(c) < 32 and c not in allowed_controls) or ord(c) == 127 for c in value):
        raise ValueError(f"unsafe or oversized {name}")
    return value


@dataclass(frozen=True)
class WorkUnitContract:
    schema_version: int
    work_unit: str
    issue_number: int
    task_class: TaskClass
    source_sha: str
    summary: str
    instructions: str
    allowed_paths: tuple[str, ...]
    max_changed_files: int
    test_profile: str
    route: ModelRoute

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["allowed_paths"] = list(self.allowed_paths)
        data["route"] = {"model": self.route.model, "reasoning_effort": self.route.reasoning_effort}
        return data

    @property
    def sha256(self) -> str:
        canonical = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def allows(self, path: str) -> bool:
        validate_path(path)
        return any(path.startswith(scope) if scope.endswith("/") else path == scope for scope in self.allowed_paths)


def validate_contract_data(data: Any) -> WorkUnitContract:
    if not isinstance(data, Mapping) or set(data) not in (_KEYS, _KEYS | {"route"}):
        raise ValueError("contract keys mismatch")
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("invalid schema_version")
    work_unit = data["work_unit"]
    if not isinstance(work_unit, str) or not _WORK_UNIT.fullmatch(work_unit) or work_unit.endswith("-") or "--" in work_unit:
        raise ValueError("invalid work_unit")
    if type(data["issue_number"]) is not int or not 1 <= data["issue_number"] <= 2147483647:
        raise ValueError("invalid issue_number")
    task_class = data["task_class"]
    if not isinstance(task_class, str) or task_class not in {"routine", "standard", "critical"}:
        raise ValueError("invalid task_class")
    if not valid_sha(data["source_sha"]):
        raise ValueError("invalid source_sha")
    summary = _text(data["summary"], "summary", 240)
    instructions = _text(data["instructions"], "instructions", 12000, multiline=True)
    scopes = data["allowed_paths"]
    if not isinstance(scopes, list) or not 1 <= len(scopes) <= 32:
        raise ValueError("allowed_paths must contain 1..32 bounded scopes")
    for scope in scopes:
        validate_path(scope, scope=True)
    if len(set(scopes)) != len(scopes):
        raise ValueError("duplicate allowed_paths")
    for directory in scopes:
        if directory.endswith("/") and any(
            scope != directory and scope.startswith(directory) for scope in scopes
        ):
            raise ValueError("overlapping allowed_paths")
    if type(data["max_changed_files"]) is not int or not 1 <= data["max_changed_files"] <= 64:
        raise ValueError("invalid max_changed_files")
    profile = data["test_profile"]
    if not isinstance(profile, str) or profile not in TEST_PROFILES:
        raise ValueError("invalid test_profile")
    route_data = data.get("route")
    if "route" in data:
        if not isinstance(route_data, dict) or set(route_data) != {"model", "reasoning_effort"}:
            raise ValueError("invalid route request")
        if any(not isinstance(v, str) for v in route_data.values()):
            raise ValueError("invalid route request")
        route = resolve_route(task_class, **route_data)
    else:
        route = resolve_route(task_class)
    contract = WorkUnitContract(
        SCHEMA_VERSION, work_unit, data["issue_number"], task_class, data["source_sha"],
        summary, instructions, tuple(scopes), data["max_changed_files"], profile, route,
    )
    if len(json.dumps(contract.as_dict(), ensure_ascii=False).encode("utf-8")) > MAX_CONTRACT_BYTES:
        raise ValueError("contract exceeds size bound")
    return contract


def load_contract(path: Path) -> WorkUnitContract:
    with path.open("rb") as stream:
        raw = stream.read(MAX_CONTRACT_BYTES + 1)
    try:
        return validate_contract_data(strict_json(raw.decode("utf-8")))
    except UnicodeError as exc:
        raise ValueError("contract must be UTF-8") from exc


def branch_name(work_unit: str) -> str:
    if not isinstance(work_unit, str) or not _WORK_UNIT.fullmatch(work_unit) or work_unit.endswith("-") or "--" in work_unit:
        raise ValueError("invalid work_unit")
    return f"gdl-v2/work/{work_unit}"


def run_marker(work_unit: str) -> str:
    branch_name(work_unit)
    return f"[gdl-v2-run:{work_unit}]"


def validate_trigger(
    contract: WorkUnitContract, branch: str, head_sha: str,
    history: Sequence[tuple[str, str]], *, run_attempt: int = 1,
) -> dict[str, str]:
    contract = validate_contract_data(contract.as_dict())
    if branch != branch_name(contract.work_unit):
        raise ValueError("branch does not match work_unit")
    if type(run_attempt) is not int or run_attempt != 1:
        raise ValueError("reruns require unknown-outcome reconciliation; live retry is blocked")
    if not valid_sha(head_sha) or head_sha == contract.source_sha or not history or history[0][0] != head_sha:
        raise ValueError("history does not match exact head")
    shas = [sha for sha, _ in history]
    if any(not valid_sha(sha) for sha in shas) or len(set(shas)) != len(shas) or contract.source_sha not in shas:
        raise ValueError("history must contain unique commits and exact source SHA")
    marker = run_marker(contract.work_unit)
    if history[0][1].rstrip("\n") != marker:
        raise ValueError("head must contain only the exact work-unit run marker")
    if sum(message.count(marker) for _, message in history) != 1:
        raise ValueError("duplicate work-unit trigger in branch history")
    return {"branch": branch, "head_sha": head_sha, "work_unit": contract.work_unit,
            "run_marker": marker, "contract_sha256": contract.sha256}


def verify_git_trigger(
    contract: WorkUnitContract, repository: Path, *, run_attempt: int = 1,
) -> dict[str, str]:
    """Read complete local history; never fetch or modify GitHub."""
    def git(*args: str) -> str:
        completed = subprocess.run(["git", "-C", str(repository), *args], capture_output=True, check=False)
        if completed.returncode:
            raise ValueError("cannot read trigger checkout")
        return completed.stdout.decode("utf-8")

    if git("rev-parse", "--is-shallow-repository").strip() != "false":
        raise ValueError("full branch history is required")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("trigger checkout must be clean")
    head = git("rev-parse", "HEAD").strip()
    branch = git("symbolic-ref", "--short", "HEAD").strip()
    committed = validate_contract_data(strict_json(git("show", f"{head}:{CONTRACT_PATH}")))
    if committed != contract:
        raise ValueError("contract is not bound to the trigger head")
    fields = git("log", "-z", "--format=%H%x00%B", "HEAD").split("\0")
    if fields[-1] != "" or len(fields) % 2 != 1:
        raise ValueError("invalid history evidence")
    history = list(zip(fields[0:-1:2], fields[1:-1:2]))
    return validate_trigger(contract, branch, head, history, run_attempt=run_attempt)
