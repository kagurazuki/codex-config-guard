import json
import tempfile
import unittest
from pathlib import Path

from codex_config_guard.gdl_v2_handoff import (
    HandoffContract,
    build_handoff_payload,
    load_contract,
    validate_contract_data,
    validate_downloaded_artifacts,
    validate_patch_text,
    validate_result_text,
)
from codex_config_guard.gdl_v2_sandbox import (
    PATCH_ARTIFACT_PATH,
    RESULT_ARTIFACT_PATH,
    TEST_COMMAND,
)


VALID_DATA = {
    "work_unit": "issue-11-phase4",
    "task_class": "routine",
    "source_sha": "b6d18dffcfad5016f2f21ee760372a2cf0ab2bdc",
    "changed_path": "docs/gdl-v2-orchestrated-handoff-canary.txt",
    "content": "GDL_V2_ORCHESTRATED_HANDOFF_CANARY\n",
}


def _contract() -> HandoffContract:
    return validate_contract_data(VALID_DATA)


class ContractTests(unittest.TestCase):
    def test_loads_exact_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract.json"
            path.write_text(json.dumps(VALID_DATA), encoding="utf-8")
            contract = load_contract(path)
        self.assertEqual(contract.work_unit, VALID_DATA["work_unit"])
        self.assertEqual(contract.changed_path, VALID_DATA["changed_path"])

    def test_rejects_extra_keys(self):
        bad = dict(VALID_DATA)
        bad["shell"] = "rm -rf /"
        with self.assertRaisesRegex(ValueError, "keys mismatch"):
            validate_contract_data(bad)

    def test_rejects_path_traversal(self):
        bad = dict(VALID_DATA)
        bad["changed_path"] = "docs/../README.txt"
        with self.assertRaisesRegex(ValueError, "safe docs"):
            validate_contract_data(bad)

    def test_rejects_non_docs_path(self):
        bad = dict(VALID_DATA)
        bad["changed_path"] = "src/escape.txt"
        with self.assertRaisesRegex(ValueError, "safe docs"):
            validate_contract_data(bad)

    def test_rejects_multiline_or_shellish_content(self):
        for content in (
            "FIRST\nSECOND\n",
            "hello\n",
            "MARKER;curl_bad\n",
            "MARKER $(id)\n",
        ):
            bad = dict(VALID_DATA)
            bad["content"] = content
            with self.subTest(content=content):
                with self.assertRaisesRegex(ValueError, "uppercase ASCII marker"):
                    validate_contract_data(bad)


class PayloadTests(unittest.TestCase):
    def test_default_route_is_explicit_luna_max(self):
        payload, route = build_handoff_payload(_contract())
        self.assertEqual(route.model, "gpt-6-luna")
        self.assertEqual(route.reasoning_effort, "max")
        self.assertEqual(payload["agent"]["model"], "gpt-6-luna")
        self.assertEqual(payload["agent"]["reasoning"]["effort"], "max")

    def test_environment_is_restricted_and_contract_is_pinned(self):
        contract = _contract()
        payload, _ = build_handoff_payload(contract)
        self.assertEqual(
            payload["environment"]["network"],
            {"access": "restricted", "allowed_domains": ["github.com"]},
        )
        self.assertEqual(payload["metadata"]["source_sha"], contract.source_sha)
        self.assertEqual(payload["metadata"]["work_unit"], contract.work_unit)
        self.assertIn(contract.source_sha, payload["input"])
        self.assertIn(contract.changed_path, payload["input"])
        self.assertIn(TEST_COMMAND, payload["input"])
        self.assertIn("Never push", payload["input"])

    def test_under_floor_explicit_route_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "below reasoning floor"):
            build_handoff_payload(
                _contract(),
                model="gpt-6-luna",
                reasoning_effort="high",
            )


class ArtifactValidationTests(unittest.TestCase):
    def setUp(self):
        self.contract = _contract()
        _, self.route = build_handoff_payload(self.contract)
        marker = self.contract.content.rstrip("\n")
        self.patch = (
            f"diff --git a/{self.contract.changed_path} "
            f"b/{self.contract.changed_path}\n"
            "new file mode 100644\n"
            "index 0000000..1111111\n"
            "--- /dev/null\n"
            f"+++ b/{self.contract.changed_path}\n"
            "@@ -0,0 +1 @@\n"
            f"+{marker}\n"
        )
        self.result = {
            "work_unit": self.contract.work_unit,
            "task_class": self.route.task_class,
            "model": self.route.model,
            "reasoning_effort": self.route.reasoning_effort,
            "source_sha": self.contract.source_sha,
            "changed_path": self.contract.changed_path,
            "content_sha256": self.contract.content_sha256,
            "test_command": TEST_COMMAND,
            "test_status": "pass",
            "remote_write_attempted": False,
        }

    def test_valid_patch_and_result_pass(self):
        validate_patch_text(self.contract, self.patch)
        self.assertEqual(
            validate_result_text(
                self.contract,
                self.route,
                json.dumps(self.result),
            ),
            self.result,
        )

    def test_patch_with_extra_change_fails(self):
        bad = self.patch + "diff --git a/README.md b/README.md\n"
        with self.assertRaisesRegex(ValueError, "unexpected paths"):
            validate_patch_text(self.contract, bad)

    def test_result_route_mismatch_fails(self):
        bad = dict(self.result)
        bad["reasoning_effort"] = "high"
        with self.assertRaisesRegex(ValueError, "did not match contract"):
            validate_result_text(
                self.contract,
                self.route,
                json.dumps(bad),
            )

    def test_downloaded_artifact_map_is_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            patch_path = Path(tmp) / "change.patch"
            result_path = Path(tmp) / "result.json"
            patch_path.write_text(self.patch, encoding="utf-8")
            result_path.write_text(json.dumps(self.result), encoding="utf-8")
            verified = validate_downloaded_artifacts(
                self.contract,
                self.route,
                {
                    PATCH_ARTIFACT_PATH: patch_path,
                    RESULT_ARTIFACT_PATH: result_path,
                },
            )
        self.assertTrue(verified["patch_verified"])
        self.assertTrue(verified["result_verified"])
        self.assertEqual(verified["model"], "gpt-6-luna")
        self.assertEqual(verified["reasoning_effort"], "max")
        self.assertFalse(verified["remote_write_attempted"])


if __name__ == "__main__":
    unittest.main()
