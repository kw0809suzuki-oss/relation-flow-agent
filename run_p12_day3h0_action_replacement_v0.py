#!/usr/bin/env python3
"""First-divergence intervention at Day3 Hour0 for P12.

Intervention:
1. Replay current WR-02 and record the selected agent's actual submitted action
   at Day3 Hour0 for this same seed/seat.
2. Replay normal P12.
3. Replay P12 again, but at Day3 Hour0 replace only the selected agent's
   submitted action with the recorded current-world action.
4. Observe Day3 Hour1 MILK market state and terminal score.

This is a causal probe of that one submitted action as a lever. It does not
explain the action's contents or attribute opponent/resolver behavior.
"""
import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as current
import wr02_p12_day0_reservation_v0 as candidate

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"p12_day3h0_action_replacement_v0_{SEED}_seat{SEAT}.json")
TARGET = (3, 0)
OBSERVE = (3, 1)


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def jsonable(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def market_milk(obs):
    market = obs.get("market", {}) or {}
    inv = market.get("inventory", {}) or {}
    prices = market.get("prices", {}) or {}
    return {
        "inventory": float(inv.get("MILK", 0) or 0),
        "price": float(prices.get("MILK", 0) or 0),
    }


def play(module, replacement=None):
    configure()
    module.reset_telemetry()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    target_action = None
    observed_h1 = None

    def observed(obs):
        nonlocal target_action, observed_h1
        action = module.agent(obs)
        point = (int(obs.get("day", 0) or 0), int(obs.get("hour", 0) or 0))
        if point == TARGET:
            target_action = jsonable(action)
            if replacement is not None:
                return copy.deepcopy(replacement)
        if point == OBSERVE:
            observed_h1 = market_milk(obs)
        return action

    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[SEAT] = observed
    env.run(players)
    rewards = [float(x.reward) for x in env.state]
    return {
        "target_action_generated": target_action,
        "day3_hour1_market": observed_h1,
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
    }


def main():
    baseline = play(current)
    normal = play(candidate)
    replacement_action = baseline["target_action_generated"]
    replaced = play(candidate, replacement=replacement_action)

    payload = {
        "schema": "kaggriculture.p12-day3h0-action-replacement.v0",
        "seed": SEED,
        "seat": SEAT,
        "current": baseline,
        "p12_normal": normal,
        "p12_replaced": replaced,
        "replacement": {
            "source": "current WR-02 selected-agent submitted action at same seed/seat Day3 Hour0",
            "target": "P12 selected-agent submitted action at Day3 Hour0",
            "action_changed": replacement_action != normal["target_action_generated"],
        },
        "comparisons": {
            "normal_delta_self": normal["terminal"]["self"] - baseline["terminal"]["self"],
            "replaced_delta_self": replaced["terminal"]["self"] - baseline["terminal"]["self"],
            "replacement_terminal_effect": replaced["terminal"]["self"] - normal["terminal"]["self"],
            "normal_h1_inventory_delta": normal["day3_hour1_market"]["inventory"] - baseline["day3_hour1_market"]["inventory"],
            "replaced_h1_inventory_delta": replaced["day3_hour1_market"]["inventory"] - baseline["day3_hour1_market"]["inventory"],
            "normal_h1_price_delta": normal["day3_hour1_market"]["price"] - baseline["day3_hour1_market"]["price"],
            "replaced_h1_price_delta": replaced["day3_hour1_market"]["price"] - baseline["day3_hour1_market"]["price"],
        },
        "boundary": [
            "Exactly one selected-agent submitted action is replaced: Day3 Hour0.",
            "The replacement action comes from the separate current-world replay for the same seed/seat.",
            "Opponent policy is not replaced.",
            "The environment may process a transplanted action differently in the P12 world.",
            "A terminal response establishes sensitivity to this intervention, not a complete mechanism.",
            "No action-content explanation is made by this probe.",
        ],
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("P12_DAY3H0_ACTION_REPLACEMENT " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "action_changed": payload["replacement"]["action_changed"],
        **payload["comparisons"],
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
