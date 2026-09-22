from __future__ import annotations

from typing import Any

from jsonschema import Draft7Validator

from .model import Finding

# Current migration hints verified against current Codex docs/issues at project creation time.
RENAMED_KEYS: dict[str, str] = {
    "ask_for_approval": "approval_policy",
    "sandbox": "sandbox_mode",
    "experimental_instructions_file": "model_instructions_file",
}

# Current docs state these values are ignored when placed in project-local .codex/config.toml.
PROJECT_IGNORED_ROOT_KEYS = {
    "openai_base_url",
    "chatgpt_base_url",
    "apps_mcp_product_sku",
    "model_provider",
    "model_providers",
    "notify",
    "profile",
    "profiles",
    "experimental_realtime_ws_base_url",
    "otel",
}


def _json_path(parts: list[Any]) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


def schema_findings(config: dict[str, Any], schema: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(config), key=lambda e: list(e.absolute_path))
    for error in errors:
        findings.append(
            Finding(
                rule_id="CG101",
                severity="error",
                path=_json_path(list(error.absolute_path)),
                message=error.message,
                suggestion="Compare this key/value with the schema for the Codex version you actually run.",
            )
        )
    return findings


def compatibility_findings(config: dict[str, Any], scope: str) -> list[Finding]:
    findings: list[Finding] = []

    for old, new in RENAMED_KEYS.items():
        if old in config:
            findings.append(
                Finding(
                    rule_id="CG201",
                    severity="warning",
                    path=f"$.{old}",
                    message=f"Legacy/renamed key '{old}' is present.",
                    suggestion=f"Review migration to '{new}' for the Codex version you run.",
                )
            )

    if scope == "project":
        for key in sorted(PROJECT_IGNORED_ROOT_KEYS.intersection(config.keys())):
            findings.append(
                Finding(
                    rule_id="CG202",
                    severity="warning",
                    path=f"$.{key}",
                    message=f"'{key}' is ignored in project-local Codex config according to current documentation.",
                    suggestion="Move this setting to the user-level config if you expect it to take effect.",
                )
            )

    return findings
