import unittest

import seed_horizon_isolation_probe_v0 as probe
import strong_origin_v2_body_only_v0 as current


def action_with(*orders):
    return {
        "farmer": ["PASS"],
        "hands": [],
        "market": [list(x) for x in orders],
    }


class SeedHorizonIsolationProbeTest(unittest.TestCase):
    def test_a_matches_current_d14_filter_on_mixed_orders(self):
        obs = {"day": 20, "hour": 5}
        action = action_with(
            ("SELL", "WHEAT", 2),
            ("BUY_LAND",),
            ("BUY_SEED", "WHEAT", 1),
            ("BUY_ANIMAL", "COW", 1),
            ("BUY_PRODUCT", "COW", 1),
            ("HIRE",),
        )
        expected, _ = current._apply_d14(obs, action)
        actual, _, _ = probe.filter_action(obs, action, probe.MODE_CURRENT_D14)
        self.assertEqual(expected, actual)

    def test_b_reopens_seed_but_keeps_structural_closure(self):
        obs = {"day": 20, "hour": 5}
        action = action_with(
            ("BUY_LAND",),
            ("BUY_SEED", "WHEAT", 1),
            ("BUY_ANIMAL", "COW", 1),
            ("BUY_PRODUCT", "COW", 1),
            ("HIRE",),
        )
        actual, removed, decisions = probe.filter_action(
            obs, action, probe.MODE_SEED_REOPEN
        )
        self.assertEqual(
            [["BUY_SEED", "WHEAT", 1], ["HIRE"]],
            actual["market"],
        )
        self.assertEqual(1, len(decisions))
        self.assertTrue(decisions[0]["allowed"])
        self.assertIn(["BUY_LAND"], removed)
        self.assertIn(["BUY_ANIMAL", "COW", 1], removed)

    def test_c_allows_day27_wheat_from_earliest_harvest_boundary(self):
        obs = {"day": 27, "hour": 0}
        action = action_with(("BUY_SEED", "WHEAT", 1))
        actual, removed, decisions = probe.filter_action(
            obs, action, probe.MODE_HARVEST_FEASIBLE_SEED
        )
        self.assertEqual([["BUY_SEED", "WHEAT", 1]], actual["market"])
        self.assertEqual([], removed)
        self.assertEqual(29, decisions[0]["earliest_harvest_day"])
        self.assertTrue(decisions[0]["allowed"])

    def test_c_rejects_day28_wheat(self):
        obs = {"day": 28, "hour": 0}
        action = action_with(("BUY_SEED", "WHEAT", 1))
        actual, removed, decisions = probe.filter_action(
            obs, action, probe.MODE_HARVEST_FEASIBLE_SEED
        )
        self.assertEqual([], actual["market"])
        self.assertEqual([["BUY_SEED", "WHEAT", 1]], removed)
        self.assertEqual(30, decisions[0]["earliest_harvest_day"])
        self.assertFalse(decisions[0]["allowed"])

    def test_c_rejects_day27_hour23_wheat_due_to_market_after_units(self):
        obs = {"day": 27, "hour": 23}
        action = action_with(("BUY_SEED", "WHEAT", 1))
        _, removed, decisions = probe.filter_action(
            obs, action, probe.MODE_HARVEST_FEASIBLE_SEED
        )
        self.assertEqual([["BUY_SEED", "WHEAT", 1]], removed)
        self.assertEqual(28, decisions[0]["earliest_plant_day"])
        self.assertEqual(30, decisions[0]["earliest_harvest_day"])
        self.assertFalse(decisions[0]["allowed"])

    def test_c_separates_melon_horizon_from_wheat(self):
        obs = {"day": 20, "hour": 0}
        action = action_with(
            ("BUY_SEED", "WHEAT", 1),
            ("BUY_SEED", "MELON", 1),
        )
        actual, removed, decisions = probe.filter_action(
            obs, action, probe.MODE_HARVEST_FEASIBLE_SEED
        )
        self.assertEqual([["BUY_SEED", "WHEAT", 1]], actual["market"])
        self.assertEqual([["BUY_SEED", "MELON", 1]], removed)
        by_crop = {d["crop"]: d for d in decisions}
        self.assertTrue(by_crop["WHEAT"]["allowed"])
        self.assertFalse(by_crop["MELON"]["allowed"])
        self.assertEqual(30, by_crop["MELON"]["earliest_harvest_day"])

    def test_pre_d14_is_identical_for_all_modes(self):
        obs = {"day": 13, "hour": 23}
        action = action_with(
            ("BUY_LAND",),
            ("BUY_SEED", "MELON", 1),
            ("BUY_ANIMAL", "COW", 1),
        )
        for mode in sorted(probe.VALID_MODES):
            actual, removed, decisions = probe.filter_action(obs, action, mode)
            self.assertEqual(action, actual)
            self.assertEqual([], removed)
            self.assertEqual([], decisions)


if __name__ == "__main__":
    unittest.main()
