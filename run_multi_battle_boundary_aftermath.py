#!/usr/bin/env python3
"""Run multiple Kaggriculture battles and aggregate paired boundary aftermath contrasts."""

import json
from pathlib import Path

from analyze_boundary_aftermath import observe_aftermath
from analyze_boundary_aftermath_contrast import PAIRS, delta
from judgment_trace_bridge import cycles_from_trace
from run_whole_flow_control_v2 import play


CASES = ((3202, 0), (3206, 0), (3215, 1))


def serialize_cycle(c):
    return {
        "observe": {"known": list(c.observe.known), "missing": list(c.observe.missing)},
        "choose": {"selected": c.choose.selected},
    }


def mean_dict(items):
    if not items:
        return None
    keys = items[0].keys()
    return {k: sum(x[k] for x in items) / len(items) for k in keys}


def main():
    battles = []
    pair_deltas = {f"{a}__vs__{b}": [] for a, b in PAIRS}
    vote_deltas = {f"{a}__vs__{b}": [] for a, b in PAIRS}

    for seed, seat in CASES:
        candidate = play(seed, seat, True)
        cycles = cycles_from_trace({"whole_flow": candidate["flow_trace"]})
        slim = [serialize_cycle(c) for c in cycles]
        aftermath = observe_aftermath(slim)

        contrasts = {}
        for left, right in PAIRS:
            key = f"{left}__vs__{right}"
            if left not in aftermath or right not in aftermath:
                continue
            a, b = aftermath[left], aftermath[right]
            if a["mean"] is None or b["mean"] is None:
                continue
            d = delta(a["mean"], b["mean"])
            vd = a["positive_vote_mean"] - b["positive_vote_mean"]
            contrasts[key] = {
                "mean_delta_left_minus_right": d,
                "positive_vote_mean_delta": vd,
                "left_count": a["observed_count"],
                "right_count": b["observed_count"],
            }
            pair_deltas[key].append(d)
            vote_deltas[key].append(vd)

        battles.append({
            "seed": seed,
            "seat": seat,
            "cycle_count": len(cycles),
            "aftermath": aftermath,
            "contrasts": contrasts,
        })

    aggregate = {}
    for key in pair_deltas:
        if not pair_deltas[key]:
            continue
        aggregate[key] = {
            "battle_count": len(pair_deltas[key]),
            "mean_delta_across_battles": mean_dict(pair_deltas[key]),
            "positive_vote_mean_delta_across_battles": sum(vote_deltas[key]) / len(vote_deltas[key]),
            "status": "multi_battle_descriptive_contrast",
            "causal_attribution": False,
            "promote": False,
        }

    result = {
        "schema": "kaggriculture.multi-battle-boundary-aftermath.v1",
        "cases": [{"seed": s, "seat": t} for s, t in CASES],
        "battles": battles,
        "aggregate_contrasts": aggregate,
        "boundary": "descriptive_only_no_causal_attribution_no_rule_promotion",
    }
    Path("multi_battle_boundary_aftermath.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({
        "cases": result["cases"],
        "aggregate_contrasts": aggregate,
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
