#!/usr/bin/env python3
"""Open Learning temporal observation for seed 6201, Days 19-29.

Records only the action/economic series needed to test whether the unknown case
looks like a single bad choice or an unresolved multi-day realization problem.
No intervention is applied.
"""

import json
import os
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


def money_changing_market(action):
    if not isinstance(action, (list, tuple)) or not action:
        return False
    op = action[0]
    return op in {
        "BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT", "BUY_LAND",
        "SELL_PRODUCT", "SELL_CROP", "SELL", "HIRE", "FIRE"
    }


def action_bucket(actions):
    if not isinstance(actions, dict):
        return {"market": [], "farm": [], "raw": actions}
    market = list(actions.get("market", []) or [])
    farm = list(actions.get("farm", []) or [])
    return {
        "market": market,
        "money_changing_market": [a for a in market if money_changing_market(a)],
        "farm": farm,
    }


def main():
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    rows = []
    last_money = None
    last_day = None

    def observed_agent(obs):
        nonlocal last_money, last_day
        day = int(obs.get("day", 0) or 0)
        me = obs["farms"][obs["player"]]
        before_money = float(me.get("money", 0) or 0)
        state = observe_state(obs)
        actions = combat.agent(obs)
        if START_DAY <= day <= END_DAY and day != last_day:
            rows.append({
                "day": day,
                "remaining": state["time"]["remaining_days"],
                "money_before_action": before_money,
                "money_delta_from_prev_day": None if last_money is None else before_money - last_money,
                "capacity": state["capacity"],
                "flow_inputs": state["flow_inputs"],
                "flow_outputs": state["flow_outputs"],
                "work_state": state["work_state"],
                "actions": action_bucket(actions),
            })
            last_day = day
        if START_DAY <= day <= END_DAY:
            last_money = before_money
        return actions

    players = [OPPONENT, OPPONENT]
    players[SEAT] = observed_agent
    env.run(players)
    rewards = [float(s.reward) for s in env.state]

    payload = {
        "schema": "kaggriculture.open-learning-temporal-observation.v0",
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
            "This observation does not establish temporal_realization.",
            "The existing taxonomy remains open.",
            "Only Days 19-29 and the action/economic sequence needed for the next discrimination are retained.",
        ],
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OPEN_LEARNING_TEMPORAL_ROWS " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
    print("OPEN_LEARNING_TEMPORAL_TERMINAL " + json.dumps(payload["terminal"], separators=(",", ":")))


if __name__ == "__main__":
    main()
