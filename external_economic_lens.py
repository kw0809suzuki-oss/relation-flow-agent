"""External Economic Lens v0.

This module does not control Kaggriculture actions.
It reads the same observed relation state as the Combat controller and produces
an independent coarse economic judgment for comparison only.

Disagreement is material for candidate generation, not evidence that either
lens is wrong.
"""

CANDIDATE_SPACE = ("push", "maintain", "stop", "switch")


def candidate_space_snapshot():
    return {
        "candidates": list(CANDIDATE_SPACE),
        "scope": "declared_coarse_modes_only",
        "winner_only": False,
        "adoption": "none",
    }


def evaluate_economic(event):
    axes = event.get("relation_axes") or {}
    movements = event.get("axis_movements")

    required = ("money", "capacity", "production")
    if any(k not in axes for k in required):
        return {
            "judgment": "unknown",
            "reason": "relation_axes_missing",
            "promote": False,
        }

    reserve = (float(axes["money"]) + float(axes["capacity"])) / 2.0
    productive_base = float(axes["production"])

    if movements is None or any(k not in movements for k in required):
        return {
            "judgment": "maintain",
            "reason": "warmup_no_trend_preserve_optional_space",
            "reserve": reserve,
            "productive_base": productive_base,
            "trend": None,
            "promote": False,
        }

    trend = sum(float(movements[k]) for k in required) / 3.0

    # Deliberately independent from the Combat 2-of-3 majority rule.
    if reserve >= 0.0 and trend >= 0.0:
        judgment = "push"
        reason = "reserve_nonnegative_and_trend_nonnegative"
    elif reserve < 0.0 and trend < 0.0:
        judgment = "stop"
        reason = "reserve_negative_and_trend_negative"
    elif productive_base < 0.0 and trend >= 0.0:
        judgment = "maintain"
        reason = "productive_base_negative_but_trend_nonnegative"
    else:
        judgment = "switch"
        reason = "mixed_economic_state"

    return {
        "judgment": judgment,
        "reason": reason,
        "reserve": reserve,
        "productive_base": productive_base,
        "trend": trend,
        "promote": False,
    }
