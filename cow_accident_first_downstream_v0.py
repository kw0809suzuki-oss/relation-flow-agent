#!/usr/bin/env python3
"""COW accident first downstream transformation observer.

Question:
After the common Day0 COW suppression, where do accident cases
4404/4407/4409 first diverge downstream from their own baseline,
and is that first downstream transformation shared with the improved cases?

No new rule is proposed here.
"""

import copy
import json
import os

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import cow_first_purchase_suppress_v0 as candidate

OPPONENT = base.OPPONENT
CASES = [(4402 + i, i % 2) for i in range(10)]
ACCIDENTS = {4404, 4407, 4409}
IMPROVED = {4402, 4403, 4405, 4408, 4410, 4411}


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
    return {
        "trace": trace,
        "self": rewards[seat],
    }


def canon_action(a):
    return json.dumps(a, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def first_downstream_divergence(bt, ct):
    n = min(len(bt), len(ct))
    first = None
    for i in range(n):
        if canon_action(bt[i]["action"]) != canon_action(ct[i]["action"]):
            first = i
            break
    if first is None:
        return None

    # first difference is the intervention itself. Find the next actual action divergence.
    for i in range(first + 1, n):
        if canon_action(bt[i]["action"]) != canon_action(ct[i]["action"]):
            return {
                "intervention_turn": first,
                "turn": i,
                "day": ct[i]["day"],
                "baseline_action": bt[i]["action"],
                "candidate_action": ct[i]["action"],
            }
    return {
        "intervention_turn": first,
        "turn": None,
        "day": None,
        "baseline_action": None,
        "candidate_action": None,
    }


def action_signature(row):
    if not row or row["turn"] is None:
        return "none"
    return json.dumps({
        "baseline": row["baseline_action"],
        "candidate": row["candidate_action"],
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def main():
    rows = []
    for seed, seat in CASES:
        b = play(baseline.agent, seed, seat)
        c = play(candidate.agent, seed, seat, candidate.reset_experiment)
        div = first_downstream_divergence(b["trace"], c["trace"])
        sd = c["self"] - b["self"]
        rows.append({
            "seed": seed,
            "seat": seat,
            "class": "accident" if seed in ACCIDENTS else "improved" if seed in IMPROVED else "other",
            "self_diff": sd,
            "first_downstream_transformation": div,
            "signature": action_signature(div),
        })

    improved_sigs = {}
    accident_sigs = {}
    for r in rows:
        bucket = improved_sigs if r["class"] == "improved" else accident_sigs if r["class"] == "accident" else None
        if bucket is not None:
            bucket[r["signature"]] = bucket.get(r["signature"], 0) + 1

    out = {
        "schema": "cow-accident-first-downstream-transformation.v0",
        "question": "Where do 4404/4407/4409 first enter a different downstream transformation path after common Day0 COW suppression?",
        "rows": rows,
        "summary": {
            "improved_signature_counts": improved_sigs,
            "accident_signature_counts": accident_sigs,
        },
        "boundary": "This compares first post-intervention action divergence only. It does not create rescue conditions.",
    }

    with open("cow_accident_first_downstream_v0.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    compact = [{
        "seed": r["seed"],
        "class": r["class"],
        "self_diff": r["self_diff"],
        "turn": r["first_downstream_transformation"]["turn"] if r["first_downstream_transformation"] else None,
        "day": r["first_downstream_transformation"]["day"] if r["first_downstream_transformation"] else None,
        "baseline_action": r["first_downstream_transformation"]["baseline_action"] if r["first_downstream_transformation"] else None,
        "candidate_action": r["first_downstream_transformation"]["candidate_action"] if r["first_downstream_transformation"] else None,
    } for r in rows]

    print("COW_ACCIDENT_FIRST_DOWNSTREAM_ROWS " + json.dumps(compact, separators=(",", ":")))
    print("COW_ACCIDENT_FIRST_DOWNSTREAM_SUMMARY " + json.dumps(out["summary"], separators=(",", ":")))


if __name__ == "__main__":
    main()
