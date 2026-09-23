#!/usr/bin/env python3
"""LAND Productive Transition Observer v0.

Exact SB-01 baseline policy/runtime. No Candidate and no policy mutation.

For each side independently:
- locate the first *realized* Expansion from retained observations
  (unlocked tile count increases between adjacent rows);
- align that transition as t=0;
- keep only snapshots at t=-1,0,+24,+48,+72;
- keep the first post-LAND change event for selected State fields.

Action is deliberately not analyzed here. This observer records State
transition only.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from analyze_sb01_economic_layers_v0 import derive_side

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OPPONENT = base.OPPONENT
OFFSETS = (-1, 0, 24, 48, 72)
SCAN_HORIZON = 72
OUT = Path(f"land_productive_transition_observer_v0_{SEED}.json")

PHYSICAL_DIVERGENCE_FIELDS = (
    "empty_tiles",
    "occupied_tiles",
    "crop_count",
    "animal_count",
    "seed_inventory_total",
    "sellable_stock_total",
)
FIRST_CHANGE_FIELDS = PHYSICAL_DIVERGENCE_FIELDS + ("committed_mark",)


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def _plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "items"):
        try:
            return {str(k): _plain(v) for k, v in value.items()}
        except Exception:
            pass
    if hasattr(value, "tolist"):
        try:
            return _plain(value.tolist())
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return _plain(value.item())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {
                str(k): _plain(v)
                for k, v in vars(value).items()
                if not str(k).startswith("_")
            }
        except Exception:
            pass
    return str(value)


def _get(state, key, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    try:
        return getattr(state, key)
    except Exception:
        return default


def state_vector(obs):
    d = derive_side(obs)
    cap = d["uncommitted_capacity"]
    unlocked = float(cap["unlocked_tiles"])
    empty = float(cap["empty_unlocked_tiles"])
    occupied = unlocked - empty
    crop_count = float(sum(d["committed_production"]["crop_count"].values()))
    animal_count = float(sum(d["committed_production"]["animal_count"].values()))
    seed_total = float(sum(d["seed_inventory_fact"].values()))
    stock_total = float(sum(
        x.get("quantity", 0) or 0
        for x in d["liquidatable_inventory"]["by_item"].values()
    ))
    return {
        "day": int(d["day"]),
        "hour": int(d["hour"]),
        "cash": float(d["cash"]),
        "unlocked_tiles": unlocked,
        "empty_tiles": empty,
        "occupied_tiles": occupied,
        "occupancy_ratio": (occupied / unlocked if unlocked else None),
        "crop_count": crop_count,
        "animal_count": animal_count,
        "hands": float(cap["current_hands"]),
        "seed_inventory_total": seed_total,
        "sellable_stock_total": stock_total,
        "committed_mark": float(d["committed_production"]["same_basis_subtotal"]),
        "remaining_turns": float(cap["remaining_season_turns"]),
        "crop_count_by_type": dict(d["committed_production"]["crop_count"]),
        "animal_count_by_type": dict(d["committed_production"]["animal_count"]),
        "seed_inventory_by_type": dict(d["seed_inventory_fact"]),
        "sellable_stock_by_item": {
            k: float(v.get("quantity", 0) or 0)
            for k, v in d["liquidatable_inventory"]["by_item"].items()
        },
    }


def collect_side_rows(env, seat):
    rows = []
    for step_index, step in enumerate(getattr(env, "steps", []) or []):
        if not isinstance(step, (list, tuple)) or len(step) <= seat:
            continue
        obs = _plain(_get(step[seat], "observation"))
        if not isinstance(obs, dict) or "farms" not in obs:
            continue
        try:
            vec = state_vector(obs)
        except Exception:
            continue
        rows.append({
            "step_index": step_index,
            "state": vec,
        })
    return rows


def first_land_event_index(rows):
    for i in range(1, len(rows)):
        if rows[i]["state"]["unlocked_tiles"] > rows[i-1]["state"]["unlocked_tiles"]:
            return i
    return None


def delta(a, b):
    out = {}
    for k in (
        "cash","unlocked_tiles","empty_tiles","occupied_tiles","occupancy_ratio",
        "crop_count","animal_count","hands","seed_inventory_total",
        "sellable_stock_total","committed_mark","remaining_turns"
    ):
        av = a.get(k); bv = b.get(k)
        out[k] = None if av is None or bv is None else bv - av
    return out


def snapshot_for_offset(rows, event_i, rel):
    j = event_i + rel
    if j < 0 or j >= len(rows):
        return None
    row = rows[j]
    return {
        "relative_turn": rel,
        "step_index": row["step_index"],
        "state": row["state"],
    }


def first_post_change(rows, event_i, field):
    base_v = rows[event_i]["state"][field]
    end = min(len(rows), event_i + SCAN_HORIZON + 1)
    for j in range(event_i + 1, end):
        v = rows[j]["state"][field]
        if v != base_v:
            prev = rows[j-1]["state"][field]
            direction = "increase" if v > base_v else "decrease"
            return {
                "relative_turn": j - event_i,
                "step_index": rows[j]["step_index"],
                "day": rows[j]["state"]["day"],
                "hour": rows[j]["state"]["hour"],
                "baseline_value_t0": base_v,
                "previous_turn_value": prev,
                "new_value": v,
                "delta_from_t0": v - base_v,
                "direction": direction,
            }
    return None


def build_side(rows):
    event_i = first_land_event_index(rows)
    if event_i is None:
        return {
            "land_event_found": False,
            "row_count": len(rows),
            "land_event": None,
            "snapshots": {},
            "event_delta": None,
            "first_state_change_by_field": {},
        }

    prev = rows[event_i-1]["state"]
    cur = rows[event_i]["state"]
    snaps = {}
    for rel in OFFSETS:
        s = snapshot_for_offset(rows, event_i, rel)
        snaps[str(rel)] = s

    first = {f: first_post_change(rows, event_i, f) for f in FIRST_CHANGE_FIELDS}
    return {
        "land_event_found": True,
        "row_count": len(rows),
        "land_event": {
            "step_index": rows[event_i]["step_index"],
            "day": cur["day"],
            "hour": cur["hour"],
            "unlocked_before": prev["unlocked_tiles"],
            "unlocked_after": cur["unlocked_tiles"],
            "added_tiles": cur["unlocked_tiles"] - prev["unlocked_tiles"],
        },
        "snapshots": snaps,
        "event_delta": delta(prev, cur),
        "first_state_change_by_field": first,
    }


def relative_state(rows, event_i, rel):
    j = event_i + rel
    if j < 0 or j >= len(rows):
        return None
    return rows[j]["state"]


def first_transition_divergence(self_rows, opp_rows):
    si = first_land_event_index(self_rows)
    oi = first_land_event_index(opp_rows)
    if si is None or oi is None:
        return None

    s0 = self_rows[si]["state"]
    o0 = opp_rows[oi]["state"]
    max_rel = min(
        SCAN_HORIZON,
        len(self_rows) - si - 1,
        len(opp_rows) - oi - 1,
    )
    for rel in range(1, max_rel + 1):
        s = relative_state(self_rows, si, rel)
        o = relative_state(opp_rows, oi, rel)
        diffs = []
        detail = {}
        for f in PHYSICAL_DIVERGENCE_FIELDS:
            sd = s[f] - s0[f]
            od = o[f] - o0[f]
            if sd != od:
                diffs.append(f)
                detail[f] = {
                    "self_delta_from_t0": sd,
                    "opponent_delta_from_t0": od,
                }
        if diffs:
            return {
                "relative_turn": rel,
                "fields": diffs,
                "detail": detail,
                "boundary": "Event-aligned physical State deltas differ; this is not a causal attribution.",
            }
    return None


def main():
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[SEAT] = combat.agent
    env.run(players)

    rewards = [float(x.reward) for x in env.state]
    rows0 = collect_side_rows(env, 0)
    rows1 = collect_side_rows(env, 1)
    rows_by_side = {0: rows0, 1: rows1}

    self_rows = rows_by_side[SEAT]
    opp_rows = rows_by_side[1-SEAT]
    self_out = build_side(self_rows)
    opp_out = build_side(opp_rows)

    payload = {
        "schema": "kaggriculture.land-productive-transition-observer.v0",
        "seed": SEED,
        "seat": SEAT,
        "benchmark": "strength_benchmark_v0",
        "policy_mutated": False,
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1-SEAT],
            "margin": rewards[SEAT] - rewards[1-SEAT],
        },
        "self": self_out,
        "opponent": opp_out,
        "first_self_vs_opponent_transition_divergence": first_transition_divergence(
            self_rows, opp_rows
        ),
        "boundary": [
            "Exact SB-01 baseline policy/runtime is reused.",
            "No Candidate, strategy rule, threshold, or Action change is introduced.",
            "t=0 is identified from realized State: unlocked tile count increased from the preceding retained observation.",
            "Snapshots are retained only at t=-1,0,+24,+48,+72.",
            "first_state_change_by_field scans only the first 72 turns after LAND and stores only the first change event.",
            "Cash and hands are retained in snapshots/context but do not trigger first_self_vs_opponent_transition_divergence.",
            "The divergence marker compares event-aligned physical State deltas from each side's own t=0.",
            "No cause field and no Action attribution is emitted.",
        ],
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("LAND_PRODUCTIVE_TRANSITION_OBSERVER " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "terminal": payload["terminal"],
        "self_land_event": self_out["land_event"],
        "opponent_land_event": opp_out["land_event"],
        "first_divergence": payload["first_self_vs_opponent_transition_divergence"],
        "self_first_changes": {
            k: (v["relative_turn"] if v else None)
            for k,v in self_out["first_state_change_by_field"].items()
        },
        "opponent_first_changes": {
            k: (v["relative_turn"] if v else None)
            for k,v in opp_out["first_state_change_by_field"].items()
        },
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
