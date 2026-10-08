import unittest

from codex_config_guard.gdl_v2_router import (
    ACTIVE_ROUTE_POLICY,
    ASTRA_HIGH_DEFAULT_ROUTES,
    ASTRA_HIGH_TASK_MIN_MODEL,
    BALANCED_DEFAULT_ROUTES,
    BALANCED_TASK_MIN_MODEL,
    DEFAULT_ROUTES,
    DEFAULT_ROUTES_BY_POLICY,
    MODEL_MIN_EFFORT,
    TASK_MIN_MODEL,
    TASK_MIN_MODEL_BY_POLICY,
    select_route,
    validate_route,
)


class GdlV2RouteTests(unittest.TestCase):
    def test_active_policy_binds_public_maps(self):
        self.assertIn(ACTIVE_ROUTE_POLICY, DEFAULT_ROUTES_BY_POLICY)
        self.assertIs(DEFAULT_ROUTES, DEFAULT_ROUTES_BY_POLICY[ACTIVE_ROUTE_POLICY])
        self.assertIs(TASK_MIN_MODEL, TASK_MIN_MODEL_BY_POLICY[ACTIVE_ROUTE_POLICY])

    def test_temporary_astra_policy_definition(self):
        for task_class in ("routine", "standard", "critical"):
            route = ASTRA_HIGH_DEFAULT_ROUTES[task_class]
            self.assertEqual(route.model, "gpt-6-astra")
            self.assertEqual(route.reasoning_effort, "high")
            self.assertEqual(route.task_class, task_class)
            self.assertEqual(ASTRA_HIGH_TASK_MIN_MODEL[task_class], "gpt-6-astra")

    def test_balanced_policy_definition_is_preserved_for_one_line_rollback(self):
        self.assertEqual(BALANCED_DEFAULT_ROUTES["routine"].model, "gpt-6-luna")
        self.assertEqual(BALANCED_DEFAULT_ROUTES["routine"].reasoning_effort, "max")
        self.assertEqual(BALANCED_DEFAULT_ROUTES["standard"].model, "gpt-6.1-sol")
        self.assertEqual(BALANCED_DEFAULT_ROUTES["standard"].reasoning_effort, "high")
        self.assertEqual(BALANCED_DEFAULT_ROUTES["critical"].model, "gpt-6-astra")
        self.assertEqual(BALANCED_DEFAULT_ROUTES["critical"].reasoning_effort, "high")
        self.assertEqual(BALANCED_TASK_MIN_MODEL, {
            "routine": "gpt-6-luna",
            "standard": "gpt-6.1-sol",
            "critical": "gpt-6-astra",
        })

    def test_select_route_matches_active_policy(self):
        for task_class in ("routine", "standard", "critical"):
            self.assertEqual(select_route(task_class), DEFAULT_ROUTES_BY_POLICY[ACTIVE_ROUTE_POLICY][task_class])

    def test_active_policy_model_floor_is_enforced(self):
        if ACTIVE_ROUTE_POLICY == "astra-high-temporary":
            with self.assertRaisesRegex(ValueError, "below model floor"):
                validate_route("routine", "gpt-6-luna", "max")
            with self.assertRaisesRegex(ValueError, "below model floor"):
                validate_route("standard", "gpt-6.1-sol", "high")
        else:
            self.assertEqual(validate_route("routine", "gpt-6-luna", "max").model, "gpt-6-luna")
            self.assertEqual(validate_route("standard", "gpt-6.1-sol", "high").model, "gpt-6.1-sol")

    def test_astra_high_is_valid_for_every_task_class(self):
        for task_class in ("routine", "standard", "critical"):
            route = validate_route(task_class, "gpt-6-astra", "high")
            self.assertEqual(route.model, "gpt-6-astra")
            self.assertEqual(route.reasoning_effort, "high")

    def test_astra_rejects_effort_below_high(self):
        with self.assertRaisesRegex(ValueError, "below reasoning floor"):
            validate_route("critical", "gpt-6-astra", "medium")

    def test_model_effort_baselines_remain_intact(self):
        self.assertEqual(MODEL_MIN_EFFORT["gpt-6-luna"], "max")
        self.assertEqual(MODEL_MIN_EFFORT["gpt-6.1-sol"], "high")
        self.assertEqual(MODEL_MIN_EFFORT["gpt-6-astra"], "high")

    def test_unknown_task_class_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported task class"):
            select_route("unknown")  # type: ignore[arg-type]

    def test_unknown_model_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported model"):
            validate_route("routine", "gpt-0-fictional", "max")

    def test_unknown_effort_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported reasoning effort"):
            validate_route("routine", "gpt-6-astra", "ultra")


if __name__ == "__main__":
    unittest.main()
