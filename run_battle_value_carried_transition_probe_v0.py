#!/usr/bin/env python3
"""Battle Value Carried Transition Probe v0.

Fixed five-Battle Day20->24 observation.

Trigger:
  opponent-minus-self carried quantity for a focus item increases between
  previous market-after State and current market-before State.

For each trigger, record:
- previous market-after State
- current market-before State
- raw recursive field differences
- absolute shed/carried/on-hand quantities for both sides

The probe does not name the transition HARVEST, DROP, maturity, transfer,
movement, production, or any other mechanism.
"""
import json
import os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as body_only

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"battle_value_carried_transition_probe_v0_{SEED}_seat{SEAT}.json")
FOCUS_ITEMS = ("STRAWBERRY", "MELON", "WOOL")

events = []
_last_market_after = None

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

def qty_map(src):
    src = src if isinstance(src, dict) else {}
    return {item: int(src.get(item, 0) or 0) for item in econ.PRODUCTS}

def side_stock(obs):
    player = int(obs["player"])
    private = obs.get("private", {}) or {}
    shed = qty_map(private.get("shed", {}) or {})
    carried = {item: 0 for item in econ.PRODUCTS}
    for inv in private.get("inventories", []) or []:
        if not isinstance(inv, dict):
            continue
        for item in econ.PRODUCTS:
            carried[item] += int(inv.get(item, 0) or 0)
    return {
        "shed": shed,
        "carried": carried,
        "on_hand": {item: shed[item] + carried[item] for item in econ.PRODUCTS},
    }

def path_join(base, key):
    if isinstance(key, int):
        return f"{base}[{key}]" if base else f"[{key}]"
    return f"{base}.{key}" if base else str(key)

def raw_diff(before, after, path=""):
    out = []
    if type(before) is not type(after):
        out.append({"path": path, "before": before, "after": after})
        return out
    if isinstance(before, dict):
        keys = sorted(set(before) | set(after), key=str)
        for k in keys:
            p = path_join(path, k)
            if k not in before:
                out.append({"path": p, "before": {"__missing__": True}, "after": after[k]})
            elif k not in after:
                out.append({"path": p, "before": before[k], "after": {"__missing__": True}})
            else:
                out.extend(raw_diff(before[k], after[k], p))
        return out
    if isinstance(before, list):
        n = max(len(before), len(after))
        for i in range(n):
            p = path_join(path, i)
            if i >= len(before):
                out.append({"path": p, "before": {"__missing__": True}, "after": after[i]})
            elif i >= len(after):
                out.append({"path": p, "before": before[i], "after": {"__missing__": True}})
            else:
                out.extend(raw_diff(before[i], after[i], p))
        return out
    if before != after:
        out.append({"path": path, "before": before, "after": after})
    return out

def snapshot_pair(state):
    obs = [plain(getv(state[p], "observation")) for p in (0, 1)]
    return {"obs": obs, "stock": [side_stock(obs[p]) for p in (0, 1)]}

def timestamp(pair):
    obs0 = pair["obs"][0]
    return {"day": int(obs0.get("day", 0) or 0), "hour": int(obs0.get("hour", 0) or 0)}

def carried_residual(pair, item):
    s = SEAT
    o = 1 - SEAT
    return pair["stock"][o]["carried"][item] - pair["stock"][s]["carried"][item]

def item_position(pair, item):
    s = SEAT
    o = 1 - SEAT
    return {
        "self": {
            "shed": pair["stock"][s]["shed"][item],
            "carried": pair["stock"][s]["carried"][item],
            "on_hand": pair["stock"][s]["on_hand"][item],
        },
        "opponent": {
            "shed": pair["stock"][o]["shed"][item],
            "carried": pair["stock"][o]["carried"][item],
            "on_hand": pair["stock"][o]["on_hand"][item],
        },
        "residual_opponent_minus_self": {
            "shed": pair["stock"][o]["shed"][item] - pair["stock"][s]["shed"][item],
            "carried": pair["stock"][o]["carried"][item] - pair["stock"][s]["carried"][item],
            "on_hand": pair["stock"][o]["on_hand"][item] - pair["stock"][s]["on_hand"][item],
        },
    }

def measured_market_with_transition_probe(state, env):
    global _last_market_after
    current_before = snapshot_pair(state)
    ts = timestamp(current_before)
    t = ts["day"] * 24 + ts["hour"]
    in_window = (20 * 24 <= t <= 24 * 24)

    if in_window and _last_market_after is not None:
        prev_ts = timestamp(_last_market_after)
        for item in FOCUS_ITEMS:
            before_r = carried_residual(_last_market_after, item)
            after_r = carried_residual(current_before, item)
            if after_r > before_r:
                events.append({
                    "item": item,
                    "from": prev_ts,
                    "to": ts,
                    "carried_residual_before": before_r,
                    "carried_residual_after": after_r,
                    "carried_residual_delta": after_r - before_r,
                    "position_before": item_position(_last_market_after, item),
                    "position_after": item_position(current_before, item),
                    "state_before_market_after": _last_market_after["obs"],
                    "state_after_next_market_before": current_before["obs"],
                    "raw_diff_by_player_observation": [
                        raw_diff(_last_market_after["obs"][p], current_before["obs"][p])
                        for p in (0, 1)
                    ],
                })

    exact.measured_process_market(state, env)

    after_market = snapshot_pair(state)
    after_ts = timestamp(after_market)
    after_t = after_ts["day"] * 24 + after_ts["hour"]
    if 20 * 24 <= after_t <= 24 * 24:
        _last_market_after = after_market

def main():
    global _last_market_after
    configure()
    events.clear()
    _last_market_after = None
    exact.ledger = [defaultdict(float), defaultdict(float)]
    exact.units = [defaultdict(int), defaultdict(int)]
    exact.events = []

    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    original_market = kg._process_market
    kg._process_market = measured_market_with_transition_probe
    try:
        players = [basecfg.OPPONENT, basecfg.OPPONENT]
        players[SEAT] = body_only.agent
        env.run(players)
    finally:
        kg._process_market = original_market

    rewards = [float(x.reward) for x in env.state]
    payload = {
        "schema": "kaggriculture.strong-origin-v2.carried-transition-probe.v0",
        "seed": SEED,
        "seat": SEAT,
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "window": "Day20 h0 -> Day24 h0",
        "focus_items": list(FOCUS_ITEMS),
        "events": events,
        "boundary": [
            "A trigger means opponent-minus-self carried quantity increased between one market-after State and the next market-before State.",
            "The compared interval excludes market processing at the earlier turn.",
            "raw_diff_by_player_observation is a structural JSON field difference only; changed paths are not assigned causal meaning.",
            "The probe does not claim that changed fields are causes of the carried change.",
            "The probe does not identify HARVEST, DROP, maturity, movement, transfer, production, or item lineage.",
            "MELON and WOOL are retained only as parallel positive-control observations; STRAWBERRY remains the parent-path target.",
            "No Action, policy, Representation, Evaluation, Direction, Candidate, or adoption decision is introduced.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {item: sum(1 for e in events if e["item"] == item) for item in FOCUS_ITEMS}
    print("BATTLE_VALUE_CARRIED_TRANSITION_PROBE " + json.dumps({
        "seed": SEED, "seat": SEAT, "event_counts": counts, "terminal": payload["terminal"]
    }, ensure_ascii=False, separators=(",", ":")))

if __name__ == "__main__":
    main()
