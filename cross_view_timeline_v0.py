#!/usr/bin/env python3
"""Cross-View Timeline v0 for Kaggriculture replay JSON.

Observation-only. No policy mutation and no causal inference.

The replay action stored at step s is treated as the action that transforms
observation s-1 into observation s. This matches the transition semantics
verified from raw Kaggriculture replays.

v0 intentionally does NOT:
- infer a cycle id,
- treat SELL requests as executed sales,
- declare state re-convergence,
- rank or score players.

It emits a common 30-day/720-turn coordinate system with:
- normalized state summaries,
- before/action/after transition deltas,
- direct productive/output/harvest witnesses,
- same-timestamp player differences,
- stable physical lineage keys for later overlays.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

CROPS = ("CARROT", "MELON", "STRAWBERRY", "TOMATO", "WHEAT")
ANIMALS = ("COW", "SHEEP", "GOOSE")
PRODUCTS = (
    "CARROT",
    "EGG",
    "FERTILIZER",
    "MELON",
    "MILK",
    "STRAWBERRY",
    "TOMATO",
    "WHEAT",
    "WOOL",
)


def n(v: Any) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def i(v: Any) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


def count_dict(values: Mapping[str, Any], keys: Iterable[str]) -> Dict[str, int]:
    return {k: i(values.get(k, 0)) for k in keys if i(values.get(k, 0)) != 0}


def add_counts(dst: Counter, src: Mapping[str, Any], keys: Iterable[str]) -> None:
    for k in keys:
        q = i(src.get(k, 0))
        if q:
            dst[k] += q


def own_observation(step: List[Mapping[str, Any]], player: int) -> Mapping[str, Any]:
    return (step[player] or {}).get("observation", {}) or {}


def own_farm(obs: Mapping[str, Any], player: int) -> Mapping[str, Any]:
    farms = obs.get("farms", []) or []
    return farms[player] if player < len(farms) and isinstance(farms[player], Mapping) else {}


def private_state(obs: Mapping[str, Any]) -> Mapping[str, Any]:
    p = obs.get("private", {}) or {}
    return p if isinstance(p, Mapping) else {}


def tile_records(farm: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for y, row in enumerate(farm.get("tiles", []) or []):
        for x, tile in enumerate(row or []):
            if not isinstance(tile, Mapping):
                continue
            key = f"{x},{y}"
            if tile.get("kind") == "PLANT" and tile.get("crop"):
                out[key] = {
                    "position": [x, y],
                    "kind": "PLANT",
                    "crop": str(tile.get("crop")),
                    "planted_day": i(tile.get("planted_day")),
                    "yield_units": i(tile.get("yield_units")),
                    "lineage_key": f"crop:{tile.get('crop')}:{x},{y}:d{i(tile.get('planted_day'))}",
                }
            elif tile.get("animal"):
                out[key] = {
                    "position": [x, y],
                    "kind": "ANIMAL",
                    "animal": str(tile.get("animal")),
                    "placed_day": i(tile.get("placed_day")),
                    "yield_units": i(tile.get("yield_units")),
                    "lineage_key": f"animal:{tile.get('animal')}:{x},{y}:d{i(tile.get('placed_day'))}",
                }
    return out


def state_summary(obs: Mapping[str, Any], player: int) -> Dict[str, Any]:
    farm = own_farm(obs, player)
    private = private_state(obs)
    tiles = tile_records(farm)

    plant_comp = Counter()
    animal_comp = Counter()
    yield_comp = Counter()
    for t in tiles.values():
        if t["kind"] == "PLANT":
            plant_comp[t["crop"]] += 1
            yield_comp[t["crop"]] += t["yield_units"]
        else:
            animal_comp[t["animal"]] += 1
            yield_comp[t["animal"]] += t["yield_units"]

    shed = private.get("shed", {}) or {}
    carried = Counter()
    for inv in private.get("inventories", []) or []:
        if isinstance(inv, Mapping):
            add_counts(carried, inv, PRODUCTS)

    seed_comp = count_dict(private.get("seeds", {}) or {}, CROPS)
    shed_products = count_dict(shed, PRODUCTS)
    unplaced_animals = count_dict(shed, ANIMALS)

    unlocked = list(farm.get("unlocked_quadrants", []) or [])
    return {
        "cash": n(farm.get("money", 0)),
        "hands": len(farm.get("hands", []) or []),
        "land_quadrants": len(unlocked),
        "unlocked_quadrants": unlocked,
        "plant_count": sum(plant_comp.values()),
        "animal_count": sum(animal_comp.values()),
        "plant_composition": dict(sorted(plant_comp.items())),
        "animal_composition": dict(sorted(animal_comp.items())),
        "yield_units_total": sum(yield_comp.values()),
        "yield_composition": dict(sorted(yield_comp.items())),
        "seed_units_total": sum(seed_comp.values()),
        "seed_composition": seed_comp,
        "shed_product_units": sum(shed_products.values()),
        "shed_products": shed_products,
        "unplaced_animal_units": sum(unplaced_animals.values()),
        "unplaced_animals": unplaced_animals,
        "carried_product_units": sum(carried.values()),
        "carried_products": dict(sorted(carried.items())),
        "tiles": tiles,
    }


def dict_numeric_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k in sorted(set(before) | set(after)):
        d = n(after.get(k, 0)) - n(before.get(k, 0))
        if abs(d) > 1e-9:
            out[k] = d
    return out


def action_ops(action: Mapping[str, Any]) -> List[str]:
    ops: List[str] = []
    farmer = action.get("farmer")
    if isinstance(farmer, list) and farmer:
        ops.append(str(farmer[0]))
    for a in action.get("hands", []) or []:
        if isinstance(a, list) and a:
            ops.append(str(a[0]))
    for a in action.get("market", []) or []:
        if isinstance(a, list) and a:
            ops.append(str(a[0]))
    return ops


def market_requests(action: Mapping[str, Any]) -> List[List[Any]]:
    return [list(a) for a in (action.get("market", []) or []) if isinstance(a, list) and a]


def unit_requests(action: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out = []
    f = action.get("farmer")
    if isinstance(f, list) and f:
        out.append({"actor": "farmer", "action": list(f)})
    for idx, a in enumerate(action.get("hands", []) or []):
        if isinstance(a, list) and a:
            out.append({"actor": f"hand:{idx}", "action": list(a)})
    return out


def tile_events(
    before_tiles: Mapping[str, Mapping[str, Any]],
    after_tiles: Mapping[str, Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for key in sorted(set(before_tiles) | set(after_tiles)):
        b = before_tiles.get(key)
        a = after_tiles.get(key)
        if b is None and a is not None:
            out.append(
                {
                    "kind": "asset_appeared",
                    "position": a["position"],
                    "after": a,
                    "lineage_key": a["lineage_key"],
                }
            )
            continue
        if b is not None and a is None:
            out.append(
                {
                    "kind": "asset_disappeared",
                    "position": b["position"],
                    "before": b,
                    "lineage_key": b["lineage_key"],
                }
            )
            continue
        if not b or not a:
            continue
        if b.get("lineage_key") != a.get("lineage_key"):
            out.append(
                {
                    "kind": "asset_replaced",
                    "position": a["position"],
                    "before": b,
                    "after": a,
                }
            )
            continue
        dy = i(a.get("yield_units")) - i(b.get("yield_units"))
        if dy:
            out.append(
                {
                    "kind": "yield_changed",
                    "position": a["position"],
                    "lineage_key": a["lineage_key"],
                    "before_yield": i(b.get("yield_units")),
                    "after_yield": i(a.get("yield_units")),
                    "delta": dy,
                }
            )
    return out


def transition_summary(
    before: Dict[str, Any],
    after: Dict[str, Any],
    action: Mapping[str, Any],
) -> Dict[str, Any]:
    scalar_keys = (
        "cash",
        "hands",
        "land_quadrants",
        "plant_count",
        "animal_count",
        "yield_units_total",
        "seed_units_total",
        "shed_product_units",
        "unplaced_animal_units",
        "carried_product_units",
    )
    scalar_delta = {}
    for k in scalar_keys:
        d = n(after[k]) - n(before[k])
        if abs(d) > 1e-9:
            scalar_delta[k] = d

    composition_delta = {
        "plants": dict_numeric_delta(before["plant_composition"], after["plant_composition"]),
        "animals": dict_numeric_delta(before["animal_composition"], after["animal_composition"]),
        "unplaced_animals": dict_numeric_delta(before["unplaced_animals"], after["unplaced_animals"]),
        "seeds": dict_numeric_delta(before["seed_composition"], after["seed_composition"]),
        "shed": dict_numeric_delta(before["shed_products"], after["shed_products"]),
        "carried": dict_numeric_delta(before["carried_products"], after["carried_products"]),
    }
    composition_delta = {k: v for k, v in composition_delta.items() if v}
    t_events = tile_events(before["tiles"], after["tiles"])

    direct_witnesses: List[Dict[str, Any]] = []
    ops = set(action_ops(action))

    if "BUY_LAND" in ops and after["land_quadrants"] > before["land_quadrants"]:
        direct_witnesses.append(
            {
                "kind": "productive_conversion",
                "subtype": "LAND",
                "evidence": "action+land_state_change",
            }
        )

    if "HIRE" in ops and after["hands"] > before["hands"]:
        direct_witnesses.append(
            {
                "kind": "productive_conversion",
                "subtype": "HIRE",
                "evidence": "action+hands_state_change",
            }
        )

    if "BUY_ANIMAL" in ops and (
        after["animal_count"] > before["animal_count"]
        or after["unplaced_animal_units"] > before["unplaced_animal_units"]
    ):
        direct_witnesses.append(
            {
                "kind": "productive_conversion",
                "subtype": "ANIMAL",
                "evidence": "action+animal_state_change",
            }
        )

    if "BUY_SEED" in ops and after["seed_units_total"] > before["seed_units_total"]:
        direct_witnesses.append(
            {
                "kind": "productive_conversion",
                "subtype": "SEED",
                "evidence": "action+seed_stock_increase",
                "boundary": (
                    "same-turn PLANT can hide a successful BUY_SEED in net seed stock; "
                    "absence of this witness is not evidence of no purchase"
                ),
            }
        )

    for e in t_events:
        if e["kind"] == "asset_appeared":
            direct_witnesses.append(
                {
                    "kind": "productive_state_activated",
                    "lineage_key": e["lineage_key"],
                    "position": e["position"],
                    "asset": e["after"],
                }
            )
        elif e["kind"] == "yield_changed" and e["delta"] > 0:
            direct_witnesses.append(
                {
                    "kind": "output_formed",
                    "lineage_key": e["lineage_key"],
                    "position": e["position"],
                    "units": e["delta"],
                }
            )

    if "HARVEST" in ops:
        harvest_tiles = [
            e
            for e in t_events
            if e["kind"] == "asset_disappeared"
            or (e["kind"] == "yield_changed" and e.get("delta", 0) < 0)
        ]
        if harvest_tiles:
            direct_witnesses.append(
                {
                    "kind": "harvest_boundary",
                    "evidence": "HARVEST_request+tile_output_decrease",
                    "tiles": harvest_tiles,
                }
            )

    requests = market_requests(action)
    return {
        "scalar_delta": scalar_delta,
        "composition_delta": composition_delta,
        "tile_events": t_events,
        "direct_witnesses": direct_witnesses,
        "market_requests": requests,
        "unit_requests": unit_requests(action),
        "sell_requests": [a for a in requests if a and a[0] == "SELL"],
        "buy_requests": [
            a
            for a in requests
            if a and (str(a[0]).startswith("BUY") or a[0] == "HIRE")
        ],
        "boundary": (
            "market requests are requests only; v0 does not label them as executed "
            "without a dedicated lineage witness"
        ),
    }


def difference_view(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    scalar_keys = (
        "cash",
        "hands",
        "land_quadrants",
        "plant_count",
        "animal_count",
        "yield_units_total",
        "seed_units_total",
        "shed_product_units",
        "unplaced_animal_units",
        "carried_product_units",
    )
    scalars = {}
    for k in scalar_keys:
        d = n(b[k]) - n(a[k])
        if abs(d) > 1e-9:
            scalars[k] = d

    comps = {}
    for label, key in (
        ("plants", "plant_composition"),
        ("animals", "animal_composition"),
        ("unplaced_animals", "unplaced_animals"),
        ("seeds", "seed_composition"),
        ("shed", "shed_products"),
        ("carried", "carried_products"),
        ("yield", "yield_composition"),
    ):
        d = dict_numeric_delta(a[key], b[key])
        if d:
            comps[label] = d

    return {
        "orientation": "player1_minus_player0",
        "scalar_delta": scalars,
        "composition_delta": comps,
        "view_difference_empty": not scalars and not comps,
        "boundary": (
            "view_difference_empty means equality only in this compact observation view; "
            "it is not a declaration of full State Re-convergence"
        ),
    }


def build(replay: Mapping[str, Any]) -> Dict[str, Any]:
    steps = replay.get("steps", []) or []
    if not steps:
        raise ValueError("replay has no steps")

    agents = [
        x.get("Name")
        for x in (replay.get("info", {}).get("Agents", []) or [])
    ]
    timeline = []
    prev_state: List[Optional[Dict[str, Any]]] = [None, None]
    witness_counts = Counter()
    difference_nonempty = 0

    for s, step in enumerate(steps):
        obs0 = own_observation(step, 0)
        day = i(obs0.get("day"))
        hour = i(obs0.get("hour"))
        states = [state_summary(own_observation(step, p), p) for p in (0, 1)]

        players = []
        for p in (0, 1):
            action = (step[p] or {}).get("action", {}) or {}
            transition = (
                None
                if prev_state[p] is None
                else transition_summary(prev_state[p], states[p], action)
            )
            if transition:
                for w in transition["direct_witnesses"]:
                    witness_counts[w["kind"]] += 1

            players.append(
                {
                    "player": p,
                    "agent": agents[p] if p < len(agents) else None,
                    "state": states[p],
                    "action": action,
                    "transition_from_previous_step": transition,
                }
            )

        diff = difference_view(states[0], states[1])
        if not diff["view_difference_empty"]:
            difference_nonempty += 1

        timeline.append(
            {
                "step_index": s,
                "day": day,
                "hour": hour,
                "players": players,
                "difference_view": diff,
            }
        )
        prev_state = states

    return {
        "schema": "kaggriculture.cross-view-timeline.v0",
        "source": {
            "episode_id": replay.get("info", {}).get("EpisodeId"),
            "seed": replay.get("info", {}).get("seed"),
            "agents": agents,
            "rewards": replay.get("rewards"),
            "steps": len(steps),
            "turns_per_day": replay.get("configuration", {}).get("turnsPerDay"),
        },
        "semantics": {
            "transition": (
                "action stored at step s is paired with observation s-1 -> observation s"
            ),
            "cycle_view": (
                "v0 emits direct witnesses and lineage keys only; "
                "cycle identity/open/close comes from a later conservative overlay"
            ),
            "difference_view": (
                "same-timestamp compact external state difference, player1 minus player0"
            ),
            "promotion_boundary": (
                "no causal claim, strategy claim, or strength ranking is emitted"
            ),
        },
        "summary": {
            "direct_witness_counts": dict(sorted(witness_counts.items())),
            "turns_with_nonempty_difference_view": difference_nonempty,
            "turns_with_empty_difference_view": len(steps) - difference_nonempty,
        },
        "timeline": timeline,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("replay", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    replay = json.loads(args.replay.read_text(encoding="utf-8"))
    payload = build(replay)
    out = args.out or args.replay.with_name(
        args.replay.stem + "_cross_view_timeline_v0.json"
    )
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"out": str(out), **payload["source"], **payload["summary"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
