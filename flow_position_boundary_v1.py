#!/usr/bin/env python3
"""Flow Position Boundary Observer v1.

Compare the two observed downstream groups inside the dominant fresh30
WHEAT pickup 2->3 branch.  No policy mutation.  Re-run only the 13 selected
cases and retain existing G15 snapshots around the branch so we can ask:
where do the groups first differ in latent/internal/reachability-relevant state?
"""
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

LAND_GROUP = {(4129,1),(4130,0),(4131,1),(4147,1),(4149,1),(4151,1),(4158,0)}
SEED3_GROUP = {(4142,0),(4143,1),(4144,0),(4152,0),(4156,0),(4161,1)}
CASES = sorted(LAND_GROUP | SEED3_GROUP)
OPPONENT = base.OPPONENT
START_TURN = 72
END_TURN = 122

def compact_snapshot(s):
    oi = s.get("origin_internal", {}) or {}
    gc = s.get("gate_conditions", {}) or {}
    return {
        "turn": s.get("turn"),
        "day": s.get("day"),
        "money": s.get("money"),
        "units": s.get("units"),
        "cows": s.get("cows"),
        "wheat": s.get("wheat"),
        "land": s.get("land"),
        "feed_need": s.get("feed_need"),
        "remaining": s.get("remaining"),
        "mode": s.get("mode"),
        "target": s.get("target"),
        "feed_carry": s.get("feed_carry"),
        "raw_opportunity": s.get("raw_opportunity"),
        "opportunity": s.get("opportunity"),
        "gate_margin": s.get("gate_margin"),
        "probe_age": gc.get("probe_age"),
        "cooldown": gc.get("cooldown"),
        "resonance_pass": gc.get("resonance_pass"),
        "money_pass": gc.get("money_pass"),
        "remaining_pass": gc.get("remaining_pass"),
        "strategy_name": oi.get("strategy_name"),
        "targets": oi.get("targets"),
        "market": oi.get("market"),
        "farmer_action": oi.get("farmer_action"),
        "hand_actions": oi.get("hand_actions"),
        "unit_pos_sig": s.get("unit_pos_sig"),
        "shed_sig": s.get("shed_sig"),
        "inv_sig": s.get("inv_sig"),
        "tile_sig": s.get("tile_sig"),
        "action": s.get("action"),
        "base_action": s.get("base_action"),
    }

def g15_snapshots(trace):
    # whole_flow -> g17(body) -> g16(observe) -> g15(body)
    return trace["body"]["observe"]["body"]["snapshots"]

def play(seed, seat, enabled):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1" if enabled else "0"
    agent.reset_telemetry()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        return agent.agent(obs)

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    snaps = [
        compact_snapshot(s)
        for s in g15_snapshots(agent.get_trace())
        if START_TURN <= int(s.get("turn", -1)) <= END_TURN
    ]
    return {
        "terminal_self": rewards[seat],
        "terminal_opp": rewards[1-seat],
        "snapshots": snaps,
    }

def main():
    rows = []
    for seed, seat in CASES:
        b = play(seed, seat, False)
        c = play(seed, seat, True)
        group = "land_reinvest" if (seed,seat) in LAND_GROUP else "seed3"
        rows.append({
            "seed": seed,
            "seat": seat,
            "group": group,
            "baseline": b,
            "control": c,
            "self_diff": c["terminal_self"] - b["terminal_self"],
            "margin_diff": (c["terminal_self"]-c["terminal_opp"]) - (b["terminal_self"]-b["terminal_opp"]),
        })
    out = {
        "schema": "flow-position-boundary.v1",
        "policy_mutated": False,
        "question": "Where do the two downstream groups first differ before the common WHEAT pickup 2->3 divergence?",
        "selection": {
            "land_reinvest": sorted([list(x) for x in LAND_GROUP]),
            "seed3": sorted([list(x) for x in SEED3_GROUP]),
            "selection_basis": "observed downstream sequence in Transition Sequence Observer v1; not a causal label",
        },
        "turn_window": [START_TURN, END_TURN],
        "cases": rows,
        "boundary": "internal fields are descriptive implementation state; a separating field is not automatically causal or a complete reachable-action set",
    }
    Path("flow_position_boundary_v1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("FLOW_POSITION_BOUNDARY_V1 " + json.dumps({
        "cases": len(rows),
        "land_reinvest": sum(r["group"]=="land_reinvest" for r in rows),
        "seed3": sum(r["group"]=="seed3" for r in rows),
        "turn_window": [START_TURN, END_TURN],
    }, separators=(",",":")))

if __name__ == "__main__":
    main()
