#!/usr/bin/env python3
"""Observation-only all-participant MILK action audit around P12 split.

Replays WR-02 and WR-02+P12 on the same Fresh20 cases.
Reads env.steps after completion so both players' submitted actions can be
observed without wrapping or mutating the opponent. The narrow window is
Day19 Hour16..18, because the first clean shared MILK separation is observed
at Day19 Hour17.

Boundary:
- actions_by_player are agent-submitted actions recorded in replay state.
- submission is not the same as resolver acceptance.
- environment effect is observed only through the next public market state.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as current
import wr02_p12_day0_reservation_v0 as candidate

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"p12_milk_action_audit_v0_{SEED}_seat{SEAT}.json")
TARGET_HOURS = {16, 17, 18}


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def jsonable(value):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except Exception:
        return str(value)


def state_obs(states):
    if not isinstance(states, list) or len(states) < 2:
        return {}
    st = states[SEAT]
    obs = getattr(st, "observation", None)
    if obs is None and isinstance(st, dict):
        obs = st.get("observation")
    return dict(obs) if obs is not None else {}


def state_actions(states):
    if not isinstance(states, list) or len(states) < 2:
        return []
    out = []
    for st in states:
        action = getattr(st, "action", None)
        if action is None and isinstance(st, dict):
            action = st.get("action")
        out.append(jsonable(action))
    return out


def market_state(obs):
    market = obs.get("market", {}) or {}
    inv = market.get("inventory", {}) or {}
    prices = market.get("prices", {}) or {}
    return {
        "milk_inventory": float(inv.get("MILK", 0) or 0),
        "milk_price": float(prices.get("MILK", 0) or 0),
    }


def sell_milk_units(action):
    total = 0.0
    if not isinstance(action, dict):
        return total
    for row in action.get("market", []) or []:
        if (
            isinstance(row, (list, tuple))
            and len(row) >= 3
            and row[0] == "SELL"
            and str(row[1]) == "MILK"
        ):
            total += float(row[2] or 0)
    return total


def play(module):
    configure()
    module.reset_telemetry()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[SEAT] = module.agent
    env.run(players)

    snapshots = []
    for step_index, states in enumerate(env.steps):
        obs = state_obs(states)
        if not obs:
            continue
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        snapshots.append({
            "step_index": step_index,
            "day": day,
            "hour": hour,
            "market": market_state(obs),
            "actions_by_player": state_actions(states),
        })

    transitions = []
    for before, after in zip(snapshots, snapshots[1:]):
        if before["day"] != 19 or before["hour"] not in TARGET_HOURS:
            continue
        actions = before["actions_by_player"]
        submitted = []
        for pid in range(2):
            action = actions[pid] if pid < len(actions) else None
            submitted.append({
                "player_id": pid,
                "role": "self" if pid == SEAT else "opponent",
                "market_actions": (
                    action.get("market", [])
                    if isinstance(action, dict)
                    else []
                ),
                "sell_milk_units": sell_milk_units(action),
                "raw_action": action,
            })
        transitions.append({
            "from_step_index": before["step_index"],
            "to_step_index": after["step_index"],
            "from_day": before["day"],
            "from_hour": before["hour"],
            "to_day": after["day"],
            "to_hour": after["hour"],
            "market_before": before["market"],
            "market_after": after["market"],
            "market_transition": {
                "milk_inventory": (
                    after["market"]["milk_inventory"]
                    - before["market"]["milk_inventory"]
                ),
                "milk_price": (
                    after["market"]["milk_price"]
                    - before["market"]["milk_price"]
                ),
            },
            "submitted_actions": submitted,
        })

    rewards = [float(x.reward) for x in env.state]
    return {
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "transitions": transitions,
    }


def main():
    baseline = play(current)
    p12 = play(candidate)
    payload = {
        "schema": "kaggriculture.p12-milk-action-audit.v0",
        "seed": SEED,
        "seat": SEAT,
        "current": baseline,
        "candidate": p12,
        "delta_self": p12["terminal"]["self"] - baseline["terminal"]["self"],
        "delta_margin": p12["terminal"]["margin"] - baseline["terminal"]["margin"],
        "boundary": [
            "Observation-only replay; no policy mutation.",
            "Both players' replay actions are agent-submitted actions, not confirmed resolver acceptance.",
            "Environment effect is observed through the next public MILK market state.",
            "Only Day19 Hour16..18 transitions are retained.",
            "No missing action or causal relation is inferred.",
        ],
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("P12_MILK_ACTION_AUDIT " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "delta_self": payload["delta_self"],
        "current_transitions": len(baseline["transitions"]),
        "candidate_transitions": len(p12["transitions"]),
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
