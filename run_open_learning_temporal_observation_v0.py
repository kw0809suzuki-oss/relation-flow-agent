#!/usr/bin/env python3
"""Open Learning temporal observation for seed 6201, Days 19-29.

Aggregate every agent call within each day. This is observation only:
no intervention and no claim that temporal_realization exists.
"""

import json
import os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state

SEED = 6201
SEAT = 0
START_DAY = 19
END_DAY = 29
OPPONENT = base.OPPONENT
OUT = Path("open_learning_temporal_observation_v0.json")


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def main():
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    by_day = defaultdict(lambda: {
        "calls": 0,
        "first_state": None,
        "last_state": None,
        "actions": [],
    })

    def observed_agent(obs):
        day = int(obs.get("day", 0) or 0)
        state = observe_state(obs)
        actions = combat.agent(obs)

        if START_DAY <= day <= END_DAY:
            rec = by_day[day]
            rec["calls"] += 1
            if rec["first_state"] is None:
                rec["first_state"] = state
            rec["last_state"] = state
            rec["actions"].append(actions)
        return actions

    players = [OPPONENT, OPPONENT]
    players[SEAT] = observed_agent
    env.run(players)
    rewards = [float(s.reward) for s in env.state]

    rows = []
    prev_last_money = None
    for day in range(START_DAY, END_DAY + 1):
        rec = by_day.get(day)
        if not rec:
            continue
        first = rec["first_state"]
        last = rec["last_state"]
        first_money = first["money"]["self"]
        last_money = last["money"]["self"]

        market_actions = []
        farm_actions = []
        all_raw = []
        for a in rec["actions"]:
            all_raw.append(a)
            if isinstance(a, dict):
                market_actions.extend(list(a.get("market", []) or []))
                farm_actions.extend(list(a.get("farm", []) or []))

        rows.append({
            "day": day,
            "remaining": first["time"]["remaining_days"],
            "calls": rec["calls"],
            "money_first_call": first_money,
            "money_last_call": last_money,
            "money_change_within_observed_day": last_money - first_money,
            "money_change_vs_prev_day_last": None if prev_last_money is None else first_money - prev_last_money,
            "first_capacity": first["capacity"],
            "last_capacity": last["capacity"],
            "first_flow_inputs": first["flow_inputs"],
            "last_flow_inputs": last["flow_inputs"],
            "first_flow_outputs": first["flow_outputs"],
            "last_flow_outputs": last["flow_outputs"],
            "first_work_state": first["work_state"],
            "last_work_state": last["work_state"],
            "market_actions": market_actions,
            "farm_actions": farm_actions,
            "action_call_count": len(rec["actions"]),
        })
        prev_last_money = last_money

    payload = {
        "schema": "kaggriculture.open-learning-temporal-observation.v0.1",
        "case": {"seed": SEED, "seat": SEAT},
        "window": [START_DAY, END_DAY],
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1-SEAT],
            "margin": rewards[SEAT] - rewards[1-SEAT],
        },
        "rows": rows,
        "boundary": [
            "No intervention is applied.",
            "All agent calls inside each day are aggregated.",
            "This observation does not establish temporal_realization.",
            "The existing taxonomy remains open.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OPEN_LEARNING_TEMPORAL_ROWS " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
    print("OPEN_LEARNING_TEMPORAL_TERMINAL " + json.dumps(payload["terminal"], separators=(",", ":")))


if __name__ == "__main__":
    main()
