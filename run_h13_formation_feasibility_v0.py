#!/usr/bin/env python3
"""h13 -> h14 Asset Formation Feasibility Surface v0.

Same fixed five Battles. Observation only.

At Day0 h13, record external World-side formation resources:
- cash
- seed stock
- unplaced animal stock
- empty unlocked tiles
- farmer / hand count
- unit positions and units currently standing on empty unlocked tiles

At Day0 h14, record the change in present productive asset composition.

No Action, intention, policy, or causal explanation is read.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body_only
import run_asset_formation_map_v0 as af

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"h13_formation_feasibility_v0_{SEED}_seat{SEAT}.json")
CROPS = tuple(kg.CROPS.keys())
ANIMALS = tuple(kg.ANIMALS.keys())


def unplaced_animals(private):
    out = {a: 0 for a in ANIMALS}
    shed = private.get("shed", {}) or {}
    for a in ANIMALS:
        out[a] += int(shed.get(a, 0) or 0)
    for inv in private.get("inventories", []) or []:
        if not isinstance(inv, dict):
            continue
        for a in ANIMALS:
            out[a] += int(inv.get(a, 0) or 0)
    return out


def unit_positions(farm):
    out = [{"kind": "farmer", "index": 0, "position": af.plain(farm.get("farmer"))}]
    for i, p in enumerate(farm.get("hands", []) or [], start=1):
        out.append({"kind": "hand", "index": i, "position": af.plain(p)})
    return out


def tile_at(farm, pos):
    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
        return None
    x, y = int(pos[0]), int(pos[1])
    rows = farm.get("tiles", []) or []
    if y < 0 or y >= len(rows):
        return None
    row = rows[y] or []
    if x < 0 or x >= len(row):
        return None
    return row[x]


def h13_resources(obs, pidx):
    farm = (obs.get("farms", []) or [])[pidx]
    private = obs.get("private", {}) or {}
    land = af.land_context(farm)
    seeds = {
        c: int((private.get("seeds", {}) or {}).get(c, 0) or 0)
        for c in CROPS
    }
    animals = unplaced_animals(private)
    units = unit_positions(farm)
    units_on_empty = []
    for u in units:
        if tile_at(farm, u["position"]) is None:
            units_on_empty.append(u)

    return {
        "money": float(farm.get("money", 0) or 0),
        "seed_stock": seeds,
        "unplaced_animal_stock": animals,
        "empty_unlocked_tile_count": int(land["empty_unlocked_tile_count"]),
        "unlocked_tile_count": int(land["unlocked_tile_count"]),
        "productive_occupied_tile_count": int(land["productive_occupied_tile_count"]),
        "hands_count": len(farm.get("hands", []) or []),
        "acting_unit_count": 1 + len(farm.get("hands", []) or []),
        "private_inventory_slot_count": len(private.get("inventories", []) or []),
        "unit_positions": units,
        "units_on_empty_tile_count": len(units_on_empty),
        "units_on_empty_tiles": units_on_empty,
    }


def composition(obs, pidx, day):
    farm = (obs.get("farms", []) or [])[pidx]
    instances = []
    for y, row in enumerate(farm.get("tiles", []) or []):
        for x, tile in enumerate(row or []):
            z = af.asset_instance(tile, x, y, day)
            if z is not None:
                instances.append(z)
    s = af.summarize(instances)
    return {typ: int(s[typ]["present_asset_count"]) for typ in s}


def delta(a, b):
    return {k: int(b.get(k, 0)) - int(a.get(k, 0)) for k in sorted(set(a) | set(b))}


def main():
    af.configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[SEAT] = body_only.agent
    env.run(players)

    found = {}
    for step in getattr(env, "steps", []) or []:
        if not isinstance(step, (list, tuple)) or len(step) < 2:
            continue
        obs = [af.plain(af.getv(step[p], "observation")) for p in (0, 1)]
        if not all(isinstance(o, dict) for o in obs):
            continue
        day = int(obs[0].get("day", 0) or 0)
        hour = int(obs[0].get("hour", 0) or 0)
        if day == 0 and hour in (13, 14) and hour not in found:
            found[hour] = obs

    if set(found) != {13, 14}:
        raise SystemExit(f"Missing h13/h14 snapshots: {sorted(found)}")

    sides = {}
    for label, pidx in (("self", SEAT), ("opponent", 1 - SEAT)):
        r13 = h13_resources(found[13][pidx], pidx)
        c13 = composition(found[13][pidx], pidx, 0)
        c14 = composition(found[14][pidx], pidx, 0)
        sides[label] = {
            "h13_resources": r13,
            "h13_composition": c13,
            "h14_composition": c14,
            "h13_to_h14_present_asset_delta": delta(c13, c14),
        }

    opp_added = {
        k: v for k, v in sides["opponent"]["h13_to_h14_present_asset_delta"].items()
        if v > 0
    }

    # This is deliberately only a material-count comparison.
    self_material_check = {
        "opponent_added_assets": opp_added,
        "self_h13_seed_stock_for_added_crops": {
            k: sides["self"]["h13_resources"]["seed_stock"].get(k, 0)
            for k in opp_added if k in CROPS
        },
        "self_h13_unplaced_stock_for_added_animals": {
            k: sides["self"]["h13_resources"]["unplaced_animal_stock"].get(k, 0)
            for k in opp_added if k in ANIMALS
        },
        "self_h13_total_added_asset_count_reference": sum(opp_added.values()),
        "self_h13_empty_unlocked_tile_count": sides["self"]["h13_resources"]["empty_unlocked_tile_count"],
        "self_h13_units_on_empty_tile_count": sides["self"]["h13_resources"]["units_on_empty_tile_count"],
        "self_h13_acting_unit_count": sides["self"]["h13_resources"]["acting_unit_count"],
    }

    rewards = [float(x.reward) for x in env.state]
    payload = {
        "schema": "kaggriculture.strong-origin-v2.h13-formation-feasibility.v0",
        "seed": SEED,
        "seat": SEAT,
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "self": sides["self"],
        "opponent": sides["opponent"],
        "material_reference": self_material_check,
        "boundary": [
            "This probe reads only Day0 h13 World resources and h13->h14 productive asset State change.",
            "Seed stock / unplaced animal stock are immediate material stock. Cash is reported separately and is not treated as same-turn plant/place material.",
            "units_on_empty_tile_count is a positional State fact, not proof that a particular requested asset can be formed on that turn.",
            "material_reference compares raw counts only; it is not a legal reachability or counterfactual execution proof.",
            "No Action, purchase/plant/place decision, movement diagnosis, policy, motive, Candidate, or causal conclusion is introduced.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("H13_FORMATION_FEASIBILITY " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "self_money": sides["self"]["h13_resources"]["money"],
        "opp_money": sides["opponent"]["h13_resources"]["money"],
        "self_seed_stock": sides["self"]["h13_resources"]["seed_stock"],
        "opp_seed_stock": sides["opponent"]["h13_resources"]["seed_stock"],
        "self_unplaced_animals": sides["self"]["h13_resources"]["unplaced_animal_stock"],
        "opp_unplaced_animals": sides["opponent"]["h13_resources"]["unplaced_animal_stock"],
        "self_empty": sides["self"]["h13_resources"]["empty_unlocked_tile_count"],
        "opp_empty": sides["opponent"]["h13_resources"]["empty_unlocked_tile_count"],
        "self_units_on_empty": sides["self"]["h13_resources"]["units_on_empty_tile_count"],
        "opp_units_on_empty": sides["opponent"]["h13_resources"]["units_on_empty_tile_count"],
        "self_delta": sides["self"]["h13_to_h14_present_asset_delta"],
        "opp_delta": sides["opponent"]["h13_to_h14_present_asset_delta"],
        "terminal": payload["terminal"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
