from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .checks import compatibility_findings, schema_findings
from .migration import (
    build_migration_report,
    render_markdown_report,
    schema_diff,
    schema_url_for_ref,
)
from .model import Finding
from .schema_io import OFFICIAL_SCHEMA_URL, load_json_source


def _read_toml(path: str) -> dict[str, Any]:
    with Path(path).open("rb") as fh:
        value = tomllib.load(fh)
    if not isinstance(value, dict):
        raise ValueError("TOML root must be a table")
    return value


def _print_findings(findings: list[Finding], as_json: bool) -> None:
    if as_json:
        print(json.dumps({"findings": [f.to_dict() for f in findings]}, ensure_ascii=False, indent=2))
        return

    if not findings:
        print("PASS: no findings")
        return

    for finding in findings:
        print(f"{finding.severity.upper():7} {finding.rule_id} {finding.path}: {finding.message}")
        if finding.suggestion:
            print(f"         suggestion: {finding.suggestion}")


def _should_fail(findings: list[Finding], fail_on: str) -> bool:
    if fail_on == "warning":
        return bool(findings)
    return any(f.severity == "error" for f in findings)


def cmd_check(args: argparse.Namespace) -> int:
    try:
        config = _read_toml(args.config)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        finding = Finding("CG001", "error", f"Could not parse TOML: {exc}")
        _print_findings([finding], args.json)
        return 2

    findings = compatibility_findings(config, args.scope)

    if not args.no_schema:
        try:
            schema = load_json_source(args.schema, timeout=args.timeout)
            findings.extend(schema_findings(config, schema))
        except Exception as exc:  # noqa: BLE001 - CLI boundary
            findings.append(
                Finding(
                    "CG301",
                    "error" if args.require_schema else "warning",
                    f"Could not load/validate against schema: {exc}",
                    suggestion="Use --schema PATH for an offline schema, or --no-schema for compatibility-only checks.",
                )
            )

    findings.sort(key=lambda f: (0 if f.severity == "error" else 1, f.rule_id, f.path))
    _print_findings(findings, args.json)
    return 1 if _should_fail(findings, args.fail_on) else 0


def _schema_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    # Kept as a compatibility shim for callers/tests from v0.1.
    return schema_diff(old, new)


def cmd_diff_schema(args: argparse.Namespace) -> int:
    try:
        old = load_json_source(args.old, timeout=args.timeout)
        new = load_json_source(args.new, timeout=args.timeout)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"ERROR: could not load schema: {exc}", file=sys.stderr)
        return 2

    diff = schema_diff(old, new)
    if args.json:
        print(json.dumps(diff, ensure_ascii=False, indent=2))
    else:
        print("Root keys added:", ", ".join(diff["root"]["added"]) or "(none)")
        print("Root keys removed:", ", ".join(diff["root"]["removed"]) or "(none)")
        print("Feature keys added:", ", ".join(diff["features"]["added"]) or "(none)")
        print("Feature keys removed:", ", ".join(diff["features"]["removed"]) or "(none)")
    return 0


def cmd_migration_report(args: argparse.Namespace) -> int:
    from_source = args.from_schema or schema_url_for_ref(args.from_version)
    to_source = args.to_schema or schema_url_for_ref(args.to_version)

    try:
        old_schema = load_json_source(from_source, timeout=args.timeout)
        new_schema = load_json_source(to_source, timeout=args.timeout)
        config = _read_toml(args.config) if args.config else None
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"ERROR: could not build migration report: {exc}", file=sys.stderr)
        return 2

    report = build_migration_report(
        from_input=args.from_version,
        to_input=args.to_version,
        old_schema=old_schema,
        new_schema=new_schema,
        config=config,
        from_source=from_source,
        to_source=to_source,
    )

    if args.json:
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    else:
        payload = render_markdown_report(report)

    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"WROTE: {args.output}")
    else:
        print(payload, end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-config-guard",
        description="Unofficial local checks and version-aware migration reports for Codex config.toml.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Validate one config.toml")
    check.add_argument("config")
    check.add_argument("--scope", choices=["user", "project"], default="user")
    check.add_argument("--schema", default=OFFICIAL_SCHEMA_URL)
    check.add_argument("--no-schema", action="store_true")
    check.add_argument("--require-schema", action="store_true", help="Treat schema fetch failure as an error")
    check.add_argument("--fail-on", choices=["error", "warning"], default="error")
    check.add_argument("--timeout", type=float, default=10.0)
    check.add_argument("--json", action="store_true")
    check.set_defaults(func=cmd_check)

    diff = sub.add_parser("diff-schema", help="Compare two Codex JSON schemas")
    diff.add_argument("old", help="Old schema file or URL")
    diff.add_argument("new", help="New schema file or URL")
    diff.add_argument("--timeout", type=float, default=10.0)
    diff.add_argument("--json", action="store_true")
    diff.set_defaults(func=cmd_diff_schema)

    migrate = sub.add_parser("migration-report", help="Create a version-aware upgrade report")
    migrate.add_argument("--from-version", required=True, help="Source Codex version/ref, e.g. 0.135.0")
    migrate.add_argument("--to-version", required=True, help="Target Codex version/ref, e.g. 0.150.0")
    migrate.add_argument("--config", help="Optional config.toml to assess; values are omitted from Markdown output")
    migrate.add_argument("--from-schema", help="Override source schema with a local file/URL")
    migrate.add_argument("--to-schema", help="Override target schema with a local file/URL")
    migrate.add_argument("--output", help="Write report to this path")
    migrate.add_argument("--timeout", type=float, default=10.0)
    migrate.add_argument("--json", action="store_true", help="Emit structured JSON instead of sanitized Markdown")
    migrate.set_defaults(func=cmd_migration_report)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
