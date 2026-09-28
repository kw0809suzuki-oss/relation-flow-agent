#!/usr/bin/env python3
"""Work Allocation Surface Compare fresh10 v0.

At the last compact-MILK-equal turn immediately before the first MILK physical
stage divergence, compare A=Current D14 vs B=Seed reopen on a mechanically
observable work-allocation surface.

No pressure score is invented. Raw counts and submitted unit actions only.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import seed_horizon_isolation_probe_v0 as probe
import run_seed_horizon_isolation_fresh10_v0 as horizon
import run_milk_return_boundary_audit_fresh10_v0 as milk_boundary
import run_milk_physical_precursor_audit_fresh10_v0 as phys

CASES = horizon.CASES
OUT = Path("work_allocation_surface_compare_fresh10_v0_result.json")


def key(day: int, hour: int) -> str:
    return f"D{day}h{hour}"


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def compact_inventory(inv: Dict[str, Any]) -> Dict[str, int]:
    if not isinstance(inv, dict):
        return {}
    return {
        str(k): int(v or 0)
        for k, v in sorted(inv.items())
        if int(v or 0) != 0
    }


def surface(obs: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    player = int(obs.get("player", 0) or 0)
    day = int(obs.get("day", 0) or 0)
    farm = (obs.get("farms", []) or [])[player]
    private = obs.get("private", {}) or {}
    seeds = private.get("seeds", {}) or {}
    invs = private.get("inventories", []) or []

    actor_positions = [farm.get("farmer")]
    actor_positions.extend(farm.get("hands", []) or [])

    unit_actions = [action.get("farmer", ["PASS"])]
    unit_actions.extend(action.get("hands", []) or [])

    actors = []
    for idx, pos in enumerate(actor_positions):
        inv = invs[idx] if idx < len(invs) and isinstance(invs[idx], dict) else {}
        act = unit_actions[idx] if idx < len(unit_actions) else ["PASS"]
        if not isinstance(act, list) or not act:
            act = ["PASS"]
        actors.append({
            "actor": "farmer" if idx == 0 else f"hand:{idx-1}",
            "position": list(pos) if isinstance(pos, (list, tuple)) else None,
            "inventory": compact_inventory(inv),
            "submitted_action": list(act),
        })

    harvestable_cows = []
    harvestable_crops = []
    water_needed_plants = []
    care_needed_animals = []
    feed_needed_animals = []
    empty_tiles = 0
    plant_tiles = 0
    animal_tiles = 0

    for y, row in enumerate(farm.get("tiles", []) or []):
        for x, tile in enumerate(row or []):
            if tile is None:
                empty_tiles += 1
                continue
            if not isinstance(tile, dict):
                continue

            if tile.get("kind") == "PLANT" and tile.get("crop") in kg.CROPS:
                plant_tiles += 1
                crop = str(tile["crop"])
                age = day - int(tile.get("planted_day", day) or day)
                yld = int(tile.get("yield_units", 0) or 0)
                if not bool(tile.get("watered_today", False)):
                    water_needed_plants.append({
                        "position": [x, y],
                        "crop": crop,
                        "age_days": age,
                        "yield_units": yld,
                    })
                if yld > 0 and age >= int(kg.CROPS[crop]["first_yield_day"]):
                    harvestable_crops.append({
                        "position": [x, y],
                        "crop": crop,
                        "age_days": age,
                        "yield_units": yld,
                    })

            if tile.get("animal") in kg.ANIMALS:
                animal_tiles += 1
                animal = str(tile["animal"])
                yld = int(tile.get("yield_units", 0) or 0)
                if animal == "COW" and yld > 0:
                    harvestable_cows.append({
                        "position": [x, y],
                        "yield_units": yld,
                        "placed_day": int(tile.get("placed_day", 0) or 0),
                    })
                if not bool(tile.get("cared_today", False)):
                    care_needed_animals.append({
                        "position": [x, y],
                        "animal": animal,
                        "yield_units": yld,
                    })
                if not bool(tile.get("fed_today", False)):
                    feed_needed_animals.append({
                        "position": [x, y],
                        "animal": animal,
                        "yield_units": yld,
                    })

    action_counts = Counter()
    for a in unit_actions:
        op = a[0] if isinstance(a, list) and a else "PASS"
        action_counts[str(op)] += 1

    seed_stock = {
        crop: int(seeds.get(crop, 0) or 0)
        for crop in kg.CROPS
        if int(seeds.get(crop, 0) or 0) > 0
    }

    carried_total_by_product = Counter()
    for inv in invs:
        if not isinstance(inv, dict):
            continue
        for item, n in inv.items():
            if int(n or 0):
                carried_total_by_product[str(item)] += int(n or 0)

    return {
        "day": day,
        "hour": int(obs.get("hour", 0) or 0),
        "cash": float(farm.get("money", 0) or 0),
        "hands_count": len(farm.get("hands", []) or []),
        "actor_count": len(actor_positions),
        "actors": actors,
        "plant_tiles": plant_tiles,
        "animal_tiles": animal_tiles,
        "empty_tiles": empty_tiles,
        "seed_stock": seed_stock,
        "carried_total_by_product": dict(sorted(carried_total_by_product.items())),
        "harvestable_cow_count": len(harvestable_cows),
        "harvestable_cow_yield": sum(x["yield_units"] for x in harvestable_cows),
        "harvestable_cows": harvestable_cows,
        "harvestable_crop_count": len(harvestable_crops),
        "harvestable_crop_yield": sum(x["yield_units"] for x in harvestable_crops),
        "harvestable_crops": harvestable_crops,
        "water_needed_plant_count": len(water_needed_plants),
        "water_needed_plants": water_needed_plants,
        "care_needed_animal_count": len(care_needed_animals),
        "care_needed_animals": care_needed_animals,
        "feed_needed_animal_count": len(feed_needed_animals),
        "feed_needed_animals": feed_needed_animals,
        "submitted_action_counts": dict(sorted(action_counts.items())),
        "market_orders": json.loads(json.dumps(action.get("market", []) or [])),
        "boundary": [
            "Counts are raw visible-state counts, not a combined pressure score.",
            "water_needed means PLANT and watered_today is false.",
            "care_needed/feed_needed means animal tile and cared_today/fed_today is false.",
            "harvestable crop uses public first_yield_day plus yield_units > 0.",
            "harvestable COW means visible COW yield_units > 0.",
        ],
    }


def play(seed: int, seat: int, mode: str) -> Dict[str, Any]:
    configure()
    probe.set_mode(mode)
    probe.reset_telemetry()

    exact = milk_boundary.MilkAudit()
    rows: Dict[str, Any] = {}

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed_agent(obs):
        action = probe.agent(obs)
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        player = int(obs.get("player", seat) or seat)
        farm = (obs.get("farms", []) or [])[player]
        private = obs.get("private", {}) or {}
        rows[key(day, hour)] = {
            "surface": surface(obs, action),
            "milk_state": phys.farm_milk_state(farm, private),
        }
        return action

    original_market = kg._process_market
    kg._process_market = exact.process_market
    try:
        players = [basecfg.OPPONENT, basecfg.OPPONENT]
        players[seat] = observed_agent
        env.run(players)
        rewards = [float(x.reward) for x in env.state]
    finally:
        kg._process_market = original_market

    realized = [e for e in exact.events if e["player"] == seat]
    realized_by_turn = defaultdict(list)
    for e in realized:
        realized_by_turn[key(e["day"], e["hour"])].append(e)

    return {
        "terminal": {
            "self": rewards[seat],
            "opponent": rewards[1-seat],
            "margin": rewards[seat] - rewards[1-seat],
        },
        "rows": rows,
        "realized_milk_sell_by_turn": dict(realized_by_turn),
    }


def first_sell_diff(a: Dict[str, Any], b: Dict[str, Any]):
    turns = sorted(
        set(a["realized_milk_sell_by_turn"]) | set(b["realized_milk_sell_by_turn"]),
        key=lambda t: tuple(map(int, t[1:].replace("h", " ").split())),
    )
    for t in turns:
        aa = a["realized_milk_sell_by_turn"].get(t, [])
        bb = b["realized_milk_sell_by_turn"].get(t, [])
        sa = [(x["cash_delta"], x["unit_price"], x["market_inventory_before"]) for x in aa]
        sb = [(x["cash_delta"], x["unit_price"], x["market_inventory_before"]) for x in bb]
        if sa != sb:
            return t
    return None


def compact_milk_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return phys.physical_equal(a["milk_state"], b["milk_state"])


def last_equal_before_first_milk_diff(a: Dict[str, Any], b: Dict[str, Any], sell_t: str):
    turns = sorted(
        set(a["rows"]) & set(b["rows"]),
        key=lambda t: tuple(map(int, t[1:].replace("h", " ").split())),
    )
    sell_pair = tuple(map(int, sell_t[1:].replace("h", " ").split()))
    turns = [t for t in turns if tuple(map(int, t[1:].replace("h", " ").split())) <= sell_pair]

    previous_equal = None
    for t in turns:
        if compact_milk_equal(a["rows"][t], b["rows"][t]):
            previous_equal = t
        else:
            return previous_equal, t
    return None, None


def scalar_delta(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, float]:
    fields = [
        "cash",
        "hands_count",
        "actor_count",
        "plant_tiles",
        "animal_tiles",
        "empty_tiles",
        "harvestable_cow_count",
        "harvestable_cow_yield",
        "harvestable_crop_count",
        "harvestable_crop_yield",
        "water_needed_plant_count",
        "care_needed_animal_count",
        "feed_needed_animal_count",
    ]
    out = {}
    for f in fields:
        d = float(b.get(f, 0) or 0) - float(a.get(f, 0) or 0)
        if abs(d) > 1e-9:
            out[f] = d
    return out


def dict_delta(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, int]:
    out = {}
    for k in sorted(set(a) | set(b)):
        d = int(b.get(k, 0) or 0) - int(a.get(k, 0) or 0)
        if d:
            out[k] = d
    return out


def main():
    cases = []
    for seed, seat in CASES:
        a = play(seed, seat, "A")
        b = play(seed, seat, "B")
        ds = b["terminal"]["self"] - a["terminal"]["self"]
        group = "SELF_IMPROVED" if ds > 0 else "SELF_WORSE" if ds < 0 else "SELF_EQUAL"

        sell_t = first_sell_diff(a, b)
        if sell_t is None:
            cases.append({
                "seed": seed, "seat": seat, "group": group, "delta_self": ds,
                "status": "NO_MILK_SELL_DIFFERENCE",
            })
            continue

        last_equal, first_diff = last_equal_before_first_milk_diff(a, b, sell_t)
        if last_equal is None or first_diff is None:
            cases.append({
                "seed": seed, "seat": seat, "group": group, "delta_self": ds,
                "sell_boundary": sell_t,
                "status": "NO_PHYSICAL_PRECURSOR",
            })
            continue

        sa = a["rows"][last_equal]["surface"]
        sb = b["rows"][last_equal]["surface"]

        cases.append({
            "seed": seed,
            "seat": seat,
            "group": group,
            "delta_self": ds,
            "status": "OBSERVED",
            "last_milk_equal_timestamp": last_equal,
            "first_milk_physical_difference": first_diff,
            "first_milk_sell_difference": sell_t,
            "A": sa,
            "B": sb,
            "delta_B_minus_A": {
                "scalar": scalar_delta(sa, sb),
                "seed_stock": dict_delta(sa["seed_stock"], sb["seed_stock"]),
                "carried_total_by_product": dict_delta(
                    sa["carried_total_by_product"], sb["carried_total_by_product"]
                ),
                "submitted_action_counts": dict_delta(
                    sa["submitted_action_counts"], sb["submitted_action_counts"]
                ),
            },
        })

    groups = {}
    for group in ("SELF_IMPROVED", "SELF_WORSE"):
        rows = [c for c in cases if c["group"] == group and c.get("status") == "OBSERVED"]
        scalar_fields = [
            "cash", "hands_count", "plant_tiles", "animal_tiles",
            "harvestable_cow_count", "harvestable_cow_yield",
            "harvestable_crop_count", "harvestable_crop_yield",
            "water_needed_plant_count", "care_needed_animal_count",
            "feed_needed_animal_count",
        ]
        mean_scalar = {}
        for f in scalar_fields:
            vals = [
                float(c["B"].get(f, 0) or 0) - float(c["A"].get(f, 0) or 0)
                for c in rows
            ]
            mean_scalar[f] = sum(vals) / len(vals) if vals else None

        action_keys = sorted({
            k for c in rows
            for k in set(c["A"]["submitted_action_counts"]) | set(c["B"]["submitted_action_counts"])
        })
        mean_action_delta = {}
        for k in action_keys:
            vals = [
                int(c["B"]["submitted_action_counts"].get(k, 0) or 0)
                - int(c["A"]["submitted_action_counts"].get(k, 0) or 0)
                for c in rows
            ]
            mean_action_delta[k] = sum(vals) / len(vals) if vals else None

        groups[group] = {
            "count_observed": len(rows),
            "mean_B_minus_A_scalar": mean_scalar,
            "mean_B_minus_A_action_count": mean_action_delta,
            "by_seed": {
                str(c["seed"]): {
                    "delta_self": c["delta_self"],
                    "timestamp": c["last_milk_equal_timestamp"],
                    "scalar_delta": c["delta_B_minus_A"]["scalar"],
                    "seed_stock_delta": c["delta_B_minus_A"]["seed_stock"],
                    "carried_delta": c["delta_B_minus_A"]["carried_total_by_product"],
                    "action_count_delta": c["delta_B_minus_A"]["submitted_action_counts"],
                }
                for c in rows
            },
        }

    result = {
        "schema": "kaggriculture.work-allocation-surface-compare.fresh10.result.v0",
        "group_summary": groups,
        "cases": cases,
        "boundary": [
            "Comparison timestamp is the last compact-MILK-equal live state immediately before the first compact MILK physical divergence.",
            "A/B differ only in D14 BUY_SEED suppression.",
            "Work fields are raw visible-state counts; no synthetic pressure score is used.",
            "Differences at this timestamp are candidate separators only.",
            "Improved/worse grouping is retrospective and not live-safe.",
        ],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("WORK_ALLOCATION_SURFACE_COMPARE " + json.dumps({
        "group_summary": groups,
        "cases": [
            {
                "seed": c["seed"],
                "group": c["group"],
                "delta_self": c["delta_self"],
                "status": c["status"],
                "timestamp": c.get("last_milk_equal_timestamp"),
                "scalar_delta": c.get("delta_B_minus_A", {}).get("scalar"),
                "action_count_delta": c.get("delta_B_minus_A", {}).get("submitted_action_counts"),
            }
            for c in cases
        ],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
