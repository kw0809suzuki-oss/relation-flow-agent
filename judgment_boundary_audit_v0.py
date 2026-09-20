"""Structural boundary audit for Judgment packets.

This checks only premature structural closure.
It does not judge whether a Hint, Direction, or Action is substantively correct.
"""

from judgment_manufacturing_policy_v0 import MANUFACTURING_POLICY_V0


def audit_packet(packet):
    boundary = packet.get("boundary", {}) or {}
    violations = []

    checks = {
        "hint_truth_decided": False,
        "triage_used_as_weight": False,
        "hint_relevance_precomputed": False,
        "direction_precomputed": False,
        "action_precomputed": False,
        "selection_precomputed": False,
    }

    for key, expected in checks.items():
        if key in boundary and boundary.get(key) != expected:
            violations.append({
                "field": key,
                "observed": boundary.get(key),
                "expected": expected,
                "reason": "premature closure at this layer",
            })

    return {
        "schema": "kaggriculture.judgment-boundary-audit.v0",
        "central_principle": MANUFACTURING_POLICY_V0["central_principle"],
        "pass": not violations,
        "violations": violations,
        "note": (
            "PASS means only that this packet did not structurally close fields "
            "that this layer is required to leave open."
        ),
    }
