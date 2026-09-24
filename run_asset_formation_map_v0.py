#!/usr/bin/env python3
"""Asset Formation Map v0.

Fixed five-Battle coarse World map at Day0 / 8 / 12 / 16 / 20.

For every live crop / placed animal asset, record only public World facts:
- present productive asset count
- currently held output units
- currently harvestable units
- maturity / next public output boundary position
- near-window (4-day) public output opportunities, explicitly conditional
- future public output opportunities through the Day20 anchor, explicitly conditional
- unlocked land context

No market value, Action diagnosis, policy interpretation, Candidate, or causal claim.
"""
import hashlib
import inspect
import json
import os
from pathlib import Path

import kaggle_environments
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body_only

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"asset_formation_map_v0_{SEED}_seat{SEAT}.json")
CHECKPOINT_DAYS = (0, 8, 12, 16, 20)
NEAR_DAYS = 4
ANCHOR_DAY = 20


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


def next_ongoing_crop_events(tile, day, horizon_day_exclusive):
    crop = tile["crop"]
    spec = kg.CROPS[crop]
    first = int(tile["planted_day"]) + int(spec["first_yield_day"])
    interval = max(1, int(spec["interval"]))
    max_events = int(spec["max_yield"])
    out = []
    for n in range(max_events):
        d = first + n * interval
        # At h0, the event for current day has already been applied by prior EOD.
        if d > day and d < horizon_day_exclusive:
            out.append(d)
    return out


def nonongoing_water_opportunities(tile, day, horizon_day_exclusive):
    crop = tile["crop"]
    spec = kg.CROPS[crop]
    planted = int(tile["planted_day"])
    # Public rule: water-yield formation window is ceil((max_yield_day+1)/2)..max_yield_day.
    start_off = (int(spec["max_yield_day"]) + 1) // 2
    end_off = int(spec["max_yield_day"])
    out = []
    for off in range(start_off, end_off + 1):
        d = planted + off
        if day <= d < horizon_day_exclusive:
            out.append(d)
    # Base WATER adds one unit, but current held cap can limit total additions.
    room = max(0, int(spec["max_yield"]) - int(tile.get("yield_units", 0) or 0))
    return out[:room]


def animal_events(tile, day, horizon_day_exclusive):
    animal = tile["animal"]
    spec = kg.ANIMALS[animal]
    first = int(tile["placed_day"]) + int(spec["first_yield_day"])
    interval = max(1, int(spec["interval"]))
    out = []
    d = first
    while d < horizon_day_exclusive:
        if d > day:
            out.append(d)
        d += interval
    return out


def asset_instance(tile, x, y, day):
    if not isinstance(tile, dict):
        return None

    if tile.get("kind") == "PLANT" and tile.get("crop") in kg.CROPS:
        typ = str(tile["crop"])
        spec = kg.CROPS[typ]
        origin = int(tile.get("planted_day", day))
        age = day - origin
        held = max(0, int(tile.get("yield_units", 0) or 0))
        harvestable = held if age >= int(spec["first_yield_day"]) else 0
        harvestable_in_days = max(0, int(spec["first_yield_day"]) - age)

        if bool(spec["ongoing"]):
            near_events = next_ongoing_crop_events(tile, day, day + NEAR_DAYS + 1)
            future_events = next_ongoing_crop_events(tile, day, ANCHOR_DAY + 1) if day < ANCHOR_DAY else []
            boundary_kind = "automatic_day_boundary_output"
            conditional_note = "scheduled base output opportunity; conditional on asset survival"
        else:
            near_events = nonongoing_water_opportunities(tile, day, day + NEAR_DAYS + 1)
            future_events = nonongoing_water_opportunities(tile, day, ANCHOR_DAY + 1) if day < ANCHOR_DAY else []
            boundary_kind = "water_output_formation_opportunity"
            conditional_note = "output formation opportunity; requires future WATER and asset survival"

        first_near = min(near_events) if near_events else None
        return {
            "asset_type": typ,
            "asset_class": "crop",
            "x": x,
            "y": y,
            "origin_day": origin,
            "age_days": age,
            "held_output_units": held,
            "current_harvestable_units": harvestable,
            "days_until_harvest_eligible": harvestable_in_days,
            "near_window_boundary_kind": boundary_kind,
            "near_window_public_opportunity_days": near_events,
            "near_window_public_opportunity_count": len(near_events),
            "near_window_base_units_conditional": len(near_events),
            "future_to_day20_public_opportunity_count": len(future_events),
            "future_to_day20_base_units_conditional": len(future_events),
            "next_public_boundary_day": first_near,
            "conditional_note": conditional_note,
        }

    if tile.get("animal") in kg.ANIMALS:
        typ = str(tile["animal"])
        origin = int(tile.get("placed_day", day))
        age = day - origin
        held = max(0, int(tile.get("yield_units", 0) or 0))
        near_events = animal_events(tile, day, day + NEAR_DAYS + 1)
        future_events = animal_events(tile, day, ANCHOR_DAY + 1) if day < ANCHOR_DAY else []
        first_near = min(near_events) if near_events else None
        return {
            "asset_type": typ,
            "asset_class": "animal",
            "x": x,
            "y": y,
            "origin_day": origin,
            "age_days": age,
            "held_output_units": held,
            "current_harvestable_units": held,
            "days_until_harvest_eligible": 0 if held > 0 else None,
            "near_window_boundary_kind": "automatic_day_boundary_output",
            "near_window_public_opportunity_days": near_events,
            "near_window_public_opportunity_count": len(near_events),
            "near_window_base_units_conditional": len(near_events),
            "future_to_day20_public_opportunity_count": len(future_events),
            "future_to_day20_base_units_conditional": len(future_events),
            "next_public_boundary_day": first_near,
            "conditional_note": "scheduled base output opportunity; conditional on animal survival and available held-capacity",
            "consecutive_unfed": int(tile.get("consecutive_unfed", 0) or 0),
        }

    return None


def all_asset_types():
    return list(kg.CROPS.keys()) + list(kg.ANIMALS.keys())


def summarize(instances):
    by_type = {}
    for typ in all_asset_types():
        by_type[typ] = {
            "asset_class": "crop" if typ in kg.CROPS else "animal",
            "present_asset_count": 0,
            "held_output_units": 0,
            "current_harvestable_units": 0,
            "harvest_eligible_asset_count": 0,
            "near_window_asset_count": 0,
            "near_window_public_opportunity_count": 0,
            "near_window_base_units_conditional": 0,
            "future_to_day20_public_opportunity_count": 0,
            "future_to_day20_base_units_conditional": 0,
            "next_boundary_days": [],
            "days_until_harvest_eligible": [],
        }

    for z in instances:
        r = by_type[z["asset_type"]]
        r["present_asset_count"] += 1
        r["held_output_units"] += z["held_output_units"]
        r["current_harvestable_units"] += z["current_harvestable_units"]
        if z["current_harvestable_units"] > 0:
            r["harvest_eligible_asset_count"] += 1
        if z["near_window_public_opportunity_count"] > 0:
            r["near_window_asset_count"] += 1
        r["near_window_public_opportunity_count"] += z["near_window_public_opportunity_count"]
        r["near_window_base_units_conditional"] += z["near_window_base_units_conditional"]
        r["future_to_day20_public_opportunity_count"] += z["future_to_day20_public_opportunity_count"]
        r["future_to_day20_base_units_conditional"] += z["future_to_day20_base_units_conditional"]
        if z["next_public_boundary_day"] is not None:
            r["next_boundary_days"].append(z["next_public_boundary_day"])
        if z["days_until_harvest_eligible"] is not None:
            r["days_until_harvest_eligible"].append(z["days_until_harvest_eligible"])

    return by_type


def land_context(farm):
    unlocked = list(farm.get("unlocked_quadrants", []) or [])
    unlocked_tiles = 0
    empty_unlocked_tiles = 0
    occupied_productive_tiles = 0
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if tile != "LOCKED":
                unlocked_tiles += 1
                if tile is None:
                    empty_unlocked_tiles += 1
                elif isinstance(tile, dict) and (
                    tile.get("kind") == "PLANT" or tile.get("animal") in kg.ANIMALS
                ):
                    occupied_productive_tiles += 1
    return {
        "unlocked_quadrants": unlocked,
        "unlocked_quadrant_count": len(unlocked),
        "unlocked_tile_count": unlocked_tiles,
        "empty_unlocked_tile_count": empty_unlocked_tiles,
        "productive_occupied_tile_count": occupied_productive_tiles,
    }


def main():
    configure()

    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[SEAT] = body_only.agent
    env.run(players)

    checkpoints = []
    seen = set()
    for step in getattr(env, "steps", []) or []:
        if not isinstance(step, (list, tuple)) or len(step) < 2:
            continue
        so = plain(getv(step[SEAT], "observation"))
        oo = plain(getv(step[1 - SEAT], "observation"))
        if not isinstance(so, dict) or not isinstance(oo, dict):
            continue
        day = int(so.get("day", 0) or 0)
        hour = int(so.get("hour", 0) or 0)
        if day not in CHECKPOINT_DAYS or hour != 0 or day in seen:
            continue
        seen.add(day)

        sides = {}
        for label, obs, pidx in (("self", so, SEAT), ("opponent", oo, 1 - SEAT)):
            farms = obs.get("farms", []) or []
            farm = farms[pidx] if pidx < len(farms) else {}
            instances = []
            for y, row in enumerate(farm.get("tiles", []) or []):
                for x, tile in enumerate(row or []):
                    z = asset_instance(tile, x, y, day)
                    if z is not None:
                        instances.append(z)
            sides[label] = {
                "land": land_context(farm),
                "instances": instances,
                "summary_by_type": summarize(instances),
            }

        checkpoints.append({"day": day, "hour": hour, **sides})

    rewards = [float(x.reward) for x in env.state]
    payload = {
        "schema": "kaggriculture.strong-origin-v2.asset-formation-map.v0",
        "seed": SEED,
        "seat": SEAT,
        "checkpoints": checkpoints,
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "environment_provenance": {
            "kaggle_environments_version": getattr(kaggle_environments, "__version__", None),
            "kaggriculture_module": str(getattr(kg, "__file__", "")),
            "interpreter_sha256": hashlib.sha256(inspect.getsource(kg.interpreter).encode("utf-8")).hexdigest(),
        },
        "boundary": [
            "Present Asset means a live crop PLANT tile or a placed animal in the public World State.",
            "Held output units and current harvestable units are physical per-asset quantities and are never summed across unlike product types for interpretation.",
            "Near-window is fixed at the next 4 calendar days from each checkpoint.",
            "For nonongoing crops, near/future supply fields are public WATER/output-formation opportunities and require future WATER plus survival; they are not guaranteed production.",
            "For ongoing crops and animals, near/future supply fields are scheduled base output opportunities conditional on survival and held-capacity; bonuses are excluded.",
            "future_to_day20 fields stop at the Day20 anchor and are conditional opportunity counts/base units, not expected value.",
            "No market price or cross-type value aggregation is applied.",
            "No Action diagnosis, policy interpretation, Candidate, or causal conclusion is introduced.",
        ],
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ASSET_FORMATION_MAP " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "checkpoint_days": [c["day"] for c in checkpoints],
        "terminal": payload["terminal"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
