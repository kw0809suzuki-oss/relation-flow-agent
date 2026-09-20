"""Learning Candidate v0.

Battle result does not create a rule.
This layer only structures where re-entry may be needed.

Central boundary:
Outcome is an input to learning, not a command to update the Judgment Guide.
"""

LEARNING_TARGETS = [
    "state_reading",
    "relation_comparison",
    "candidate_quality",
    "action_realization",
    "judgment_guide",
]


def diagnose_reentry(record):
    execution = record.get("execution_state")
    observation = record.get("observation_state")
    outcome = record.get("outcome_state")
    expected = record.get("expected_observable_change")
    actual = record.get("actual_observable_change")

    targets = []
    reason = []

    if execution in ("not_executed", "unreachable", "duplicate"):
        targets = ["action_realization"]
        reason.append("The intervention did not establish an independent executed difference.")
    elif execution == "executed" and observation in ("not_observed", "observed_same"):
        targets = ["candidate_quality", "action_realization"]
        reason.append("Execution occurred but the expected independent observable difference was not established.")
    elif execution == "executed" and observation == "observed_diff":
        if expected and actual and expected != actual:
            targets = ["candidate_quality", "relation_comparison"]
            reason.append("An action difference existed, but the observed change did not match the expected relation.")
        elif outcome == "worsened":
            targets = ["relation_comparison", "state_reading"]
            reason.append("The expected/actual relation was expressed, but the resulting outcome worsened.")
        elif outcome in ("improved", "unresolved"):
            targets = ["relation_comparison"]
            reason.append("The concrete relation reached the environment; review how strongly it should influence comparison.")
        else:
            targets = ["relation_comparison"]
            reason.append("The relation was expressed, but outcome interpretation remains open.")
    else:
        targets = ["candidate_quality"]
        reason.append("The record is insufficient to diagnose a deeper layer.")

    # Guide is deliberately excluded from single-run diagnosis.
    return {
        "update_target_candidates": targets,
        "reason": reason,
        "evidence": record.get("evidence", []),
        "uncertainty": record.get("uncertainty", []),
        "reentry_depth": targets[-1] if targets else None,
        "status": "proposed",
        "auto_adopt": False,
        "judgment_guide_update_allowed": False,
    }


def build_learning_packet(record):
    return {
        "schema": "kaggriculture.learning-candidate.v0",
        "decision_contract": record.get("decision_contract"),
        "execution_state": record.get("execution_state"),
        "observation_state": record.get("observation_state"),
        "outcome_state": record.get("outcome_state"),
        "expected_observable_change": record.get("expected_observable_change"),
        "actual_observable_change": record.get("actual_observable_change"),
        "learning_candidate": diagnose_reentry(record),
        "boundary": [
            "Action failure != Candidate failure.",
            "Candidate failure != Direction failure.",
            "Direction failure != Relation failure.",
            "Relation failure != Judgment Guide failure.",
            "Outcome is an input to learning, not a rule-generation command.",
            "Learning Candidate != Adopted Learning.",
            "Single-run evidence cannot update Judgment Guide automatically.",
        ],
    }
