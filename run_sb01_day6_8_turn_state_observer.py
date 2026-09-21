#!/usr/bin/env python3
"""Turn-level public-state transition observer for SB-01 Day 6->8.

Observation-only. No strategy, rule, threshold, or candidate is changed.
Captures every self observation from Day 6 through Day 8 and records
public farm structure for both players plus money/margin.
"""
import json
import os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OPPONENT = base.OPPONENT
OUT = Path(f"sb01_day6_8_turn_state_{SEED}.json")


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def pub(farm):
    crops, animals = {}, {}
    active_tiles = 0
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if tile == "LOCKED" or tile is None:
                continue
            active_tiles += 1
            if isinstance(tile, dict):
                c = tile.get("crop")
                a = tile.get("animal")
                if c:
                    crops[c] = crops.get(c, 0) + 1
                if a:
                    animals[a] = animals.get(a, 0) + 1
    return {
        "active_tiles": active_tiles,
        "unlocked_quadrants": len(farm.get("unlocked_quadrants", []) or []),
        "hands": len(farm.get("hands", []) or []),
        "crops": crops,
        "crop_total": sum(crops.values()),
        "animals": animals,
        "animal_total": sum(animals.values()),
        "production_asset_count": sum(crops.values()) + sum(animals.values()),
    }


def main():
    configure()
    events = []
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [OPPONENT, OPPONENT]

    def observed(obs):
        day = int(obs.get("day", 0) or 0)
        if 6 <= day <= 8:
            p = int(obs["player"])
            me = obs["farms"][p]
            op = obs["farms"][1-p]
            sm = float(me.get("money", 0) or 0)
            om = float(op.get("money", 0) or 0)
            events.append({
                "day": day,
                "turn": int(obs.get("turn", len(events)) or 0),
                "self_money": sm,
                "opponent_money": om,
                "money_margin": sm - om,
                "self_public": pub(me),
                "opponent_public": pub(op),
            })
        return combat.agent(obs)

    players[SEAT] = observed
    env.run(players)

    transitions = []
    prev = None
    for e in events:
        if prev is not None:
            for side in ("self_public", "opponent_public"):
                a = prev[side]
                b = e[side]
                if (
                    a["unlocked_quadrants"] != b["unlocked_quadrants"]
                    or a["active_tiles"] != b["active_tiles"]
                    or a["production_asset_count"] != b["production_asset_count"]
                    or a["crops"] != b["crops"]
                    or a["animals"] != b["animals"]
                ):
                    transitions.append({
                        "side": side.replace("_public",""),
                        "from_day": prev["day"],
                        "from_turn": prev["turn"],
                        "to_day": e["day"],
                        "to_turn": e["turn"],
                        "before": a,
                        "after": b,
                        "money_margin_before": prev["money_margin"],
                        "money_margin_after": e["money_margin"],
                    })
        prev = e

    payload = {
        "schema": "kaggriculture.sb01.day6-8-turn-public-state.v0",
        "probe": "Remaining Strength Gap Day6-8 Turn State",
        "mode": "observation_only_replay",
        "seed": SEED,
        "seat": SEAT,
        "snapshot": "SB-01",
        "events": events,
        "transitions": transitions,
        "boundary": [
            "No strategy, rule, threshold, or candidate is changed.",
            "Uses exact fixed SB-01 seed/seat/opponent/runtime conditions.",
            "Only public state visible to the self observation stream is recorded.",
            "The probe localizes the earliest public-state jump in Day 6-8; it does not establish cause."
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SB01_DAY6_8_TURN_STATE_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
