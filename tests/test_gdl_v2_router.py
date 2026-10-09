import unittest

from codex_config_guard.gdl_v2_router import (
    ACTIVE_CURRENT_ROUTE_POLICY,
    CURRENT_DEFAULT_ROUTES_BY_POLICY,
    CURRENT_TASK_MIN_MODEL_BY_POLICY,
    DEFAULT_ROUTES,
    TASK_MIN_MODEL,
    select_current_route,
    select_route,
    validate_current_route,
    validate_route,
)


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

    def test_current_policy_selector_is_supported(self):
        self.assertIn(ACTIVE_CURRENT_ROUTE_POLICY, CURRENT_DEFAULT_ROUTES_BY_POLICY)
        self.assertIn(ACTIVE_CURRENT_ROUTE_POLICY, CURRENT_TASK_MIN_MODEL_BY_POLICY)
        for task_class in ("routine", "standard", "critical"):
            self.assertEqual(
                select_current_route(task_class),
                CURRENT_DEFAULT_ROUTES_BY_POLICY[ACTIVE_CURRENT_ROUTE_POLICY][task_class],
            )

    def test_temporary_current_policy_is_astra_high_for_all_classes(self):
        for task_class in ("routine", "standard", "critical"):
            route = CURRENT_DEFAULT_ROUTES_BY_POLICY["astra-high-temporary"][task_class]
            self.assertEqual(route.model, "gpt-6-astra")
            self.assertEqual(route.reasoning_effort, "high")
            self.assertEqual(CURRENT_TASK_MIN_MODEL_BY_POLICY["astra-high-temporary"][task_class], "gpt-6-astra")

    def test_balanced_current_policy_reuses_preserved_baseline(self):
        self.assertIs(CURRENT_DEFAULT_ROUTES_BY_POLICY["balanced"], DEFAULT_ROUTES)
        self.assertIs(CURRENT_TASK_MIN_MODEL_BY_POLICY["balanced"], TASK_MIN_MODEL)

    def test_active_current_model_floor_is_enforced(self):
        if ACTIVE_CURRENT_ROUTE_POLICY == "astra-high-temporary":
            with self.assertRaisesRegex(ValueError, "below Current model floor"):
                validate_current_route("routine", "gpt-6-luna", "max")
            with self.assertRaisesRegex(ValueError, "below Current model floor"):
                validate_current_route("standard", "gpt-6.1-sol", "high")
        else:
            self.assertEqual(validate_current_route("routine", "gpt-6-luna", "max").model, "gpt-6-luna")
            self.assertEqual(validate_current_route("standard", "gpt-6.1-sol", "high").model, "gpt-6.1-sol")

    def test_current_astra_high_is_valid_for_every_class(self):
        for task_class in ("routine", "standard", "critical"):
            route = validate_current_route(task_class, "gpt-6-astra", "high")
            self.assertEqual((route.model, route.reasoning_effort), ("gpt-6-astra", "high"))

    def test_unknown_task_class_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported task class"):
            select_route("unknown")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "unsupported task class"):
            select_current_route("unknown")  # type: ignore[arg-type]

    def test_unknown_model_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported model"):
            validate_route("routine", "gpt-0-fictional", "max")

    def test_unknown_effort_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported reasoning effort"):
            validate_route("routine", "gpt-6-luna", "ultra")


if __name__ == "__main__":
    unittest.main()
