#!/usr/bin/env python3
"""STRAWBERRY carried-action bridge v0.

Same fixed five Battle / Day20->24 replay.
For each increase in opponent-minus-self STRAWBERRY carried quantity between
market-after -> next market-before, record the exact current unit action mapped
to every inventory index whose STRAWBERRY quantity changed.

This is an observation bridge, not a policy diagnosis.
"""
import hashlib
import inspect
import json
import os
from collections import defaultdict
from pathlib import Path

import kaggle_environments
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as body_only

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"battle_value_strawberry_action_bridge_v0_{SEED}_seat{SEAT}.json")

events = []
_last_after = None

def plain(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if hasattr(v, "items"):
        try:
            return {str(k): plain(x) for k, x in v.items()}
        except Exception:
            pass
    return str(v)

def getv(x, key, default=None):
    if isinstance(x, dict):
        return x.get(key, default)
    try:
        return getattr(x, key)
    except Exception:
        return default

def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"
    body_only.reset_telemetry()

def snapshot(state):
    return [plain(getv(state[p], "observation")) for p in (0, 1)]

def ts(obs_pair):
    return {
        "day": int(obs_pair[0].get("day", 0) or 0),
        "hour": int(obs_pair[0].get("hour", 0) or 0),
    }

def carried(obs):
    return sum(
        int(inv.get("STRAWBERRY", 0) or 0)
        for inv in (obs.get("private", {}) or {}).get("inventories", []) or []
        if isinstance(inv, dict)
    )

def shed(obs):
    return int(((obs.get("private", {}) or {}).get("shed", {}) or {}).get("STRAWBERRY", 0) or 0)

def inventory_strawberry(obs, idx):
    invs = (obs.get("private", {}) or {}).get("inventories", []) or []
    if idx >= len(invs) or not isinstance(invs[idx], dict):
        return 0
    return int(invs[idx].get("STRAWBERRY", 0) or 0)

def unit_position(obs, player, idx):
    farm = obs["farms"][player]
    if idx == 0:
        return plain(farm.get("farmer"))
    hands = farm.get("hands", []) or []
    return plain(hands[idx - 1]) if idx - 1 < len(hands) else None

def action_for_index(action, idx):
    action = action if isinstance(action, dict) else {}
    if idx == 0:
        return plain(action.get("farmer", ["PASS"]))
    hands = action.get("hands", []) or []
    if not isinstance(hands, list) or idx - 1 >= len(hands):
        return ["PASS"]
    return plain(hands[idx - 1])

def strawberry_inventory_changes(before_obs, after_obs, action, player):
    b_invs = (before_obs.get("private", {}) or {}).get("inventories", []) or []
    a_invs = (after_obs.get("private", {}) or {}).get("inventories", []) or []
    n = max(len(b_invs), len(a_invs))
    out = []
    for idx in range(n):
        b = inventory_strawberry(before_obs, idx)
        a = inventory_strawberry(after_obs, idx)
        if a != b:
            out.append({
                "inventory_index": idx,
                "before": b,
                "after": a,
                "delta": a - b,
                "unit_position_before": unit_position(before_obs, player, idx),
                "unit_position_after": unit_position(after_obs, player, idx),
                "current_turn_action": action_for_index(action, idx),
            })
    return out

def source_hash(fn):
    src = inspect.getsource(fn)
    return hashlib.sha256(src.encode("utf-8")).hexdigest()

def measured_market(state, env):
    global _last_after
    current_before = snapshot(state)
    now = ts(current_before)
    t = now["day"] * 24 + now["hour"]
    current_actions = [plain(getv(state[p], "action", {})) for p in (0, 1)]

    if 20 * 24 <= t <= 24 * 24 and _last_after is not None:
        s = SEAT
        o = 1 - SEAT
        before_r = carried(_last_after[o]) - carried(_last_after[s])
        after_r = carried(current_before[o]) - carried(current_before[s])
        if after_r > before_r:
            events.append({
                "from": ts(_last_after),
                "to": now,
                "carried_residual_before": before_r,
                "carried_residual_after": after_r,
                "carried_residual_delta": after_r - before_r,
                "self": {
                    "carried_before": carried(_last_after[s]),
                    "carried_after": carried(current_before[s]),
                    "shed_before": shed(_last_after[s]),
                    "shed_after": shed(current_before[s]),
                    "inventory_changes": strawberry_inventory_changes(
                        _last_after[s], current_before[s], current_actions[s], s
                    ),
                },
                "opponent": {
                    "carried_before": carried(_last_after[o]),
                    "carried_after": carried(current_before[o]),
                    "shed_before": shed(_last_after[o]),
                    "shed_after": shed(current_before[o]),
                    "inventory_changes": strawberry_inventory_changes(
                        _last_after[o], current_before[o], current_actions[o], o
                    ),
                },
            })

    exact.measured_process_market(state, env)
    after = snapshot(state)
    at = ts(after)
    at_t = at["day"] * 24 + at["hour"]
    if 20 * 24 <= at_t <= 24 * 24:
        _last_after = after

def main():
    global _last_after
    configure()
    events.clear()
    _last_after = None
    exact.ledger = [defaultdict(float), defaultdict(float)]
    exact.units = [defaultdict(int), defaultdict(int)]
    exact.events = []

    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    original = kg._process_market
    kg._process_market = measured_market
    try:
        players = [basecfg.OPPONENT, basecfg.OPPONENT]
        players[SEAT] = body_only.agent
        env.run(players)
    finally:
        kg._process_market = original

    rewards = [float(x.reward) for x in env.state]
    provenance = {
        "kaggle_environments_version": getattr(kaggle_environments, "__version__", None),
        "module_file": str(getattr(kg, "__file__", "")),
        "apply_unit_action_sha256": source_hash(kg._apply_unit_action),
        "farmer_inventory_sha256": source_hash(kg._farmer_inventory),
        "interpreter_sha256": source_hash(kg.interpreter),
    }
    payload = {
        "schema": "kaggriculture.strong-origin-v2.strawberry-carried-action-bridge.v0",
        "seed": SEED,
        "seat": SEAT,
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1-SEAT],
            "margin": rewards[SEAT] - rewards[1-SEAT],
        },
        "environment_provenance": provenance,
        "events": events,
        "boundary": [
            "Event trigger is identical to the prior STRAWBERRY carried-residual increase trigger.",
            "current_turn_action is read directly from state.action at market entry, after unit actions have executed for that turn.",
            "inventory index mapping follows the installed environment's public _farmer_inventory convention; no behavioral motive is inferred.",
            "This probe does not by itself prove item lineage across multiple turns.",
            "No policy, Evaluation, Direction, Candidate, or adoption decision is introduced.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("STRAWBERRY_ACTION_BRIDGE " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "events": len(events),
        "terminal": payload["terminal"],
        "environment_provenance": provenance,
    }, ensure_ascii=False, separators=(",", ":")))

if __name__ == "__main__":
    main()
