#!/usr/bin/env python3
"""Shadow observer for WHEAT inventory growth points between turn 2 and 120.

A market snapshot at turn t is observed before turn-t actions execute, so a delta
change visible at t is paired with the actions emitted at t-1.  This observer
extracts only those transitions where Full-v1 minus baseline WHEAT inventory
becomes more negative (the observed divergence grows).  It records both self and
opponent actions for baseline and candidate without changing either policy.
"""
import importlib.util
import json
from pathlib import Path
from kaggle_environments import make
import strong_origin_g5_roi as baseline_agent
import full_strong_origin_v1 as candidate_agent

OPPONENT_PATH = "opponents/seyamalam_v21.py"
CASES = ((3514,0),(3528,0),(3530,0),(3554,0),(3561,1))
END = 120


def load_opponent(tag):
    spec = importlib.util.spec_from_file_location(f"seyamalam_v21_growth_{tag}", OPPONENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent


def play(seed, seat, self_module, tag):
    self_module.reset_telemetry()
    self_trace = []
    opp_trace = []
    opp_agent = load_opponent(tag)
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def self_wrapped(obs):
        t = len(self_trace)
        action = self_module.agent(obs)
        market = obs.get("market", {})
        self_trace.append({
            "turn": t,
            "day": obs.get("day"),
            "wheat_inventory": market.get("inventory", {}).get("WHEAT"),
            "wheat_price": market.get("prices", {}).get("WHEAT"),
            "action": action,
        })
        return action

    def opp_wrapped(obs):
        t = len(opp_trace)
        action = opp_agent(obs)
        opp_trace.append({"turn": t, "action": action})
        return action

    players = [opp_wrapped, opp_wrapped]
    players[seat] = self_wrapped
    players[1-seat] = opp_wrapped
    env.run(players)
    return self_trace, opp_trace


def compact_action(a):
    if a is None:
        return None
    # Keep the raw three-lane action shape; JSON output is the evidence.
    return a


def main():
    cases = []
    for seed, seat in CASES:
        b_self, b_opp = play(seed, seat, baseline_agent, f"b{seed}_{seat}")
        c_self, c_opp = play(seed, seat, candidate_agent, f"c{seed}_{seat}")
        n = min(len(b_self), len(c_self), END + 1)

        series = []
        for t in range(n):
            bi = b_self[t]["wheat_inventory"]
            ci = c_self[t]["wheat_inventory"]
            d = None if bi is None or ci is None else ci - bi
            series.append({
                "turn": t,
                "day": b_self[t]["day"],
                "baseline_inventory": bi,
                "candidate_inventory": ci,
                "delta": d,
                "baseline_price": b_self[t]["wheat_price"],
                "candidate_price": c_self[t]["wheat_price"],
            })

        growth = []
        contraction = []
        for t in range(3, n):
            prev = series[t-1]["delta"]
            cur = series[t]["delta"]
            if prev is None or cur is None or cur == prev:
                continue
            row = {
                "state_turn": t,
                "day": series[t]["day"],
                "action_turn": t-1,
                "delta_before": prev,
                "delta_after": cur,
                "delta_step": cur - prev,
                "baseline_self_action": compact_action(b_self[t-1]["action"]),
                "candidate_self_action": compact_action(c_self[t-1]["action"]),
                "baseline_opponent_action": compact_action(b_opp[t-1]["action"]) if t-1 < len(b_opp) else None,
                "candidate_opponent_action": compact_action(c_opp[t-1]["action"]) if t-1 < len(c_opp) else None,
                "opponent_action_equal": (b_opp[t-1]["action"] == c_opp[t-1]["action"]) if t-1 < len(b_opp) and t-1 < len(c_opp) else None,
                "baseline_price_after": series[t]["baseline_price"],
                "candidate_price_after": series[t]["candidate_price"],
            }
            if cur < prev:
                growth.append(row)
            else:
                contraction.append(row)

        cases.append({
            "seed": seed,
            "seat": seat,
            "turn2_delta": series[2]["delta"],
            "turn120_delta": series[120]["delta"] if len(series) > 120 else None,
            "growth_point_count": len(growth),
            "contraction_point_count": len(contraction),
            "first_growth": growth[0] if growth else None,
            "growth_points": growth,
            "contraction_points": contraction,
        })

    result = {
        "schema": "kaggriculture.full-v1-wheat-growth-points.v1",
        "observer_only": True,
        "agent_mutated": False,
        "timing_rule": "state delta at turn t is paired with actions at turn t-1",
        "cases": cases,
    }
    Path("full_v1_wheat_growth_points.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )

    compact = []
    for r in cases:
        fg = r["first_growth"]
        compact.append({
            "seed": r["seed"],
            "turn2": r["turn2_delta"],
            "turn120": r["turn120_delta"],
            "growth_count": r["growth_point_count"],
            "contraction_count": r["contraction_point_count"],
            "first_growth": None if fg is None else {
                "state_turn": fg["state_turn"],
                "action_turn": fg["action_turn"],
                "before": fg["delta_before"],
                "after": fg["delta_after"],
                "step": fg["delta_step"],
                "opp_equal": fg["opponent_action_equal"],
                "b_self": fg["baseline_self_action"],
                "c_self": fg["candidate_self_action"],
                "b_opp": fg["baseline_opponent_action"],
                "c_opp": fg["candidate_opponent_action"],
            },
        })
    print("WHEAT_GROWTH_POINTS " + json.dumps(compact, separators=(",", ":")))


if __name__ == "__main__":
    main()
