"""Kaggriculture Judgment Guide v1.

v1 teaches observable relations, not directions or actions.
There are no thresholds that directly emit grow / earn / recover.
"""

JUDGMENT_GUIDE_V1 = {
    "purpose": (
        "Help a reasoning model generate farm judgment directions from observable "
        "state and evidence without embedding the answer in rules."
    ),
    "relation_hints": [
        {
            "name": "time_x_returnability",
            "look_at": ["remaining_days", "current_money", "production_capacity", "inventory", "harvestable_output"],
            "question": "残り時間に対して、新しい投資はterminalまでに価値をMoneyへ戻せそうか。",
        },
        {
            "name": "capacity_x_need",
            "look_at": ["land", "cows", "hands", "planted_tiles", "empty_tiles", "inventory"],
            "question": "今ある生産能力で十分か。それとも追加capacityに意味がありそうか。",
        },
        {
            "name": "flow_x_blockage",
            "look_at": ["feed_input", "hands", "work_backlog", "harvestable_output", "inventory", "money"],
            "question": "餌・人手・作業待ち・販売待ちのどこかが、生産循環を詰まらせていないか。",
        },
        {
            "name": "output_x_cash_conversion",
            "look_at": ["harvestable_output", "inventory", "money", "remaining_days"],
            "question": "既に作った価値を今Moneyへ戻す余地はあるか。待つ価値との比較は必要か。",
        },
    ],
    "candidate_directions": {
        "grow": "育てる必要",
        "earn": "稼ぐ必要",
        "recover": "立て直す必要",
    },
    "boundaries": [
        "Do not force exactly one direction.",
        "Do not derive a direction from a single threshold.",
        "Direction is not Action.",
        "earn != early harvest.",
        "closure != stop hiring.",
        "recover != buy wheat.",
        "Keep self, margin, and win as separate evidence axes.",
        "Human direction is an exploration vector, not ground truth.",
        "Known evidence constrains interpretation but does not dictate a concrete action.",
        "If evidence is insufficient, preserve uncertainty.",
    ],
    "known_evidence": [
        "Late continued Expansion has shown terminal-self loss signals.",
        "Closure direction has reproduced terminal-self improvement across multiple opponents.",
        "The concrete Switch 'stop HIRE + early HARVEST' worsened against Closure-only in 15/15 tested cases.",
        "This does not reject the upper-level Switch direction.",
    ],
}
