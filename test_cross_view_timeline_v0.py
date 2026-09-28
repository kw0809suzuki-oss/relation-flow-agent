import unittest

import cross_view_timeline_v0 as cv


def obs(
    player,
    *,
    money=100,
    land=None,
    hands=None,
    shed=None,
    seeds=None,
    tiles=None,
    inventories=None,
):
    farms = [
        {
            "money": 100,
            "unlocked_quadrants": ["NW"],
            "hands": [],
            "tiles": [[None]],
        },
        {
            "money": 100,
            "unlocked_quadrants": ["NW"],
            "hands": [],
            "tiles": [[None]],
        },
    ]
    farms[player] = {
        "money": money,
        "unlocked_quadrants": land or ["NW"],
        "hands": hands or [],
        "tiles": tiles or [[None]],
    }
    return {
        "day": 0,
        "hour": 0,
        "farms": farms,
        "private": {
            "shed": shed or {},
            "seeds": seeds or {},
            "inventories": inventories or [{}],
        },
    }


class CrossViewTimelineTest(unittest.TestCase):
    def test_buy_land_requires_action_and_state_change_for_witness(self):
        before = cv.state_summary(obs(0, money=110, land=["NW"]), 0)
        after = cv.state_summary(obs(0, money=25, land=["NW", "NE"]), 0)
        transition = cv.transition_summary(
            before,
            after,
            {
                "farmer": ["PASS"],
                "hands": [],
                "market": [["BUY_LAND"]],
            },
        )
        self.assertIn(
            {
                "kind": "productive_conversion",
                "subtype": "LAND",
                "evidence": "action+land_state_change",
            },
            transition["direct_witnesses"],
        )

    def test_buy_animal_uses_unplaced_animal_state(self):
        before = cv.state_summary(obs(0, money=337, shed={"COW": 0}), 0)
        after = cv.state_summary(obs(0, money=33, shed={"COW": 1}), 0)
        transition = cv.transition_summary(
            before,
            after,
            {
                "farmer": ["PASS"],
                "hands": [],
                "market": [
                    ["SELL", "FERTILIZER", 1],
                    ["BUY_ANIMAL", "COW", 1],
                ],
            },
        )
        self.assertTrue(
            any(
                witness.get("subtype") == "ANIMAL"
                for witness in transition["direct_witnesses"]
            )
        )

    def test_sell_request_is_not_promoted_to_executed_return(self):
        before = cv.state_summary(obs(0, money=100, shed={"MELON": 6}), 0)
        after = cv.state_summary(obs(0, money=100, shed={"MELON": 6}), 0)
        transition = cv.transition_summary(
            before,
            after,
            {
                "farmer": ["PASS"],
                "hands": [],
                "market": [["SELL", "MELON", 6]],
            },
        )
        self.assertEqual([["SELL", "MELON", 6]], transition["sell_requests"])
        self.assertFalse(
            any(
                witness.get("kind") == "return"
                for witness in transition["direct_witnesses"]
            )
        )

    def test_difference_orientation_is_player1_minus_player0(self):
        player0 = cv.state_summary(obs(0, money=100), 0)
        player1 = cv.state_summary(obs(1, money=130), 1)
        difference = cv.difference_view(player0, player1)
        self.assertEqual("player1_minus_player0", difference["orientation"])
        self.assertEqual(30.0, difference["scalar_delta"]["cash"])


if __name__ == "__main__":
    unittest.main()
