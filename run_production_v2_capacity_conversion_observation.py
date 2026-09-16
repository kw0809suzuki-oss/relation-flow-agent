#!/usr/bin/env python3
"""Observe whether Production v2 added capacity becomes real work.

Comparison only: Production v1 vs Production v2 on the same fresh 30 seeds.
Records day 7-12 hands and emitted action counts, then attaches terminal reward.
No observation value is fed back into either agent.
"""

import json
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import production_agent_v1 as v1
import production_agent_v2_capacity_bridge as v2

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3942) % 2) for seed in range(3942, 3972))
WATCH_DAYS = set(range(7, 13))


def action_counts(action):
    c = Counter()
    units = [action.get("farmer", ["PASS"]), *(action.get("hands", []) or [])]
    for a in units:
        if not a:
            continue
        k = a[0]
        if k in {"NORTH", "SOUTH", "EAST", "WEST"}:
            c["move"] += 1
        elif k in {"FEED", "CARE", "HARVEST", "DROP", "PICKUP", "DIG", "PLANT", "WATER", "PLACE", "BUILD_PASTURE", "COLLECT_FERTILIZER", "FERTILIZE"}:
            c["work"] += 1
            c[k.lower()] += 1
        elif k == "PASS":
            c["pass"] += 1
    for o in action.get("market", []) or []:
        if not o:
            continue
        if o[0] == "HIRE": c["hire"] += 1
        elif o[0] == "BUY_LAND": c["buy_land"] += 1
        elif o[0] == "SELL": c["sell_order"] += 1
    return c


def play(seed, seat, module):
    module.reset_telemetry()
    days = {}

    def wrapped(obs):
        action = module.agent(obs)
        day = int(obs.get("day", 0))
        if day in WATCH_DAYS:
            me = obs["farms"][int(obs["player"])]
            rec = days.setdefault(day, {"hands_samples": [], "actions": Counter()})
            rec["hands_samples"].append(len(me.get("hands", []) or []))
            rec["actions"].update(action_counts(action))
        return action

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = wrapped
    env.run(players)

    frozen = []
    for day in sorted(days):
        r = days[day]
        frozen.append({
            "day": day,
            "mean_hands": sum(r["hands_samples"]) / len(r["hands_samples"]) if r["hands_samples"] else 0.0,
            "actions": dict(r["actions"]),
        })

    rewards = [state.reward for state in env.state]
    return {
        "days": frozen,
        "terminal": {
            "self": float(rewards[seat]),
            "opponent": float(rewards[1-seat]),
            "margin": float(rewards[seat]) - float(rewards[1-seat]),
            "win": float(rewards[seat]) > float(rewards[1-seat]),
        },
    }


def totals(case, key):
    return sum(d["actions"].get(key, 0) for d in case["days"])


def mean_hands(case):
    vals = [d["mean_hands"] for d in case["days"]]
    return sum(vals)/len(vals) if vals else 0.0


def main():
    rows = []
    for seed, seat in CASES:
        a = play(seed, seat, v1)
        b = play(seed, seat, v2)
        rows.append({
            "seed": seed,
            "seat": seat,
            "v1": a,
            "v2": b,
            "delta": {
                "mean_hands": mean_hands(b) - mean_hands(a),
                "work": totals(b, "work") - totals(a, "work"),
                "move": totals(b, "move") - totals(a, "move"),
                "plant": totals(b, "plant") - totals(a, "plant"),
                "water": totals(b, "water") - totals(a, "water"),
                "care": totals(b, "care") - totals(a, "care"),
                "feed": totals(b, "feed") - totals(a, "feed"),
                "harvest": totals(b, "harvest") - totals(a, "harvest"),
                "self": b["terminal"]["self"] - a["terminal"]["self"],
                "margin": b["terminal"]["margin"] - a["terminal"]["margin"],
            },
        })

    keys = ["mean_hands", "work", "move", "plant", "water", "care", "feed", "harvest", "self", "margin"]
    summary = {"cases": len(rows)}
    for k in keys:
        vals = [r["delta"][k] for r in rows]
        summary[f"mean_delta_{k}"] = sum(vals)/len(vals)
        summary[f"positive_{k}"] = sum(v > 0 for v in vals)
        summary[f"negative_{k}"] = sum(v < 0 for v in vals)

    out = {
        "schema": "kaggriculture.production-v2-capacity-conversion-observation.v1",
        "observer_only": True,
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
        "terminal_attached_after_trace": True,
        "watch_days": sorted(WATCH_DAYS),
        "rows": rows,
        "summary": summary,
        "causal_attribution": False,
    }
    Path("production_v2_capacity_conversion_observation.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print("PRODUCTION_V2_CAPACITY_CONVERSION " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
