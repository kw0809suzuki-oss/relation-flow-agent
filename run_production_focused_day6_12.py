#!/usr/bin/env python3
"""Focused turn-level observation for the Day 6-12 production window.

Observation only. Compares Production Agent v1 and pinned Seyamalam turn by turn
inside the wide-run boundary window. No observed value feeds back into control.
Terminal reward is attached only after the trace is frozen.
"""

import copy
import importlib.util
import json
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import production_agent_v1 as self_agent

OPPONENT_PATH = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3862) % 2) for seed in range(3862, 3912))
DAY_MIN, DAY_MAX = 6, 12


def load_opponent():
    spec = importlib.util.spec_from_file_location("seyamalam_v21_focus", OPPONENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, "agent", None)
    if fn is None:
        raise RuntimeError("Pinned opponent module has no agent()")
    return fn


def public_state(farm):
    animals = Counter()
    active = planted = 0
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if tile in (None, "LOCKED"):
                continue
            active += 1
            if isinstance(tile, dict):
                if tile.get("animal"):
                    animals[str(tile.get("animal"))] += 1
                if tile.get("crop") or tile.get("plant"):
                    planted += 1
    return {
        "money": float(farm.get("money", 0)),
        "hands": len(farm.get("hands", []) or []),
        "land": len(farm.get("unlocked_quadrants", []) or []),
        "active_tiles": active,
        "planted_tiles": planted,
        "animal_total": sum(animals.values()),
        "animals": dict(animals),
    }


def self_private_state(obs):
    private = obs.get("private", {}) or {}
    shed = private.get("shed", {}) or {}
    invs = private.get("inventories", []) or []
    inv = Counter(shed)
    for x in invs:
        inv.update(x or {})
    me = obs["farms"][int(obs["player"])]
    cows = unfed = care_wait = harvest_ready = 0
    for row in me.get("tiles", []) or []:
        for tile in row:
            if not isinstance(tile, dict) or tile.get("animal") != "COW":
                continue
            cows += 1
            if not tile.get("fed_today", False):
                unfed += 1
            elif not tile.get("cared_today", False):
                care_wait += 1
            if tile.get("yield_units", 0) > 0:
                harvest_ready += 1
    return {
        "wheat": inv.get("WHEAT", 0),
        "produce_inventory": sum(inv.get(k, 0) for k in ("MILK", "WOOL", "EGG", "FERTILIZER")),
        "cows": cows,
        "unfed_cows": unfed,
        "care_wait_cows": care_wait,
        "harvest_ready_cows": harvest_ready,
    }


def action_surface(action):
    counts = Counter()
    units = [action.get("farmer", ["PASS"]), *(action.get("hands", []) or [])]
    for a in units:
        if not a:
            continue
        k = a[0]
        if k in {"NORTH", "SOUTH", "EAST", "WEST"}:
            counts["move"] += 1
        elif k in {"FEED", "CARE", "HARVEST", "DROP", "PICKUP", "DIG", "PLANT", "WATER", "PLACE", "BUILD_PASTURE", "COLLECT_FERTILIZER", "FERTILIZE"}:
            counts[k.lower()] += 1
            counts["work"] += 1
        elif k == "PASS":
            counts["pass"] += 1
    for o in action.get("market", []) or []:
        if not o:
            continue
        if o[0] == "SELL": counts["sell_order"] += 1
        elif o[0] == "BUY_PRODUCT" and len(o) > 1 and o[1] == "WHEAT": counts["buy_wheat"] += 1
        elif o[0] == "BUY_ANIMAL": counts["buy_animal"] += 1
        elif o[0] == "HIRE": counts["hire"] += 1
        elif o[0] == "BUY_LAND": counts["buy_land"] += 1
    return dict(counts)


def snapshot(obs, action, who, local_turn):
    p = int(obs["player"])
    day = int(obs.get("day", 0))
    rec = {
        "day": day,
        "turn": local_turn,
        "who": who,
        "self_public": public_state(obs["farms"][p] if who == "self" else obs["farms"][1-p]),
        "opponent_public": public_state(obs["farms"][1-p] if who == "self" else obs["farms"][p]),
        "action": copy.deepcopy(action),
        "action_surface": action_surface(action),
        "market": {
            "prices": copy.deepcopy((obs.get("market", {}) or {}).get("prices", {}) or {}),
            "inventory": copy.deepcopy((obs.get("market", {}) or {}).get("inventory", {}) or {}),
        },
    }
    if who == "self":
        rec["self_private"] = self_private_state(obs)
    return rec


def play(seed, seat):
    self_agent.reset_telemetry()
    opponent_fn = load_opponent()
    self_trace, opp_trace = [], []
    self_turn = opp_turn = 0

    def self_wrapped(obs):
        nonlocal self_turn
        action = self_agent.agent(obs)
        day = int(obs.get("day", 0))
        if DAY_MIN <= day <= DAY_MAX:
            self_trace.append(snapshot(obs, action, "self", self_turn))
        self_turn += 1
        return action

    def opp_wrapped(obs):
        nonlocal opp_turn
        action = opponent_fn(obs)
        day = int(obs.get("day", 0))
        if DAY_MIN <= day <= DAY_MAX:
            opp_trace.append(snapshot(obs, action, "opponent", opp_turn))
        opp_turn += 1
        return action

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [opp_wrapped, opp_wrapped]
    players[seat] = self_wrapped
    env.run(players)

    frozen = {"self": copy.deepcopy(self_trace), "opponent": copy.deepcopy(opp_trace)}
    rewards = [state.reward for state in env.state]
    terminal = {
        "self": float(rewards[seat]),
        "opponent": float(rewards[1-seat]),
        "margin": float(rewards[seat]) - float(rewards[1-seat]),
        "win": float(rewards[seat]) > float(rewards[1-seat]),
    }
    return {"seed": seed, "seat": seat, "trace": frozen, "terminal": terminal}


def main():
    cases = [play(seed, seat) for seed, seat in CASES]
    result = {
        "schema": "kaggriculture.production-focused-day6-12.v1",
        "observer_only": True,
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
        "terminal_attached_after_trace": True,
        "window": {"day_min": DAY_MIN, "day_max": DAY_MAX},
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "wins": sum(c["terminal"]["win"] for c in cases),
            "mean_self": sum(c["terminal"]["self"] for c in cases)/len(cases),
            "mean_opponent": sum(c["terminal"]["opponent"] for c in cases)/len(cases),
            "mean_margin": sum(c["terminal"]["margin"] for c in cases)/len(cases),
        },
    }
    Path("production_focused_day6_12.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("PRODUCTION_FOCUSED_DAY6_12 " + json.dumps(result["summary"], separators=(",", ":")))


if __name__ == "__main__":
    main()
