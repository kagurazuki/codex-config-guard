import json
import unittest

from codex_config_guard.gdl_v2_agents import (
    CONNECTIVITY_INPUT,
    EXPECTED_CONNECTIVITY_OUTPUT,
    build_connectivity_payload,
    create_connectivity_session,
    require_api_key,
    run_connectivity_canary,
)


class _FakeResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


class _FakeSseResponse:
    def __init__(self, events: list[dict]):
        self._lines = [
            f"data: {json.dumps(event)}\n".encode("utf-8") for event in events
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._lines)


class AgentsConnectivityTests(unittest.TestCase):
    def test_routine_payload_uses_luna_max(self):
        payload = build_connectivity_payload("routine")
        self.assertEqual(payload["agent"]["model"], "gpt-6-luna")
        self.assertEqual(payload["agent"]["reasoning"]["effort"], "max")

    def test_standard_payload_uses_sol_high(self):
        payload = build_connectivity_payload("standard")
        self.assertEqual(payload["agent"]["model"], "gpt-6.1-sol")
        self.assertEqual(payload["agent"]["reasoning"]["effort"], "high")

    def test_critical_payload_uses_astra_high(self):
        payload = build_connectivity_payload("critical")
        self.assertEqual(payload["agent"]["model"], "gpt-6-astra")
        self.assertEqual(payload["agent"]["reasoning"]["effort"], "high")

    def test_payload_has_no_execution_environment(self):
        payload = build_connectivity_payload("routine")
        self.assertEqual(payload["environment"], {"type": "none"})
        self.assertEqual(payload["input"], CONNECTIVITY_INPUT)

    def test_explicit_valid_upgrade_is_preserved(self):
        payload = build_connectivity_payload(
            "routine", model="gpt-6.1-sol", reasoning_effort="xhigh"
        )
        self.assertEqual(payload["agent"]["model"], "gpt-6.1-sol")
        self.assertEqual(payload["agent"]["reasoning"]["effort"], "xhigh")

    def test_partial_override_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "supplied together"):
            build_connectivity_payload("routine", model="gpt-6.1-sol")

    def test_under_floor_override_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "below model floor"):
            build_connectivity_payload(
                "standard", model="gpt-6-luna", reasoning_effort="max"
            )

    def test_missing_api_key_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
            require_api_key({})

    def test_api_key_is_not_part_of_payload(self):
        secret = "sk-test-do-not-serialize"
        payload = build_connectivity_payload("routine")
        self.assertNotIn(secret, json.dumps(payload))
        self.assertEqual(require_api_key({"OPENAI_API_KEY": secret}), secret)

    def test_session_creation_keeps_key_in_authorization_header_only(self):
        captured = {}

        def opener(request, timeout):
            captured["authorization"] = request.get_header("Authorization")
            captured["body"] = request.data.decode("utf-8")
            captured["timeout"] = timeout
            return _FakeResponse(
                {
                    "id": "sess_canary_123",
                    "status": "in_progress",
                    "environment": {"id": None, "type": "none"},
                }
            )

        secret = "sk-test-header-only"
        payload = build_connectivity_payload("routine")
        result = create_connectivity_session(payload, secret, opener=opener)

        self.assertEqual(captured["authorization"], f"Bearer {secret}")
        self.assertNotIn(secret, captured["body"])
        self.assertEqual(result["session_id"], "sess_canary_123")
        self.assertEqual(result["status"], "in_progress")
        self.assertIsNone(result["environment_id"])

    def test_streamed_canary_requires_completed_root_turn_and_exact_output(self):
        captured = {}
        events = [
            {
                "type": "agent.session.created",
                "session": {"id": "sess_stream_123"},
            },
            {
                "type": "agent.session.turn.output_text.done",
                "text": EXPECTED_CONNECTIVITY_OUTPUT,
            },
            {
                "type": "agent.session.turn.completed",
                "turn": {"id": "turn_stream_123", "subagent_id": None},
            },
        ]

        def opener(request, timeout):
            captured["authorization"] = request.get_header("Authorization")
            captured["accept"] = request.get_header("Accept")
            captured["body"] = request.data.decode("utf-8")
            captured["timeout"] = timeout
            return _FakeSseResponse(events)

        secret = "sk-test-stream-only"
        result = run_connectivity_canary(
            build_connectivity_payload("routine"), secret, opener=opener
        )

        request_payload = json.loads(captured["body"])
        self.assertTrue(request_payload["stream"])
        self.assertEqual(captured["authorization"], f"Bearer {secret}")
        self.assertEqual(captured["accept"], "text/event-stream")
        self.assertNotIn(secret, captured["body"])
        self.assertEqual(result["session_id"], "sess_stream_123")
        self.assertEqual(result["turn_id"], "turn_stream_123")
        self.assertEqual(result["turn_status"], "completed")
        self.assertEqual(result["output_text"], EXPECTED_CONNECTIVITY_OUTPUT)
        self.assertTrue(result["verified_output"])

    def test_stream_close_before_completion_fails_closed(self):
        events = [
            {
                "type": "agent.session.created",
                "session": {"id": "sess_incomplete"},
            },
            {
                "type": "agent.session.turn.output_text.done",
                "text": EXPECTED_CONNECTIVITY_OUTPUT,
            },
        ]

        with self.assertRaisesRegex(RuntimeError, "before the root turn completed"):
            run_connectivity_canary(
                build_connectivity_payload("routine"),
                "sk-test",
                opener=lambda request, timeout: _FakeSseResponse(events),
            )

    def test_output_mismatch_fails_closed(self):
        events = [
            {
                "type": "agent.session.created",
                "session": {"id": "sess_mismatch"},
            },
            {
                "type": "agent.session.turn.output_text.done",
                "text": "NOT_THE_EXPECTED_OUTPUT",
            },
            {
                "type": "agent.session.turn.completed",
                "turn": {"id": "turn_mismatch", "subagent_id": None},
            },
        ]

        with self.assertRaisesRegex(RuntimeError, "output mismatch"):
            run_connectivity_canary(
                build_connectivity_payload("routine"),
                "sk-test",
                opener=lambda request, timeout: _FakeSseResponse(events),
            )

    def test_root_turn_failure_fails_closed(self):
        events = [
            {
                "type": "agent.session.created",
                "session": {"id": "sess_failed"},
            },
            {
                "type": "agent.session.turn.failed",
                "turn": {
                    "id": "turn_failed",
                    "subagent_id": None,
                    "error": {"message": "synthetic failure"},
                },
            },
        ]

        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            run_connectivity_canary(
                build_connectivity_payload("routine"),
                "sk-test",
                opener=lambda request, timeout: _FakeSseResponse(events),
            )

    def test_unexpected_required_action_fails_closed(self):
        events = [
            {
                "type": "agent.session.created",
                "session": {"id": "sess_action"},
            },
            {"type": "agent.session.requires_action"},
        ]

        with self.assertRaisesRegex(RuntimeError, "requires external action"):
            run_connectivity_canary(
                build_connectivity_payload("routine"),
                "sk-test",
                opener=lambda request, timeout: _FakeSseResponse(events),
            )


if __name__ == "__main__":
    unittest.main()
