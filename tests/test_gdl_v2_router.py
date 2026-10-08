import unittest

from codex_config_guard.gdl_v2_router import select_route, validate_route


class GdlV2RouteTests(unittest.TestCase):
    def test_routine_default(self):
        route = select_route("routine")
        self.assertEqual(route.model, "gpt-6-luna")
        self.assertEqual(route.reasoning_effort, "max")

    def test_standard_default(self):
        route = select_route("standard")
        self.assertEqual(route.model, "gpt-6.1-sol")
        self.assertEqual(route.reasoning_effort, "high")

    def test_critical_default(self):
        route = select_route("critical")
        self.assertEqual(route.model, "gpt-6-astra")
        self.assertEqual(route.reasoning_effort, "high")

    def test_routine_can_escalate_to_sol(self):
        route = validate_route("routine", "gpt-6.1-sol", "high")
        self.assertEqual(route.model, "gpt-6.1-sol")

    def test_standard_can_escalate_to_astra(self):
        route = validate_route("standard", "gpt-6-astra", "xhigh")
        self.assertEqual(route.reasoning_effort, "xhigh")

    def test_standard_rejects_luna(self):
        with self.assertRaisesRegex(ValueError, "below model floor"):
            validate_route("standard", "gpt-6-luna", "max")

    def test_critical_rejects_sol(self):
        with self.assertRaisesRegex(ValueError, "below model floor"):
            validate_route("critical", "gpt-6.1-sol", "max")

    def test_luna_rejects_effort_below_max(self):
        with self.assertRaisesRegex(ValueError, "below reasoning floor"):
            validate_route("routine", "gpt-6-luna", "high")

    def test_sol_rejects_effort_below_high(self):
        with self.assertRaisesRegex(ValueError, "below reasoning floor"):
            validate_route("standard", "gpt-6.1-sol", "medium")

    def test_unknown_task_class_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported task class"):
            select_route("unknown")  # type: ignore[arg-type]

    def test_unknown_model_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported model"):
            validate_route("routine", "gpt-0-fictional", "max")

    def test_unknown_effort_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported reasoning effort"):
            validate_route("routine", "gpt-6-luna", "ultra")


if __name__ == "__main__":
    unittest.main()
