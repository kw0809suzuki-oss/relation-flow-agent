#!/usr/bin/env python3
"""Observation-only Fresh20 diagnostic for WR-02 vs WR-02 + P12 Day0 reservation.

No policy modification is introduced here. The existing paired comparison is
replayed on seeds 8601-8620. We record Day0 action/position collision shape and
the first Day1 State seen by each side, then preserve terminal self/margin.
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
OUT = Path(f"p12_trigger_observer_v0_{SEED}_seat{SEAT}.json")


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
    if hasattr(v, "tolist"):
        try:
            return plain(v.tolist())
        except Exception:
            pass
    if hasattr(v, "item"):
        try:
            return plain(v.item())
        except Exception:
            pass
    if hasattr(v, "__dict__"):
        try:
            return {str(k): plain(x) for k, x in vars(v).items()}
        except Exception:
            pass
    return repr(v)


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def _tile_counts(tiles):
    out = {
        "empty_unlocked": 0,
        "locked": 0,
        "occupied_unlocked": 0,
        "plant_tiles": 0,
        "weed_tiles": 0,
        "structure_tiles": 0,
        "animal_tiles": 0,
    }
    for row in tiles or []:
        for tile in row or []:
            if tile is None:
                out["empty_unlocked"] += 1
                continue
            if tile == "LOCKED":
                out["locked"] += 1
                continue
            out["occupied_unlocked"] += 1
            if isinstance(tile, dict):
                kind = tile.get("kind")
                if kind == "PLANT":
                    out["plant_tiles"] += 1
                elif kind == "WEED":
                    out["weed_tiles"] += 1
                elif kind in ("COOP", "PASTURE"):
                    out["structure_tiles"] += 1
                    if tile.get("animal") is not None:
                        out["animal_tiles"] += 1
    return out


def summarize_obs(obs):
    o = plain(obs)
    player = int(o.get("player", SEAT))
    farms = o.get("farms") or []
    farm = farms[player] if player < len(farms) else {}
    priv = o.get("private") or {}
    tiles = farm.get("tiles") or []
    return {
        "day": o.get("day"),
        "hour": o.get("hour"),
        "step": o.get("step"),
        "money": farm.get("money"),
        "farmer": farm.get("farmer"),
        "hands": farm.get("hands") or [],
        "unlocked_quadrants": farm.get("unlocked_quadrants") or [],
        "hires_today": farm.get("hires_today"),
        "seeds": priv.get("seeds") or {},
        "shed": priv.get("shed") or {},
        "tile_counts": _tile_counts(tiles),
    }


def summarize_action(obs_summary, action):
    a = plain(action)
    if not isinstance(a, dict):
        a = {}
    farmer_action = a.get("farmer") or ["PASS"]
    hand_actions = a.get("hands") or []
    market_actions = a.get("market") or []

    plant_requests = []

    def add_plant(actor, pos, unit_action):
        if not isinstance(unit_action, list) or not unit_action:
            return
        if unit_action[0] != "PLANT":
            return
        crop = unit_action[1] if len(unit_action) > 1 else None
        p = tuple(pos) if isinstance(pos, list) and len(pos) >= 2 else None
        plant_requests.append({"actor": actor, "target": list(p) if p else None, "crop": crop})

    add_plant("farmer", obs_summary.get("farmer"), farmer_action)
    for i, unit_action in enumerate(hand_actions):
        hands = obs_summary.get("hands") or []
        pos = hands[i] if i < len(hands) else None
        add_plant(f"hand_{i}", pos, unit_action)

    target_keys = [
        tuple(x["target"]) for x in plant_requests if isinstance(x.get("target"), list)
    ]
    distinct_targets = len(set(target_keys))
    duplicate_requests = max(0, len(target_keys) - distinct_targets)

    return {
        "farmer": farmer_action,
        "hands": hand_actions,
        "market": market_actions,
        "plant_requests": plant_requests,
        "plant_request_count": len(plant_requests),
        "distinct_plant_targets": distinct_targets,
        "duplicate_plant_requests": duplicate_requests,
    }


def play(module):
    configure()
    module.reset_telemetry()
    records = []
    first_day1 = None

    def observed_agent(obs):
        nonlocal first_day1
        s = summarize_obs(obs)
        action = module.agent(obs)
        a = summarize_action(s, action)
        if s.get("day") == 0:
            records.append({"state": s, "action": a})
        elif s.get("day") == 1 and first_day1 is None:
            first_day1 = s
        return action

    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[SEAT] = observed_agent
    env.run(players)
    rewards = [float(x.reward) for x in env.state]

    def day0_summary():
        plant_count = sum(r["action"]["plant_request_count"] for r in records)
        distinct = sum(r["action"]["distinct_plant_targets"] for r in records)
        dup = sum(r["action"]["duplicate_plant_requests"] for r in records)
        dup_turns = sum(r["action"]["duplicate_plant_requests"] > 0 for r in records)
        plant_turns = sum(r["action"]["plant_request_count"] > 0 for r in records)
        return {
            "turns_observed": len(records),
            "plant_request_count": plant_count,
            "distinct_plant_targets_sum": distinct,
            "duplicate_plant_requests": dup,
            "duplicate_plant_turns": dup_turns,
            "plant_turns": plant_turns,
            "first_state": records[0]["state"] if records else None,
            "last_state": records[-1]["state"] if records else None,
        }

    return {
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "day0_summary": day0_summary(),
        "day0_records": records,
        "first_day1_state": first_day1,
    }


def keyed(records):
    return {
        (r["state"].get("day"), r["state"].get("hour")): r
        for r in records
    }


def action_signature(r):
    a = r["action"]
    return {
        "farmer": a.get("farmer"),
        "hands": a.get("hands"),
        "market": a.get("market"),
    }


def state_delta(day1_current, day1_candidate):
    if not day1_current or not day1_candidate:
        return None
    ctc = day1_current.get("tile_counts") or {}
    ktc = day1_candidate.get("tile_counts") or {}
    keys = sorted(set(ctc) | set(ktc))
    return {
        "money": (day1_candidate.get("money") or 0) - (day1_current.get("money") or 0),
        "hands_count": len(day1_candidate.get("hands") or []) - len(day1_current.get("hands") or []),
        "tile_counts": {k: (ktc.get(k) or 0) - (ctc.get(k) or 0) for k in keys},
        "seeds": {
            k: (day1_candidate.get("seeds", {}).get(k, 0) or 0)
            - (day1_current.get("seeds", {}).get(k, 0) or 0)
            for k in sorted(set(day1_current.get("seeds", {})) | set(day1_candidate.get("seeds", {})))
        },
    }


def main():
    b = play(current)
    c = play(candidate)

    bk = keyed(b["day0_records"])
    ck = keyed(c["day0_records"])
    common = sorted(set(bk) & set(ck))
    changed = []
    for key in common:
        if action_signature(bk[key]) != action_signature(ck[key]):
            changed.append({
                "day": key[0],
                "hour": key[1],
                "current_state": bk[key]["state"],
                "candidate_state": ck[key]["state"],
                "current_action": bk[key]["action"],
                "candidate_action": ck[key]["action"],
            })

    payload = {
        "schema": "kaggriculture.p12-trigger-observer.v0",
        "seed": SEED,
        "seat": SEAT,
        "current": b,
        "candidate": c,
        "delta_self": c["terminal"]["self"] - b["terminal"]["self"],
        "delta_margin": c["terminal"]["margin"] - b["terminal"]["margin"],
        "day0_changed_turn_count": len(changed),
        "day0_changed_turns": changed,
        "day1_candidate_minus_current": state_delta(
            b["first_day1_state"], c["first_day1_state"]
        ),
        "boundary": [
            "Observation-only replay of existing WR-02 vs WR-02+P12 comparison.",
            "No policy logic is changed.",
            "Duplicate PLANT requests are counted only when multiple PLANT requests in one turn originate from actors occupying the same current tile.",
            "occupied_unlocked means non-null, non-LOCKED tiles; it is an observable count, not a claim that every occupied tile is productive.",
            "The first Day1 State is observed before that side emits its first Day1 action.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("P12_TRIGGER_OBSERVER " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
