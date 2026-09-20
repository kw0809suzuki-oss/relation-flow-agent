"""Open Learning Round v0.

Packages one unknown Battle together with the current candidate pool.
The round does not select a winner, invent evidence, or auto-update maturity.
"""

from open_learning_probe_v0 import REFERENCE_TAXONOMY


def build_open_learning_round(battle, open_candidates):
    return {
        "schema": "kaggriculture.open-learning-round.v0",
        "battle": battle,
        "candidate_pool": {
            "formal_reference": {
                "status": "reference_only",
                "candidates": list(REFERENCE_TAXONOMY),
            },
            "open_candidates": [dict(c) for c in open_candidates],
            "new_candidate_allowed": True,
        },
        "execution_ai_task": {
            "instruction": (
                "Treat this Battle as unknown. Observe freely. Compare existing formal-reference "
                "candidates and open candidates without assuming any is correct. State what each "
                "candidate explains, what remains unexplained, and create a new candidate only if "
                "needed. Choose the smallest evidence that most reduces the live candidate space. "
                "If that evidence requires an intervention, propose only the minimal A/B. "
                "Return evidence updates separately from adoption."
            ),
            "required_output": {
                "observed": [],
                "candidate_assessments": [],
                "unexplained": [],
                "new_candidates": [],
                "minimal_next_evidence": [],
                "minimal_ab_if_needed": [],
                "evidence_updates": [],
                "maturity_update_proposals": [],
                "adoption": "proposed",
            },
        },
        "learning_boundary": {
            "candidate_winner_required": False,
            "new_candidate_required": False,
            "auto_run_ab": False,
            "auto_update_maturity": False,
            "auto_adopt": False,
            "auto_promote_taxonomy": False,
            "judgment_guide_update_allowed": False,
        },
        "observation_targets": [
            "Does an existing candidate explain the Battle without forcing closure?",
            "Does an open candidate transfer to a different context?",
            "Does a previously plausible candidate fail under new evidence?",
            "Does a genuinely new learning position appear?",
            "Does the selected evidence reduce the live candidate space?",
        ],
    }
