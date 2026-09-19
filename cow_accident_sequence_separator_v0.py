#!/usr/bin/env python3
"""COW accident sequence separator v0.

Single question:
After the common turn1 downstream transformation, at what first turn do
improved6 and accident3 stop sharing the same transformation sequence?

No rescue rule is created. If no near shared accident-only separator appears,
COW suppression remains a strong but unsafe lever and should be closed.
"""

import copy
import json
import os
from collections import Counter

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import cow_first_purchase_suppress_v0 as candidate

OPPONENT = base.OPPONENT
CASES = [(4402 + i, i % 2) for i in range(10)]
ACCIDENTS = {4404, 4407, 4409}
IMPROVED = {4402, 4403, 4405, 4408, 4410, 4411}
MAX_TURN = 24


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    baseline.set_control_enabled(False)
    baseline.set_probe_enabled(True)
    baseline.set_attribution_enabled(True)
    baseline.reset_telemetry()


def play(agent_fn, seed, seat, reset=None):
    configure()
    if reset:
        reset()
    trace = []
    turn = 0

    def wrapped(obs):
        nonlocal turn
        action = agent_fn(obs)
        trace.append({
            "turn": turn,
            "day": obs.get("day"),
            "action": copy.deepcopy(action),
        })
        turn += 1
        return action

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = wrapped
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return {"trace": trace, "self": rewards[seat]}


def canon(action):
    return json.dumps(action, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def main():
    rows = []
    per_case = {}

    for seed, seat in CASES:
        b = play(baseline.agent, seed, seat)
        c = play(candidate.agent, seed, seat, candidate.reset_experiment)
        n = min(len(b["trace"]), len(c["trace"]), MAX_TURN + 1)
        diffs = []
        for i in range(n):
            if canon(b["trace"][i]["action"]) != canon(c["trace"][i]["action"]):
                diffs.append({
                    "turn": i,
                    "day": c["trace"][i]["day"],
                    "baseline_action": b["trace"][i]["action"],
                    "candidate_action": c["trace"][i]["action"],
                    "signature": json.dumps({
                        "baseline": b["trace"][i]["action"],
                        "candidate": c["trace"][i]["action"],
                    }, sort_keys=True, ensure_ascii=False, separators=(",", ":")),
                })

        cls = "accident" if seed in ACCIDENTS else "improved" if seed in IMPROVED else "other"
        row = {
            "seed": seed,
            "seat": seat,
            "class": cls,
            "self_diff": c["self"] - b["self"],
            "diffs": diffs,
        }
        rows.append(row)
        per_case[seed] = row

    # Compare class signature sets turn-by-turn after turn1.
    turn_summary = []
    first_separator = None

    for turn in range(2, MAX_TURN + 1):
        improved = []
        accidents = []
        for r in rows:
            sig = next((d["signature"] for d in r["diffs"] if d["turn"] == turn), "NO_DIFF")
            if r["class"] == "improved":
                improved.append(sig)
            elif r["class"] == "accident":
                accidents.append(sig)

        imp_counts = Counter(improved)
        acc_counts = Counter(accidents)

        accident_common = accidents[0] if accidents and all(s == accidents[0] for s in accidents) else None
        improved_has_same = accident_common in imp_counts if accident_common is not None else False
        accident_only_common = accident_common is not None and not improved_has_same

        item = {
            "turn": turn,
            "improved_signature_counts": dict(imp_counts),
            "accident_signature_counts": dict(acc_counts),
            "accident_common_signature": accident_common,
            "accident_only_common": accident_only_common,
        }
        turn_summary.append(item)

        if first_separator is None and accident_only_common:
            first_separator = item

    out = {
        "schema": "cow-accident-sequence-separator.v0",
        "question": "Where do improved6 and accident3 first stop sharing the same transformation sequence after common turn1?",
        "max_turn_checked": MAX_TURN,
        "first_accident_only_common_separator": first_separator,
        "turn_summary": turn_summary,
        "cases": rows,
        "boundary": "No rescue rule is inferred. A separator is descriptive only.",
    }

    with open("cow_accident_sequence_separator_v0.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    compact = {
        "first_separator_turn": None if first_separator is None else first_separator["turn"],
        "found": first_separator is not None,
        "max_turn_checked": MAX_TURN,
    }
    print("COW_ACCIDENT_SEQUENCE_SEPARATOR_V0 " + json.dumps(compact, separators=(",", ":")))
    if first_separator is not None:
        print("COW_ACCIDENT_SEQUENCE_SEPARATOR_DETAIL " + json.dumps(first_separator, separators=(",", ":")))


if __name__ == "__main__":
    main()
