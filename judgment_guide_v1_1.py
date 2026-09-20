"""Kaggriculture Judgment Guide v1.1.

Relation hints are grounded guidance candidates, not established rules.
Triage strength indicates evidence connectivity only; it is not a decision weight.
"""

JUDGMENT_GUIDE_V11 = {
    "purpose": (
        "Provide minimally grounded relation hints to a Judgment Model without "
        "deciding their truth, relevance, direction, or action."
    ),
    "triage_contract": {
        "statement": (
            "Flow grounding decides only whether a relation hint is worth passing "
            "forward, not whether it is true."
        ),
        "labels": {
            "strong_candidate": "既存Evidenceとの接続が比較的強く、見る価値が高い",
            "candidate": "既存Evidenceとの接続理由はあるが、直接Groundingは十分でない",
            "weak_candidate": "見る理由はあるが、支持は弱く具体化失敗など反証的材料もある",
            "unsupported": "現時点のEvidenceでは渡す理由が薄い",
        },
        "boundary": (
            "Triage strength is not a hidden rule weight. A strong candidate may be "
            "not relevant in a given State; a weak candidate may be relevant."
        ),
    },
    "relation_hints": [
        {
            "name": "time_x_returnability",
            "triage": "strong_candidate",
            "look_at": [
                "remaining_days", "current_money", "production_capacity",
                "inventory", "harvestable_output"
            ],
            "question": "残り時間に対して、新しい投資はterminalまでに価値をMoneyへ戻せそうか。",
            "grounding_note": (
                "Late Expansion loss signals and payback replay provide a relatively "
                "strong reason to inspect this relation. No fixed day threshold is implied."
            ),
        },
        {
            "name": "capacity_x_need",
            "triage": "candidate",
            "look_at": ["land", "cows", "hands", "planted_tiles", "empty_tiles", "inventory"],
            "question": "今ある生産能力で十分か。それとも追加capacityに意味がありそうか。",
            "grounding_note": (
                "Expansion/Closure evidence supports asking whether more capacity is useful, "
                "but capacity itself has not been cleanly separated."
            ),
        },
        {
            "name": "flow_x_blockage",
            "triage": "candidate",
            "look_at": ["feed_input", "hands", "work_backlog", "harvestable_output", "inventory", "money"],
            "question": "餌・人手・作業待ち・販売待ちのどこかが、生産循環を詰まらせていないか。",
            "grounding_note": (
                "Feed and resource-flow differences have been observed. No proxy formula "
                "or universal blockage rule is established."
            ),
        },
        {
            "name": "output_x_cash_conversion",
            "triage": "weak_candidate",
            "look_at": ["harvestable_output", "inventory", "money", "remaining_days"],
            "question": "既に作った価値を今Moneyへ戻す余地はあるか。待つ価値との比較は必要か。",
            "grounding_note": (
                "Cash/Switch remains open. The concrete early-harvest + stop-HIRE "
                "implementation worsened outcomes, so this relation stays weak and open."
            ),
        },
    ],
    "judgment_model_contract": {
        "hint_relevance_labels": [
            "relevant",
            "weakly_relevant",
            "not_relevant",
            "conflicting",
            "missing_evidence",
        ],
        "instruction": (
            "Read each relation hint against the current State. Triage labels describe "
            "evidence connectivity only and must not be used as fixed decision weights."
        ),
    },
    "boundaries": [
        "These relation hints are grounded guidance candidates, not established rules.",
        "A hint may be irrelevant in the current state.",
        "A hint may conflict with another hint.",
        "A hint may be outweighed by another observed relation.",
        "Do not force exactly one direction.",
        "Do not derive a direction from a single threshold.",
        "Direction is not Action.",
        "If evidence is insufficient, preserve uncertainty.",
    ],
}
