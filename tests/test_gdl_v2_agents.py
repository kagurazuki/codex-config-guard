import json
import unittest

from codex_config_guard.gdl_v2_agents import (
    CONNECTIVITY_INPUT,
    build_connectivity_payload,
    create_connectivity_session,
    require_api_key,
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

    def test_live_request_keeps_key_in_authorization_header_only(self):
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


if __name__ == "__main__":
    unittest.main()
