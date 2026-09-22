from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codex_config_guard.checks import compatibility_findings, schema_findings
from codex_config_guard.cli import _schema_diff
from codex_config_guard.migration import (
    build_migration_report,
    evidence_status_for_ref,
    normalize_release_ref,
    render_markdown_report,
    schema_url_for_ref,
)
from codex_config_guard.schema_io import load_json_source


class GuardTests(unittest.TestCase):
    def test_project_scope_and_legacy_key(self) -> None:
        config = {"model_provider": "openai", "ask_for_approval": "never"}
        findings = compatibility_findings(config, "project")
        ids = [f.rule_id for f in findings]
        self.assertIn("CG201", ids)
        self.assertIn("CG202", ids)

    def test_schema_validation_reports_unknown_key(self) -> None:
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {"model": {"type": "string"}},
            "additionalProperties": False,
        }
        findings = schema_findings({"model": "x", "bogus": True}, schema)
        self.assertEqual(1, len(findings))
        self.assertEqual("CG101", findings[0].rule_id)

    def test_schema_diff(self) -> None:
        old = {"properties": {"a": {}, "features": {"properties": {"x": {}}}}}
        new = {"properties": {"b": {}, "features": {"properties": {"y": {}}}}}
        diff = _schema_diff(old, new)
        self.assertEqual(["b"], diff["root"]["added"])
        self.assertEqual(["a"], diff["root"]["removed"])
        self.assertEqual(["y"], diff["features"]["added"])
        self.assertEqual(["x"], diff["features"]["removed"])

    def test_load_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "schema.json"
            path.write_text(json.dumps({"type": "object"}), encoding="utf-8")
            self.assertEqual("object", load_json_source(str(path))["type"])

    def test_release_normalization_and_schema_url(self) -> None:
        self.assertEqual("rust-v0.135.0", normalize_release_ref("0.135.0"))
        self.assertEqual("rust-v0.135.0", normalize_release_ref("v0.135.0"))
        self.assertEqual("rust-v0.135.0", normalize_release_ref("rust-v0.135.0"))
        self.assertEqual("verified", evidence_status_for_ref("0.135.0"))
        self.assertEqual("version-ambiguous", evidence_status_for_ref("main"))
        self.assertEqual(
            "https://raw.githubusercontent.com/openai/codex/rust-v0.135.0/codex-rs/core/config.schema.json",
            schema_url_for_ref("0.135.0"),
        )

    def test_migration_report_detects_removed_configured_keys(self) -> None:
        old = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "old_root": {"type": "string"},
                "ask_for_approval": {"type": "string"},
                "features": {
                    "type": "object",
                    "properties": {"old_feature": {"type": "boolean"}},
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        }
        new = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "approval_policy": {"type": "string"},
                "new_root": {"type": "string"},
                "features": {
                    "type": "object",
                    "properties": {"new_feature": {"type": "boolean"}},
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        }
        config = {
            "old_root": "TOP-SECRET-VALUE",
            "ask_for_approval": "never",
            "features": {"old_feature": True},
        }
        report = build_migration_report(
            from_input="0.135.0",
            to_input="0.150.0",
            old_schema=old,
            new_schema=new,
            config=config,
            from_source="old.json",
            to_source="new.json",
        )
        ids = {item["rule_id"] for item in report["config_impacts"]}
        self.assertTrue({"CG401", "CG402", "CG403"}.issubset(ids))
        self.assertEqual("verified", report["change_evidence_status"])

        markdown = render_markdown_report(report)
        self.assertNotIn("TOP-SECRET-VALUE", markdown)
        self.assertIn("$.old_root", markdown)
        self.assertIn("docs-only", markdown)

    def test_branch_ref_is_marked_version_ambiguous(self) -> None:
        old = {"type": "object", "properties": {}, "additionalProperties": False}
        new = {"type": "object", "properties": {}, "additionalProperties": False}
        report = build_migration_report(
            from_input="main",
            to_input="0.150.0",
            old_schema=old,
            new_schema=new,
        )
        self.assertEqual("version-ambiguous", report["change_evidence_status"])


if __name__ == "__main__":
    unittest.main()

class PublicationPrepTests(unittest.TestCase):
    def test_package_version_matches_pyproject(self) -> None:
        import re
        import codex_config_guard

        pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version = "([^"]+)"$', pyproject, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(codex_config_guard.__version__, match.group(1))

    def test_publish_helper_defaults_to_dry_run(self) -> None:
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, "scripts/publish_github.py", "--owner", "example-user"],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertIn("DRY RUN", proc.stdout)
        self.assertIn("example-user/codex-config-guard", proc.stdout)
        self.assertNotIn("PUBLICATION_BOOTSTRAP_PASS", proc.stdout)
