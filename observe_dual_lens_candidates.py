#!/usr/bin/env python3
"""Observe Combat vs Economic Lens disagreement without changing combat control."""

import json
from collections import Counter
from pathlib import Path

from external_economic_lens import candidate_space_snapshot, evaluate_economic
from run_whole_flow_control_v2 import play


SEED = 3202
SEAT = 0


def main():
    candidate_space = candidate_space_snapshot()
    result = play(SEED, SEAT, True)

    points = []
    agreement = 0
    disagreement = 0

    for event in result["flow_trace"]:
        combat = event.get("mode")
        economic = evaluate_economic(event)
        same = combat == economic["judgment"]

        if same:
            agreement += 1
        else:
            disagreement += 1
            points.append({
                "turn": event.get("turn"),
                "day": event.get("day"),
                "state": {
                    "relation_axes": event.get("relation_axes"),
                    "axis_movements": event.get("axis_movements"),
                },
                "combat_judgment": combat,
                "economic_judgment": economic["judgment"],
                "economic_reason": economic["reason"],
                "status": "candidate_generation_point",
                "wrong_lens": None,
                "promote": False,
            })

    out = {
        "schema": "kaggriculture.dual-lens-candidate-observation.v0",
        "seed": SEED,
        "seat": SEAT,
        "candidate_space_at_battle_start": candidate_space,
        "battle_terminal": {
            "score": result["score"],
            "used_to_choose_lens": False,
        },
        "agreement_count": agreement,
        "disagreement_count": disagreement,
        "disagreement_rate": disagreement / max(1, agreement + disagreement),
        "combat_mode_counts": dict(Counter(e.get("mode") for e in result["flow_trace"])),
        "candidate_generation_points": points,
        "boundary": "observation_only_no_combat_change_no_rule_promotion",
    }

    Path("dual_lens_candidate_observation.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({
        "candidate_space": candidate_space,
        "agreement_count": agreement,
        "disagreement_count": disagreement,
        "disagreement_rate": out["disagreement_rate"],
        "generation_point_count": len(points),
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
