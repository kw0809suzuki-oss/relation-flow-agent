"""Open Learning Probe v0.

Builds an open diagnosis task from an unknown Battle result.
The existing learning taxonomy is reference-only, not a closed label set.
No learning is adopted here.
"""

REFERENCE_TAXONOMY = [
    "state_reading",
    "relation_comparison",
    "candidate_quality",
    "action_realization",
    "judgment_guide",
]


def build_open_learning_packet(battle):
    return {
        "schema": "kaggriculture.open-learning-probe.v0",
        "battle": battle,
        "reference_taxonomy": {
            "status": "reference_only",
            "known_layers": REFERENCE_TAXONOMY,
            "outside_taxonomy_allowed": True,
        },
        "execution_ai_task": {
            "instruction": (
                "Read this Battle as an unknown case. Do not classify it by label matching. "
                "Separate observation from interpretation. Infer one or more plausible re-entry "
                "positions, including a new position outside the reference taxonomy if needed. "
                "Preserve unresolved alternatives. Identify the smallest next evidence that would "
                "most reduce the remaining candidate space."
            ),
            "required_output": {
                "observed": [],
                "interpretation": [],
                "reentry_candidates": [],
                "why": [],
                "missing_evidence": [],
                "minimal_next_evidence": [],
                "confidence_uncertainty": [],
            },
        },
        "learning_boundary": {
            "status": "proposed",
            "auto_adopt": False,
            "judgment_guide_update_allowed": False,
            "taxonomy_extension_auto_adopt": False,
            "single_battle_can_establish_cause": False,
        },
        "observation_targets": [
            "Does the learner force the case into the existing taxonomy?",
            "Does it create a new learning position, and if so why?",
            "Does it return too deep or too shallow?",
            "Does it keep missing evidence explicit?",
            "Does minimal_next_evidence actually reduce competing interpretations?",
        ],
    }
