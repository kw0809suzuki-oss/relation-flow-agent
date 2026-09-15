#!/usr/bin/env python3
"""50-game wide comparison: Production Agent v1 vs pinned Seyamalam.

Observation only. Builds a day-level comparison surface from public farm state,
market state, both agents' emitted actions, and self private queue state.
Terminal reward is attached only after the comparison trace is frozen.
No Bundle value is fed back into either agent.
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


def load_opponent():
    spec = importlib.util.spec_from_file_location("seyamalam_v21_wide", OPPONENT_PATH)
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
        "animals": dict(animals),
        "animal_total": sum(animals.values()),
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
    produce_inventory = sum(inv.get(k, 0) for k in ("MILK", "WOOL", "EGG", "FERTILIZER"))
    return {
        "wheat": inv.get("WHEAT", 0),
        "produce_inventory": produce_inventory,
        "cows": cows,
        "unfed_cows": unfed,
        "care_wait_cows": care_wait,
        "harvest_ready_cows": harvest_ready,
    }


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
            c[k.lower()] += 1
            c["work"] += 1
        elif k == "PASS":
            c["pass"] += 1
    for o in action.get("market", []) or []:
        if not o:
            continue
        if o[0] == "SELL": c["sell_order"] += 1
        elif o[0] == "BUY_PRODUCT" and len(o) > 1 and o[1] == "WHEAT": c["buy_wheat"] += 1
        elif o[0] == "BUY_ANIMAL": c["buy_animal"] += 1
        elif o[0] == "HIRE": c["hire"] += 1
        elif o[0] == "BUY_LAND": c["buy_land"] += 1
    return c


def play(seed, seat):
    self_agent.reset_telemetry()
    opponent_fn = load_opponent()
    days = {}
    self_turn = 0
    opp_turn = 0

    def record(day, who, obs, action, turn):
        rec = days.setdefault(int(day), {
            "day": int(day),
            "self_public": None,
            "opponent_public": None,
            "self_private": None,
            "market": None,
            "self_actions": Counter(),
            "opponent_actions": Counter(),
            "last_turn": 0,
        })
        p = int(obs["player"])
        me = public_state(obs["farms"][p])
        other = public_state(obs["farms"][1-p])
        if who == "self":
            rec["self_public"] = me
            rec["opponent_public"] = other
            rec["self_private"] = self_private_state(obs)
            rec["self_actions"].update(action_counts(action))
        else:
            rec["opponent_public"] = me
            rec["self_public"] = other
            rec["opponent_actions"].update(action_counts(action))
        market = obs.get("market", {}) or {}
        rec["market"] = {
            "prices": copy.deepcopy(market.get("prices", {}) or {}),
            "inventory": copy.deepcopy(market.get("inventory", {}) or {}),
        }
        rec["last_turn"] = max(rec["last_turn"], turn)

    def self_wrapped(obs):
        nonlocal self_turn
        action = self_agent.agent(obs)
        record(obs.get("day", 0), "self", obs, action, self_turn)
        self_turn += 1
        return action

    def opp_wrapped(obs):
        nonlocal opp_turn
        action = opponent_fn(obs)
        record(obs.get("day", 0), "opponent", obs, action, opp_turn)
        opp_turn += 1
        return action

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [opp_wrapped, opp_wrapped]
    players[seat] = self_wrapped
    env.run(players)

    frozen_days = []
    for day in sorted(days):
        r = days[day]
        frozen_days.append({
            "day": day,
            "last_turn": r["last_turn"],
            "self_public": r["self_public"],
            "opponent_public": r["opponent_public"],
            "self_private": r["self_private"],
            "market": r["market"],
            "self_actions": dict(r["self_actions"]),
            "opponent_actions": dict(r["opponent_actions"]),
        })

    # Freeze observation first, then read terminal reward.
    rewards = [state.reward for state in env.state]
    terminal = {
        "self": float(rewards[seat]),
        "opponent": float(rewards[1-seat]),
        "margin": float(rewards[seat]) - float(rewards[1-seat]),
        "win": float(rewards[seat]) > float(rewards[1-seat]),
    }
    return {"seed": seed, "seat": seat, "days": frozen_days, "terminal": terminal}


def main():
    cases = [play(seed, seat) for seed, seat in CASES]
    result = {
        "schema": "kaggriculture.production-wide-compare-50.v1",
        "observer_only": True,
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
        "terminal_attached_after_trace": True,
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "wins": sum(c["terminal"]["win"] for c in cases),
            "mean_self": sum(c["terminal"]["self"] for c in cases)/len(cases),
            "mean_opponent": sum(c["terminal"]["opponent"] for c in cases)/len(cases),
            "mean_margin": sum(c["terminal"]["margin"] for c in cases)/len(cases),
        },
    }
    Path("production_wide_compare_50.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("PRODUCTION_WIDE_COMPARE_50 " + json.dumps(result["summary"], separators=(",", ":")))


if __name__ == "__main__":
    main()
