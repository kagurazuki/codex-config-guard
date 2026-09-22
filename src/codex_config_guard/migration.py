from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from .checks import RENAMED_KEYS, schema_findings
from .model import Finding
from .schema_io import feature_properties, top_level_properties

CODEX_REPO = "openai/codex"
CODEX_SCHEMA_PATH = "codex-rs/core/config.schema.json"
RAW_GITHUB_BASE = "https://raw.githubusercontent.com"
_RELEASE_RE = re.compile(r"^rust-v(?P<version>\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)$")
_SEMVER_RE = re.compile(r"^v?(?P<version>\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)$")


def normalize_release_ref(value: str) -> str:
    """Normalize a Codex release version to the tag format used by openai/codex.

    Exact git refs such as ``main`` or commit SHAs are also accepted so callers can
    inspect unreleased changes, but those refs are classified as version-ambiguous.
    """

    value = value.strip()
    if not value:
        raise ValueError("release/version must not be empty")

    if _RELEASE_RE.fullmatch(value):
        return value

    match = _SEMVER_RE.fullmatch(value)
    if match:
        return f"rust-v{match.group('version')}"

    # Allow an explicit Git ref (branch/tag/SHA) without pretending it is a release.
    if any(ch.isspace() for ch in value):
        raise ValueError(f"invalid git ref: {value!r}")
    return value


def schema_url_for_ref(ref_or_version: str) -> str:
    ref = normalize_release_ref(ref_or_version)
    safe_ref = quote(ref, safe="._-/+")
    return f"{RAW_GITHUB_BASE}/{CODEX_REPO}/{safe_ref}/{CODEX_SCHEMA_PATH}"


def evidence_status_for_ref(ref_or_version: str) -> str:
    ref = normalize_release_ref(ref_or_version)
    return "verified" if _RELEASE_RE.fullmatch(ref) else "version-ambiguous"


def schema_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_root = top_level_properties(old)
    new_root = top_level_properties(new)
    old_features = feature_properties(old)
    new_features = feature_properties(new)
    return {
        "root": {
            "added": sorted(new_root - old_root),
            "removed": sorted(old_root - new_root),
        },
        "features": {
            "added": sorted(new_features - old_features),
            "removed": sorted(old_features - new_features),
        },
    }


def _configured_feature_keys(config: dict[str, Any]) -> set[str]:
    features = config.get("features")
    return set(features) if isinstance(features, dict) else set()


def _impact_finding(
    *,
    rule_id: str,
    severity: str,
    path: str,
    message: str,
    suggestion: str | None,
    evidence_status: str,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "path": path,
        "message": message,
        "suggestion": suggestion,
        "evidence_status": evidence_status,
    }


def build_migration_report(
    *,
    from_input: str,
    to_input: str,
    old_schema: dict[str, Any],
    new_schema: dict[str, Any],
    config: dict[str, Any] | None = None,
    from_source: str | None = None,
    to_source: str | None = None,
) -> dict[str, Any]:
    from_ref = normalize_release_ref(from_input)
    to_ref = normalize_release_ref(to_input)
    evidence_status = (
        "verified"
        if evidence_status_for_ref(from_ref) == evidence_status_for_ref(to_ref) == "verified"
        else "version-ambiguous"
    )

    diff = schema_diff(old_schema, new_schema)
    impacts: list[dict[str, Any]] = []
    target_validation: list[dict[str, Any]] = []

    if config is not None:
        configured_root = set(config)
        configured_features = _configured_feature_keys(config)

        for key in sorted(configured_root.intersection(diff["root"]["removed"])):
            impacts.append(
                _impact_finding(
                    rule_id="CG401",
                    severity="error",
                    path=f"$.{key}",
                    message=f"Configured root key '{key}' exists in the source schema but is absent from the target schema.",
                    suggestion="Review the target release schema/release notes before upgrading; do not delete automatically.",
                    evidence_status=evidence_status,
                )
            )

        for key in sorted(configured_features.intersection(diff["features"]["removed"])):
            impacts.append(
                _impact_finding(
                    rule_id="CG402",
                    severity="warning",
                    path=f"$.features.{key}",
                    message=f"Configured feature key '{key}' exists in the source schema but is absent from the target schema.",
                    suggestion="Verify whether the feature was removed, renamed, promoted, or replaced in the target release.",
                    evidence_status=evidence_status,
                )
            )

        for old_key, new_key in sorted(RENAMED_KEYS.items()):
            if old_key in config:
                impacts.append(
                    _impact_finding(
                        rule_id="CG403",
                        severity="warning",
                        path=f"$.{old_key}",
                        message=f"Legacy/renamed key '{old_key}' is present; '{new_key}' is the current migration hint.",
                        suggestion="Treat this as a docs-only hint and verify against the exact target release before editing.",
                        evidence_status="docs-only",
                    )
                )

        target_validation = [
            {**finding.to_dict(), "evidence_status": evidence_status}
            for finding in schema_findings(config, new_schema)
        ]

    return {
        "report_version": 1,
        "from": {
            "input": from_input,
            "ref": from_ref,
            "source": from_source or schema_url_for_ref(from_ref),
            "evidence_status": evidence_status_for_ref(from_ref),
        },
        "to": {
            "input": to_input,
            "ref": to_ref,
            "source": to_source or schema_url_for_ref(to_ref),
            "evidence_status": evidence_status_for_ref(to_ref),
        },
        "change_evidence_status": evidence_status,
        "changes": diff,
        "config_impacts": impacts,
        "target_validation": target_validation,
        "sanitization": {
            "config_values_included": False,
            "note": "Markdown support reports include key paths and rule IDs only; config values are never rendered.",
        },
    }


def _render_list(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "(none)"


def render_markdown_report(report: dict[str, Any]) -> str:
    """Render a support-safe report that never includes config values."""

    lines = [
        "# Codex Config Guard migration report",
        "",
        f"- From: `{report['from']['ref']}` ({report['from']['evidence_status']})",
        f"- To: `{report['to']['ref']}` ({report['to']['evidence_status']})",
        f"- Change evidence: **{report['change_evidence_status']}**",
        "- Sanitized: config values are omitted",
        "",
        "## Schema changes",
        "",
        f"- Root keys added: {_render_list(report['changes']['root']['added'])}",
        f"- Root keys removed: {_render_list(report['changes']['root']['removed'])}",
        f"- Feature keys added: {_render_list(report['changes']['features']['added'])}",
        f"- Feature keys removed: {_render_list(report['changes']['features']['removed'])}",
        "",
        "## Config impact",
        "",
    ]

    impacts = report.get("config_impacts", [])
    if impacts:
        for item in impacts:
            suggestion = item.get("suggestion") or "Review before upgrade."
            lines.append(
                f"- **{item['severity'].upper()} {item['rule_id']}** `{item['path']}` "
                f"[{item['evidence_status']}]: {item['message']} {suggestion}"
            )
    else:
        lines.append("- No configured removed/legacy keys were identified by the supported checks.")

    lines.extend(["", "## Target schema validation", ""])
    validation = report.get("target_validation", [])
    if validation:
        for item in validation:
            # Deliberately avoid item['message']; jsonschema messages may echo values.
            lines.append(
                f"- **{item['severity'].upper()} {item['rule_id']}** `{item['path']}` "
                f"[{item['evidence_status']}]: target schema validation failed at this path."
            )
    else:
        lines.append("- No target-schema validation findings.")

    lines.extend(
        [
            "",
            "## Evidence sources",
            "",
            f"- Source schema: {report['from']['source']}",
            f"- Target schema: {report['to']['source']}",
            "",
            "> This report is read-only. It does not modify `config.toml` and does not claim that a removed key is safe to delete without release-specific review.",
        ]
    )
    return "\n".join(lines) + "\n"


def findings_from_report(report: dict[str, Any]) -> list[Finding]:
    """Convert migration impacts to Finding objects for callers that need them."""

    findings: list[Finding] = []
    for item in report.get("config_impacts", []):
        findings.append(
            Finding(
                rule_id=item["rule_id"],
                severity=item["severity"],
                path=item["path"],
                message=item["message"],
                suggestion=item.get("suggestion"),
            )
        )
    return findings
