import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from codex_config_guard.gdl_v2_production import (
    MAX_PATCH_BYTES, build_work_unit_instruction, build_work_unit_payload,
    expected_result, extract_changed_paths, validate_artifacts, validate_downloaded_artifacts, validate_patch,
)
from codex_config_guard.gdl_v2_router import ModelRoute
from codex_config_guard.gdl_v2_sandbox import PATCH_ARTIFACT_PATH, RESULT_ARTIFACT_PATH, TEST_COMMAND
from codex_config_guard.gdl_v2_work_unit import validate_contract_data
from tests.test_gdl_v2_work_unit import VALID_DATA

REPOSITORY = Path(__file__).resolve().parents[1]


def added(path, content="new line"):
    lines = content.split("\n")
    return (f"diff --git a/{path} b/{path}\nnew file mode 100644\nindex 0000000..1111111\n"
            f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" + "".join("+" + line + "\n" for line in lines))


def modified(path):
    return (f"diff --git a/{path} b/{path}\nindex 1111111..2222222 100644\n"
            f"--- a/{path}\n+++ b/{path}\n@@ -1,2 +1,2 @@ function\n unchanged\n-old\n+new\n")


class PayloadTests(unittest.TestCase):
    def test_generic_payload_and_instructions_pin_every_boundary(self):
        contract = validate_contract_data(VALID_DATA)
        payload = build_work_unit_payload(contract)
        self.assertEqual(payload["agent"]["model"], contract.route.model)
        self.assertEqual(payload["agent"]["reasoning"], {"effort": "high"})
        self.assertEqual(payload["environment"]["type"], "openai_hosted")
        self.assertEqual(payload["environment"]["network"], {"access": "restricted", "allowed_domains": ["github.com"]})
        self.assertEqual(payload["environment"]["packages"]["python"], ["hatchling>=1.25", "jsonschema>=4.23,<5"])
        instruction = payload["input"]
        for text in (contract.source_sha, contract.summary, contract.instructions.split("\n")[0],
                     "git status --porcelain", "--no-build-isolation --no-deps", TEST_COMMAND,
                     "PYTHONPATH to /workspace/repo/src", "Never push", "close issues/PRs", "GDL v0.2 remains Current", "V2 is a candidate",
                     "patch_sha256", "contract_sha256", "allowed_paths", "max_changed_files",
                     "Re-read", "GDL_V2_SANDBOX_OK", PATCH_ARTIFACT_PATH, RESULT_ARTIFACT_PATH):
            self.assertIn(text, instruction)
        self.assertEqual(payload["metadata"]["contract_sha256"], contract.sha256)

    def test_caller_credentials_and_environment_never_enter_payload(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-caller-value", "GITHUB_TOKEN": "synthetic-github-value"}):
            serialized = json.dumps(build_work_unit_payload(validate_contract_data(VALID_DATA)))
        self.assertNotIn("synthetic-caller-value", serialized)
        self.assertNotIn("synthetic-github-value", serialized)
        self.assertNotIn("GITHUB_TOKEN", serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)

    def test_dataclass_bypass_cannot_weaken_route_or_path_guard(self):
        contract = validate_contract_data(VALID_DATA)
        for bad in (replace(contract, route=ModelRoute("gpt-6-luna", "max", "standard")),
                    replace(contract, allowed_paths=("../",)), replace(contract, max_changed_files=1000)):
            with self.assertRaises(ValueError):
                build_work_unit_payload(bad)
            with self.assertRaises(ValueError):
                build_work_unit_instruction(bad)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.contract = validate_contract_data(VALID_DATA)
        self.text = modified("src/codex_config_guard/feature.py") + added("tests/test_feature.py") + added("docs/guide.md", "first\nsecond")
        self.paths = ["docs/guide.md", "src/codex_config_guard/feature.py", "tests/test_feature.py"]

    def test_multi_file_create_modify_paths_are_sorted(self):
        self.assertEqual(extract_changed_paths(self.text), self.paths)
        self.assertEqual(validate_patch(self.contract, self.text.encode()), self.paths)

    def test_scope_and_max_changed_file_enforcement(self):
        for path in ("LICENSE", "docs-other/guide.md", "src/codex_config_guardian/feature.py", "README.md/extra"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "outside allowed_paths"):
                validate_patch(self.contract, added(path).encode())
        with self.assertRaisesRegex(ValueError, "max_changed_files"):
            validate_patch(replace(self.contract, max_changed_files=2), self.text.encode())
        exact = replace(self.contract, allowed_paths=("docs/guide.md",))
        self.assertEqual(validate_patch(exact, added("docs/guide.md").encode()), ["docs/guide.md"])
        with self.assertRaises(ValueError):
            validate_patch(exact, added("docs/guide.md/extra").encode())

    def test_mismatched_headers_traversal_git_and_duplicates_fail(self):
        base = added("docs/guide.md")
        bad = [base.replace("+++ b/docs/guide.md", "+++ b/LICENSE"),
               base.replace("diff --git a/docs/guide.md b/docs/guide.md", "diff --git a/LICENSE b/docs/guide.md"),
               base.replace("--- /dev/null", "--- a/LICENSE"), base + base]
        bad += [added(path) for path in ("docs/../escape", "docs/.git/config", ".git/config", "docs/a b", 'docs/"quoted"')]
        for text in bad:
            with self.subTest(text=text[:150]), self.assertRaises(ValueError):
                extract_changed_paths(text)

    def test_unsupported_operations_binary_symlink_and_mode_changes_fail(self):
        base = added("docs/guide.md")
        modification = modified("docs/guide.md")
        for text in (base.replace("100644", "120000"), base.replace("100644", "160000"),
                     base.replace("new file mode", "deleted file mode"), base.replace("+++ b/docs/guide.md", "+++ /dev/null"),
                     base.replace("@@ -0,0 +1,1 @@\n+new line", "GIT binary patch\nliteral 3\nabc"),
                     modification.replace("index ", "old mode 100644\nnew mode 100755\nindex "),
                     modification.replace("index ", "similarity index 90%\nrename from docs/guide.md\nrename to docs/other.md\nindex "),
                     modification.replace("index ", "copy from docs/guide.md\ncopy to docs/copy.md\nindex "),
                     modification.replace("2222222", "0000000"), base + "unexpected trailer\n"):
            with self.subTest(text=text[:150]), self.assertRaises(ValueError):
                extract_changed_paths(text)

    def test_all_hunks_are_parsed_not_just_headers(self):
        text = modified("docs/guide.md") + "@@ -10 +10 @@\n-old tail\n+new tail\n"
        self.assertEqual(extract_changed_paths(text), ["docs/guide.md"])
        no_newline = modified("docs/guide.md").replace("-old\n", "-old\n\\ No newline at end of file\n").replace("+new\n", "+new\n\\ No newline at end of file\n")
        self.assertEqual(extract_changed_paths(no_newline), ["docs/guide.md"])
        spoof = added("docs/guide.md", "diff --git a/LICENSE b/LICENSE\n+++ b/LICENSE\n@@ -1 +1 @@")
        self.assertEqual(extract_changed_paths(spoof), ["docs/guide.md"])
        for malformed in (text.replace("@@ -10 +10 @@", "@@ -1 +1 @@"),
                          text.replace("@@ -10 +10 @@", "@@ -10,9 +10 @@"),
                          text.replace("+new tail\n", ""), text.replace("+new tail\n", "+new tail\n+extra\n"),
                          added("docs/guide.md").replace("@@ -0,0 +1,1 @@", "@@ -1,1 +1,1 @@"),
                          added("docs/guide.md").replace("+new line\n", "\\ No newline at end of file\n")):
            with self.subTest(malformed=malformed[-100:]), self.assertRaises(ValueError):
                extract_changed_paths(malformed)

    def test_empty_oversized_non_utf8_and_crlf_fail(self):
        for raw in (b"", b"\xff", b"x" * (MAX_PATCH_BYTES + 1), self.text.replace("\n", "\r\n").encode(), self.text[:-1].encode()):
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                validate_patch(self.contract, raw)

    def test_verifier_accepts_real_git_generated_text_patch(self):
        # No commits or remotes: diff two files using git's real patch producer.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            file = root / "docs/guide.md"
            file.write_text("line one\nline two\n", encoding="utf-8")
            result = subprocess.run(["git", "diff", "--no-index", "--", "/dev/null", "docs/guide.md"], cwd=root, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(validate_patch(self.contract, result.stdout), ["docs/guide.md"])


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.contract = validate_contract_data(VALID_DATA)
        self.raw = (modified("src/codex_config_guard/feature.py") + added("tests/test_feature.py", "UTF-8 café")).encode()
        self.paths = extract_changed_paths(self.raw.decode())
        self.result = expected_result(self.contract, self.paths, hashlib.sha256(self.raw).hexdigest())

    def test_exact_metadata_and_patch_digest_are_verified(self):
        verified = validate_artifacts(self.contract, self.raw, json.dumps(self.result))
        self.assertTrue(verified["patch_verified"])
        self.assertTrue(verified["result_verified"])
        self.assertEqual(verified["changed_paths"], self.paths)
        self.assertEqual(verified["patch_sha256"], hashlib.sha256(self.raw).hexdigest())

    def test_every_metadata_field_is_bound_and_typed(self):
        mismatches = {"schema_version": True, "work_unit": "other-unit", "issue_number": 17, "task_class": "routine",
                      "model": "gpt-6-luna", "reasoning_effort": "max", "source_sha": "b" * 40,
                      "contract_sha256": "0" * 64, "test_profile": "arbitrary", "test_command": "true", "test_status": "fail",
                      "remote_write_attempted": True, "changed_paths": self.paths[::-1], "patch_sha256": "0" * 64}
        for key, value in mismatches.items():
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "metadata or patch digest"):
                validate_artifacts(self.contract, self.raw, json.dumps({**self.result, key: value}))
        for result in ({**self.result, "remote_write_attempted": 0}, {**self.result, "issue_number": 16.0},
                       {**self.result, "extra": "unreviewed"}, {k: v for k, v in self.result.items() if k != "model"}, []):
            with self.assertRaises(ValueError):
                validate_artifacts(self.contract, self.raw, json.dumps(result))

    def test_patch_tamper_duplicate_json_and_contract_tamper_fail(self):
        with self.assertRaisesRegex(ValueError, "digest"):
            validate_artifacts(self.contract, self.raw.replace(b"+new\n", b"+tampered\n"), json.dumps(self.result))
        duplicate = json.dumps(self.result)[:-1] + ', "test_status": "pass"}'
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_artifacts(self.contract, self.raw, duplicate)
        with self.assertRaises(ValueError):
            validate_artifacts(replace(self.contract, instructions="Task changed"), self.raw, json.dumps(self.result))

    def test_downloaded_artifacts_are_reread_and_incomplete_maps_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            patch_path, result_path = Path(tmp) / "change.patch", Path(tmp) / "result.json"
            patch_path.write_bytes(self.raw)
            result_path.write_text(json.dumps(self.result), encoding="utf-8")
            saved = {PATCH_ARTIFACT_PATH: patch_path, RESULT_ARTIFACT_PATH: result_path}
            self.assertTrue(validate_downloaded_artifacts(self.contract, saved)["result_verified"])
            result_path.write_text(json.dumps({**self.result, "test_status": "fail"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_downloaded_artifacts(self.contract, saved)
            with self.assertRaises(ValueError):
                validate_downloaded_artifacts(self.contract, {PATCH_ARTIFACT_PATH: patch_path})


class CliTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("work_unit_cli", REPOSITORY / "scripts/gdl_v2_work_unit.py")
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contract_file = self.root / "contract.json"
        self.contract_file.write_text(json.dumps(VALID_DATA), encoding="utf-8")
        self.stdout, self.stderr = io.StringIO(), io.StringIO()

    def run_cli(self, *args):
        with contextlib.redirect_stdout(self.stdout), contextlib.redirect_stderr(self.stderr):
            return self.cli.main([str(self.contract_file), *args])

    def test_default_dry_run_needs_no_secret_or_transport(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(self.cli, "run_sandbox_turn") as transport, patch.object(self.cli, "require_api_key") as key:
            self.assertEqual(self.run_cli(), 0)
        transport.assert_not_called()
        key.assert_not_called()
        data = json.loads(self.stdout.getvalue())
        self.assertEqual(data["mode"], "dry-run")
        self.assertEqual(data["route"]["model"], "gpt-6.1-sol")

    def test_explicit_live_still_needs_environment_key_and_trigger(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(self.cli, "verify_git_trigger", return_value={}), patch.object(self.cli, "run_sandbox_turn") as transport:
            self.assertEqual(self.run_cli("--live", "--output-dir", str(self.root / "output")), 2)
        transport.assert_not_called()
        self.assertIn("OPENAI_API_KEY is required", self.stderr.getvalue())
        with patch.object(self.cli, "verify_git_trigger", side_effect=ValueError("invalid marker")), patch.object(self.cli, "require_api_key") as key:
            self.assertEqual(self.run_cli("--live"), 2)
        key.assert_not_called()

    def test_live_uses_caller_key_only_and_records_verified_evidence(self):
        contract = validate_contract_data(VALID_DATA)
        output = self.root / "output"
        raw = added("docs/guide.md").encode()
        evidence = expected_result(contract, ["docs/guide.md"], hashlib.sha256(raw).hexdigest())
        turn = {"session_id": "session-fixture", "turn_id": "turn-fixture", "turn_status": "completed", "output_text": "GDL_V2_SANDBOX_OK"}

        def transport(payload, api_key):
            self.assertEqual(api_key, "synthetic-caller-only")
            self.assertNotIn(api_key, json.dumps(payload))
            self.assertEqual(json.loads((output / "dispatch.json").read_text())["status"], "dispatch_pending")
            return turn

        def download(session, turn_id, key, destination):
            self.assertEqual((session, turn_id), ("session-fixture", "turn-fixture"))
            self.assertEqual(json.loads((output / "dispatch.json").read_text())["turn_id"], turn_id)
            patch_path, result_path = destination / "change.patch", destination / "result.json"
            patch_path.write_bytes(raw)
            result_path.write_text(json.dumps(evidence), encoding="utf-8")
            return {PATCH_ARTIFACT_PATH: patch_path, RESULT_ARTIFACT_PATH: result_path}

        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-caller-only", "GITHUB_RUN_ATTEMPT": "1"}), \
                patch.object(self.cli, "verify_git_trigger", return_value={"branch": "gdl-v2/work/issue-16-productionization", "head_sha": "a" * 40}), \
                patch.object(self.cli, "run_sandbox_turn", side_effect=transport) as run, patch.object(self.cli, "fetch_required_artifacts", side_effect=download):
            self.assertEqual(self.run_cli("--live", "--output-dir", str(output)), 0)
            self.assertEqual(self.run_cli("--live", "--output-dir", str(output)), 2)
            self.assertEqual(run.call_count, 1)
        receipt = json.loads((output / "dispatch.json").read_text())
        self.assertEqual(receipt["status"], "artifacts_verified")
        self.assertNotIn("synthetic-caller-only", (output / "dispatch.json").read_text() + self.stdout.getvalue())

    def test_unknown_outcome_preserves_receipt_and_does_not_retry(self):
        output = self.root / "unknown"
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-caller-only", "GITHUB_RUN_ATTEMPT": "1"}), \
                patch.object(self.cli, "verify_git_trigger", return_value={"head_sha": "a" * 40}), \
                patch.object(self.cli, "run_sandbox_turn", side_effect=RuntimeError("untrusted remote body synthetic-caller-only")) as run:
            self.assertEqual(self.run_cli("--live", "--output-dir", str(output)), 2)
            self.assertEqual(self.run_cli("--live", "--output-dir", str(output)), 2)
            self.assertEqual(run.call_count, 1)
        self.assertEqual(json.loads((output / "dispatch.json").read_text())["status"], "dispatch_pending")
        self.assertIn("do not retry", self.stderr.getvalue())
        self.assertNotIn("synthetic-caller-only", self.stderr.getvalue())

    def test_workflow_keeps_token_outside_agent_and_guards_before_live(self):
        workflow = (REPOSITORY / ".github/workflows/gdl-v2-work-unit.yml").read_text()
        self.assertIn("contents: read", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("GDL_V2_OPENAI_API_KEY", workflow)
        self.assertNotIn("GITHUB_TOKEN", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertLess(workflow.index("--check-trigger"), workflow.index("secrets.GDL_V2_OPENAI_API_KEY"))
        self.assertIn("cancel-in-progress: false", workflow)


if __name__ == "__main__":
    unittest.main()
