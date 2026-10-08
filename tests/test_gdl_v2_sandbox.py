import json
import tempfile
import unittest
from pathlib import Path

from codex_config_guard.gdl_v2_sandbox import (
    CANARY_MARKER,
    CANARY_PATH,
    EXPECTED_FINAL_OUTPUT,
    PATCH_ARTIFACT_PATH,
    PROJECT_INSTALL_COMMAND,
    RESULT_ARTIFACT_PATH,
    SOURCE_SHA,
    TEST_COMMAND,
    build_sandbox_payload,
    fetch_required_artifacts,
    run_sandbox_turn,
    validate_downloaded_artifacts,
    validate_patch_text,
    validate_result_text,
)

EXPECTED_RESULT = {
    "source_sha": SOURCE_SHA,
    "changed_path": CANARY_PATH,
    "marker": CANARY_MARKER,
    "test_command": TEST_COMMAND,
    "test_status": "pass",
    "remote_write_attempted": False,
}

EXPECTED_PATCH = f"""diff --git a/{CANARY_PATH} b/{CANARY_PATH}
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/{CANARY_PATH}
@@ -0,0 +1 @@
+{CANARY_MARKER}
"""


def _text_done(text: str, output_index: int, *, item_id: str | None = None, content_index: int = 0):
    return {
        "type": "agent.session.turn.output_text.done",
        "item_id": item_id or f"msg_{output_index}",
        "output_index": output_index,
        "content_index": content_index,
        "text": text,
    }


class _FakeStreamResponse:
    def __init__(self, events):
        self._lines = [f"data: {json.dumps(event)}\n".encode() for event in events]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._lines)


class _FakeBytesResponse:
    def __init__(self, content: bytes):
        self._content = content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._content


class SandboxPayloadTests(unittest.TestCase):
    def test_payload_uses_openai_hosted_small_restricted_github_only(self):
        payload = build_sandbox_payload("routine")
        environment = payload["environment"]
        self.assertEqual(environment["type"], "openai_hosted")
        self.assertEqual(environment["container_size"], "small")
        self.assertEqual(
            environment["network"],
            {"access": "restricted", "allowed_domains": ["github.com"]},
        )
        self.assertEqual(
            environment["packages"]["python"],
            ["hatchling>=1.25", "jsonschema>=4.23,<5"],
        )

    def test_payload_pins_source_install_test_and_boundary(self):
        payload = build_sandbox_payload("routine")
        self.assertEqual(payload["metadata"]["source_sha"], SOURCE_SHA)
        self.assertIn(SOURCE_SHA, payload["input"])
        self.assertIn(PROJECT_INSTALL_COMMAND, payload["input"])
        self.assertIn(TEST_COMMAND, payload["input"])
        self.assertIn(CANARY_PATH, payload["input"])
        self.assertIn("Never push", payload["input"])
        self.assertIn(PATCH_ARTIFACT_PATH, payload["input"])
        self.assertIn(RESULT_ARTIFACT_PATH, payload["input"])

    def test_explicit_valid_route_is_preserved(self):
        payload = build_sandbox_payload(
            "routine", model="gpt-6.1-sol", reasoning_effort="high"
        )
        self.assertEqual(payload["agent"]["model"], "gpt-6.1-sol")
        self.assertEqual(payload["agent"]["reasoning"]["effort"], "high")


class SandboxTurnTests(unittest.TestCase):
    def _run(self, events):
        return run_sandbox_turn(
            build_sandbox_payload("routine"),
            "sk-test",
            opener=lambda request, timeout: _FakeStreamResponse(events),
        )

    def test_root_completion_and_exact_output_are_required(self):
        captured = {}
        events = [
            {"type": "agent.session.created", "session": {"id": "sess_2"}},
            _text_done(EXPECTED_FINAL_OUTPUT, 0),
            {
                "type": "agent.session.turn.completed",
                "turn": {"id": "turn_2", "subagent_id": None},
            },
        ]

        def opener(request, timeout):
            captured["auth"] = request.get_header("Authorization")
            captured["body"] = request.data.decode()
            return _FakeStreamResponse(events)

        result = run_sandbox_turn(
            build_sandbox_payload("routine"), "sk-sandbox-test", opener=opener
        )
        self.assertEqual(result["session_id"], "sess_2")
        self.assertEqual(result["turn_id"], "turn_2")
        self.assertEqual(result["output_text"], EXPECTED_FINAL_OUTPUT)
        self.assertEqual(captured["auth"], "Bearer sk-sandbox-test")
        self.assertNotIn("sk-sandbox-test", captured["body"])
        self.assertTrue(json.loads(captured["body"])["stream"])

    def test_progress_items_do_not_pollute_final_output(self):
        events = [
            {"type": "agent.session.created", "session": {"id": "sess_progress"}},
            _text_done("Cloning pinned source.", 0, item_id="msg_progress_0"),
            _text_done("All tests passed.", 1, item_id="msg_progress_1"),
            _text_done(EXPECTED_FINAL_OUTPUT, 2, item_id="msg_final"),
            {
                "type": "agent.session.turn.completed",
                "turn": {"id": "turn_progress", "subagent_id": None},
            },
        ]
        result = self._run(events)
        self.assertEqual(result["output_text"], EXPECTED_FINAL_OUTPUT)

    def test_multiple_content_parts_of_final_item_are_reconstructed(self):
        events = [
            {"type": "agent.session.created", "session": {"id": "sess_parts"}},
            _text_done("progress", 0),
            _text_done("GDL_V2_", 1, item_id="msg_final", content_index=0),
            _text_done("SANDBOX_OK", 1, item_id="msg_final", content_index=1),
            {
                "type": "agent.session.turn.completed",
                "turn": {"id": "turn_parts", "subagent_id": None},
            },
        ]
        result = self._run(events)
        self.assertEqual(result["output_text"], EXPECTED_FINAL_OUTPUT)

    def test_output_mismatch_fails_closed(self):
        events = [
            {"type": "agent.session.created", "session": {"id": "sess_bad"}},
            _text_done("WRONG", 0),
            {
                "type": "agent.session.turn.completed",
                "turn": {"id": "turn_bad", "subagent_id": None},
            },
        ]
        with self.assertRaisesRegex(RuntimeError, "output mismatch"):
            self._run(events)

    def test_missing_output_indices_fail_closed(self):
        events = [
            {"type": "agent.session.created", "session": {"id": "sess_bad"}},
            {
                "type": "agent.session.turn.output_text.done",
                "item_id": "msg_bad",
                "text": EXPECTED_FINAL_OUTPUT,
            },
        ]
        with self.assertRaisesRegex(RuntimeError, "invalid output/content index"):
            self._run(events)

    def test_root_failure_fails_closed(self):
        events = [
            {"type": "agent.session.created", "session": {"id": "sess_bad"}},
            {
                "type": "agent.session.turn.failed",
                "turn": {
                    "id": "turn_bad",
                    "subagent_id": None,
                    "error": {"message": "sandbox synthetic failure"},
                },
            },
        ]
        with self.assertRaisesRegex(RuntimeError, "sandbox synthetic failure"):
            self._run(events)


class ArtifactTests(unittest.TestCase):
    def test_fetches_only_required_turn_artifacts_without_key_in_url(self):
        secret = "sk-artifact-test"
        session_id = "sess_artifact"
        turn_id = "turn_artifact"
        list_payload = {
            "data": [
                {"id": "artifact_patch", "turn_id": turn_id, "path": PATCH_ARTIFACT_PATH},
                {"id": "artifact_result", "turn_id": turn_id, "path": RESULT_ARTIFACT_PATH},
                {"id": "artifact_old", "turn_id": "turn_old", "path": PATCH_ARTIFACT_PATH},
            ]
        }
        observed_urls = []
        observed_auth = []

        def list_opener(request, timeout):
            observed_urls.append(request.full_url)
            observed_auth.append(request.get_header("Authorization"))
            return _FakeBytesResponse(json.dumps(list_payload).encode())

        def content_opener(request, timeout):
            observed_urls.append(request.full_url)
            observed_auth.append(request.get_header("Authorization"))
            if "artifact_patch" in request.full_url:
                return _FakeBytesResponse(EXPECTED_PATCH.encode())
            if "artifact_result" in request.full_url:
                return _FakeBytesResponse(json.dumps(EXPECTED_RESULT).encode())
            raise AssertionError(request.full_url)

        with tempfile.TemporaryDirectory() as tmp:
            saved = fetch_required_artifacts(
                session_id,
                turn_id,
                secret,
                Path(tmp),
                list_opener=list_opener,
                content_opener=content_opener,
            )
            self.assertEqual(set(saved), {PATCH_ARTIFACT_PATH, RESULT_ARTIFACT_PATH})
            validation = validate_downloaded_artifacts(saved)
            self.assertTrue(validation["patch_verified"])
            self.assertTrue(validation["result_verified"])

        self.assertTrue(all(auth == f"Bearer {secret}" for auth in observed_auth))
        self.assertTrue(all(secret not in url for url in observed_urls))

    def test_missing_required_artifact_fails(self):
        payload = {
            "data": [
                {"id": "artifact_patch", "turn_id": "turn_x", "path": PATCH_ARTIFACT_PATH}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "missing required"):
                fetch_required_artifacts(
                    "sess_x",
                    "turn_x",
                    "sk-x",
                    Path(tmp),
                    list_opener=lambda request, timeout: _FakeBytesResponse(
                        json.dumps(payload).encode()
                    ),
                )


class ArtifactValidationTests(unittest.TestCase):
    def test_valid_patch_passes(self):
        validate_patch_text(EXPECTED_PATCH)

    def test_patch_with_unrelated_path_fails(self):
        bad = EXPECTED_PATCH + "diff --git a/README.md b/README.md\n"
        with self.assertRaisesRegex(ValueError, "unexpected paths"):
            validate_patch_text(bad)

    def test_patch_with_extra_added_content_fails(self):
        bad = EXPECTED_PATCH.replace(
            f"+{CANARY_MARKER}\n", f"+{CANARY_MARKER}\n+EXTRA\n"
        )
        with self.assertRaisesRegex(ValueError, "unexpected added content"):
            validate_patch_text(bad)

    def test_valid_result_passes(self):
        self.assertEqual(validate_result_text(json.dumps(EXPECTED_RESULT)), EXPECTED_RESULT)

    def test_wrong_source_sha_fails(self):
        bad = dict(EXPECTED_RESULT)
        bad["source_sha"] = "wrong"
        with self.assertRaisesRegex(ValueError, "did not match contract"):
            validate_result_text(json.dumps(bad))

    def test_non_pass_test_status_fails(self):
        bad = dict(EXPECTED_RESULT)
        bad["test_status"] = "fail"
        with self.assertRaisesRegex(ValueError, "did not match contract"):
            validate_result_text(json.dumps(bad))


if __name__ == "__main__":
    unittest.main()
