#!/usr/bin/env python3
"""Aggregate SB-01 Economic Layers from raw State exports.

Layer boundary:
  Cash                  = Fact
  Liquidatable Inventory= current displayed-price mark of SELL-able inventory
  Committed Production  = current-price biological/base-production potential
  Uncommitted Capacity  = physical remaining hand/tile-time measures

No single total-economic-value score is created.
No causal/adoption conclusion is generated here.
"""
import glob
import json
import statistics
import sys
from pathlib import Path

DAYS = (6, 8, 10, 12)
SEASON_DAYS = 30
TURNS_PER_DAY = 24

# Confirmed public rules used by WB-0001; verified against Kaggriculture env.
CROPS = {
    "WHEAT":      {"seed": 10,  "first": 2,  "max_day": 4,  "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20,  "first": 2,  "max_day": 3,  "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50,  "first": 8,  "max_day": 8,  "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first": 10, "max_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80,  "first": 10, "max_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}
ANIMALS = {
    "GOOSE": {"cost": 300, "first": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW":   {"cost": 400, "first": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "first": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
RULE_PROVENANCE = "Kaggle/kaggle-environments kaggriculture.py @ b2405492c8403f6649f9317290f215e0290a2425"


def _inventory_quantities(private):
    q = {item: 0 for item in PRODUCTS}
    shed = private.get("shed", {}) or {}
    for item in PRODUCTS:
        q[item] += int(shed.get(item, 0) or 0)
    for inv in private.get("inventories", []) or []:
        if not isinstance(inv, dict):
            continue
        for item in PRODUCTS:
            q[item] += int(inv.get(item, 0) or 0)
    return q


def _nonongoing_crop_remaining(tile, day, rule):
    """Current field yield + remaining no-fertilizer WATER yield potential.

    Assumptions: plant survives, WATER can be supplied as needed, harvest occurs
    before decay, no future fertilizer bonus.
    """
    current = int(tile.get("yield_units", 0) or 0)
    planted = int(tile.get("planted_day", day) or 0)
    window_start = (rule["max_day"] + 1) // 2
    first_water_day = max(day, planted + window_start)
    last_water_day = min(SEASON_DAYS - 1, planted + rule["max_day"])
    opportunities = max(0, last_water_day - first_water_day + 1)
    potential = min(rule["max_yield"], current + opportunities)
    return current, opportunities, potential


def _ongoing_crop_remaining(tile, day, rule):
    """Current held yield + future base production events through season end.

    Assumptions: enough WATER to keep plant alive, timely harvest prevents
    max-held blocking, no future fertilizer bonus.
    """
    current = int(tile.get("yield_units", 0) or 0)
    planted = int(tile.get("planted_day", day) or 0)
    events = []
    for n in range(rule["max_yield"]):
        state_day = planted + rule["first"] + n * rule["interval"]
        if day < state_day <= SEASON_DAYS:
            events.append(state_day)
    potential = current + len(events)
    return current, len(events), potential


def _animal_remaining(tile, day, rule):
    """Current held product + future base production opportunities.

    Assumptions: animal survives with adequate FEED, timely harvest prevents
    max-held blocking, CARE bonus is excluded.
    """
    current = int(tile.get("yield_units", 0) or 0)
    placed = int(tile.get("placed_day", day) or 0)
    events = []
    state_day = placed + rule["first"]
    while state_day <= SEASON_DAYS:
        if state_day > day:
            events.append(state_day)
        state_day += rule["interval"]
    potential = current + len(events)
    return current, len(events), potential


def derive_side(obs):
    player = int(obs["player"])
    farm = obs["farms"][player]
    private = obs.get("private", {}) or {}
    prices = (obs.get("market", {}) or {}).get("prices", {}) or {}
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)

    inventory_q = _inventory_quantities(private)
    inventory_by_item = {
        item: {
            "quantity": inventory_q[item],
            "price": float(prices.get(item, 0) or 0),
            "mark": inventory_q[item] * float(prices.get(item, 0) or 0),
        }
        for item in PRODUCTS
    }
    inventory_mark = sum(v["mark"] for v in inventory_by_item.values())

    crop_count = {c: 0 for c in CROPS}
    crop_units = {c: 0 for c in CROPS}
    crop_future_opportunities = {c: 0 for c in CROPS}
    crop_mark_by_type = {c: 0.0 for c in CROPS}
    crop_detail = []

    animal_count = {a: 0 for a in ANIMALS}
    animal_units = {a: 0 for a in ANIMALS}
    animal_future_opportunities = {a: 0 for a in ANIMALS}
    animal_mark_by_type = {a: 0.0 for a in ANIMALS}
    animal_detail = []

    empty_unlocked_tiles = 0
    unlocked_tiles = 0
    weed_tiles = 0

    for y, row in enumerate(farm.get("tiles", []) or []):
        for x, tile in enumerate(row or []):
            if tile == "LOCKED":
                continue
            unlocked_tiles += 1
            if tile is None:
                empty_unlocked_tiles += 1
                continue
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                weed_tiles += 1
            if not isinstance(tile, dict):
                continue

            crop = tile.get("crop")
            if crop in CROPS:
                rule = CROPS[crop]
                crop_count[crop] += 1
                if rule["ongoing"]:
                    held, opps, potential = _ongoing_crop_remaining(tile, day, rule)
                else:
                    held, opps, potential = _nonongoing_crop_remaining(tile, day, rule)
                price = float(prices.get(crop, 0) or 0)
                mark = potential * price
                crop_units[crop] += potential
                crop_future_opportunities[crop] += opps
                crop_mark_by_type[crop] += mark
                crop_detail.append({
                    "x": x, "y": y, "crop": crop,
                    "planted_day": int(tile.get("planted_day", 0) or 0),
                    "current_yield_units": held,
                    "remaining_base_or_water_opportunities": opps,
                    "potential_units": potential,
                    "current_price": price,
                    "current_price_potential_mark": mark,
                })

            animal = tile.get("animal")
            if animal in ANIMALS:
                rule = ANIMALS[animal]
                animal_count[animal] += 1
                held, opps, potential = _animal_remaining(tile, day, rule)
                price = float(prices.get(rule["product"], 0) or 0)
                mark = potential * price
                animal_units[animal] += potential
                animal_future_opportunities[animal] += opps
                animal_mark_by_type[animal] += mark
                animal_detail.append({
                    "x": x, "y": y, "animal": animal,
                    "placed_day": int(tile.get("placed_day", 0) or 0),
                    "current_yield_units": held,
                    "remaining_base_production_opportunities": opps,
                    "potential_product_units": potential,
                    "product": rule["product"],
                    "current_price": price,
                    "current_price_potential_mark": mark,
                    "consecutive_unfed": int(tile.get("consecutive_unfed", 0) or 0),
                    "pending_care_bonus_excluded": int(tile.get("pending_care_bonus", 0) or 0),
                })

    crop_mark = sum(crop_mark_by_type.values())
    animal_mark = sum(animal_mark_by_type.values())
    remaining_turns = max(0, (SEASON_DAYS - day) * TURNS_PER_DAY - hour)
    remaining_today_turns = max(0, TURNS_PER_DAY - hour)
    hands = len(farm.get("hands", []) or [])
    seeds = {
        c: int((private.get("seeds", {}) or {}).get(c, 0) or 0)
        for c in CROPS
    }

    return {
        "day": day,
        "hour": hour,
        "cash": float(farm.get("money", 0) or 0),
        "liquidatable_inventory": {
            "display_price_mark": inventory_mark,
            "by_item": inventory_by_item,
        },
        "committed_production": {
            "crop_current_price_potential_mark": crop_mark,
            "animal_base_current_price_potential_mark": animal_mark,
            "same_basis_subtotal": crop_mark + animal_mark,
            "crop_count": crop_count,
            "crop_potential_units": crop_units,
            "crop_remaining_opportunities": crop_future_opportunities,
            "crop_mark_by_type": crop_mark_by_type,
            "animal_count": animal_count,
            "animal_potential_units": animal_units,
            "animal_remaining_base_opportunities": animal_future_opportunities,
            "animal_mark_by_type": animal_mark_by_type,
            "crop_detail": crop_detail,
            "animal_detail": animal_detail,
        },
        "uncommitted_capacity": {
            "unlocked_tiles": unlocked_tiles,
            "empty_unlocked_tiles": empty_unlocked_tiles,
            "weed_tiles": weed_tiles,
            "remaining_season_turns": remaining_turns,
            "remaining_empty_tile_turns": empty_unlocked_tiles * remaining_turns,
            "current_hands": hands,
            "remaining_hand_turns_current_hires_today": hands * remaining_today_turns,
            "remaining_main_farmer_turns_today": remaining_today_turns,
            "remaining_existing_unit_turns_today": (1 + hands) * remaining_today_turns,
        },
        "seed_inventory_fact": seeds,
    }


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def _median(xs):
    return statistics.median(xs) if xs else None


def layer_summary(rows, getter):
    self_vals = [getter(r["self"]) for r in rows]
    opp_vals = [getter(r["opponent"]) for r in rows]
    gaps = [o - s for s, o in zip(self_vals, opp_vals)]
    return {
        "self_absolute_mean": _mean(self_vals),
        "opponent_absolute_mean": _mean(opp_vals),
        "mean_gap_opponent_minus_self": _mean(gaps),
        "median_gap_opponent_minus_self": _median(gaps),
        "opponent_ahead_cases": sum(g > 0 for g in gaps),
        "self_ahead_cases": sum(g < 0 for g in gaps),
        "equal_cases": sum(g == 0 for g in gaps),
        "min_gap": min(gaps) if gaps else None,
        "max_gap": max(gaps) if gaps else None,
    }


def dict_metric_summary(rows, section, field, keys):
    out = {}
    for key in keys:
        out[key] = layer_summary(
            rows,
            lambda side, k=key: side["committed_production"][field].get(k, 0),
        )
    return out


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    files = sorted(root.glob("sb01_economic_input_export_*.json"))
    if not files:
        files = [Path(p) for p in glob.glob(str(root / "**" / "sb01_economic_input_export_*.json"), recursive=True)]
    if not files:
        raise SystemExit("No SB-01 economic input export files found")

    cases = []
    missing = []
    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        seed = int(raw["seed"])
        seat = int(raw["seat"])
        if any(str(d) not in raw["state_export"].get(str(seat), {}) for d in DAYS) or any(
            str(d) not in raw["state_export"].get(str(1-seat), {}) for d in DAYS
        ):
            missing.append(seed)
            continue

        day_rows = {}
        for day in DAYS:
            self_obs = raw["state_export"][str(seat)][str(day)]["observation"]
            opp_obs = raw["state_export"][str(1-seat)][str(day)]["observation"]
            day_rows[str(day)] = {
                "self": derive_side(self_obs),
                "opponent": derive_side(opp_obs),
            }

        cases.append({
            "seed": seed,
            "seat": seat,
            "terminal": raw["terminal_result"],
            "days": day_rows,
        })

    if missing:
        raise SystemExit(f"Missing target State for seeds: {missing}")

    aggregate_days = {}
    for day in DAYS:
        rows = [c["days"][str(day)] for c in cases]
        cash = layer_summary(rows, lambda s: s["cash"])
        inventory = layer_summary(rows, lambda s: s["liquidatable_inventory"]["display_price_mark"])
        crop = layer_summary(rows, lambda s: s["committed_production"]["crop_current_price_potential_mark"])
        animal = layer_summary(rows, lambda s: s["committed_production"]["animal_base_current_price_potential_mark"])
        committed = layer_summary(rows, lambda s: s["committed_production"]["same_basis_subtotal"])
        tile_turns = layer_summary(rows, lambda s: s["uncommitted_capacity"]["remaining_empty_tile_turns"])

        cash_nonbehind = []
        hidden_committed = []
        for r in rows:
            cash_gap = r["opponent"]["cash"] - r["self"]["cash"]
            committed_gap = (
                r["opponent"]["committed_production"]["same_basis_subtotal"]
                - r["self"]["committed_production"]["same_basis_subtotal"]
            )
            if cash_gap <= 0:
                cash_nonbehind.append(r)
                if committed_gap > 0:
                    hidden_committed.append(committed_gap)

        aggregate_days[str(day)] = {
            "cash": cash,
            "liquidatable_inventory_display_mark": inventory,
            "committed_crop_current_price_potential_mark": crop,
            "committed_animal_base_current_price_potential_mark": animal,
            "committed_production_same_basis_subtotal": committed,
            "uncommitted_empty_tile_turns": tile_turns,
            "crop_mark_by_type": dict_metric_summary(rows, "committed_production", "crop_mark_by_type", CROPS),
            "crop_count_by_type": dict_metric_summary(rows, "committed_production", "crop_count", CROPS),
            "animal_mark_by_type": dict_metric_summary(rows, "committed_production", "animal_mark_by_type", ANIMALS),
            "animal_count_by_type": dict_metric_summary(rows, "committed_production", "animal_count", ANIMALS),
            "cross_layer": {
                "self_cash_not_behind_cases": len(cash_nonbehind),
                "among_them_opponent_committed_production_ahead_cases": len(hidden_committed),
                "mean_hidden_committed_gap_when_present": _mean(hidden_committed) if hidden_committed else None,
                "median_hidden_committed_gap_when_present": _median(hidden_committed) if hidden_committed else None,
            },
        }

    terminals_self = [float(c["terminal"]["self"]) for c in cases]
    terminals_opp = [float(c["terminal"]["opponent"]) for c in cases]
    terminals_margin = [float(c["terminal"]["margin"]) for c in cases]

    payload = {
        "schema": "kaggriculture.sb01.economic-layers.v0",
        "benchmark": "strength_benchmark_v0",
        "snapshot": "SB-01",
        "battle_count": len(cases),
        "rule_provenance": RULE_PROVENANCE,
        "terminal_absolute": {
            "mean_self": _mean(terminals_self),
            "mean_opponent": _mean(terminals_opp),
            "mean_margin": _mean(terminals_margin),
            "median_self": _median(terminals_self),
            "median_opponent": _median(terminals_opp),
            "median_margin": _median(terminals_margin),
            "wins": sum(m > 0 for m in terminals_margin),
            "losses": sum(m < 0 for m in terminals_margin),
            "draws": sum(m == 0 for m in terminals_margin),
        },
        "days": aggregate_days,
        "cases": cases,
        "valuation_assumptions": {
            "inventory": [
                "SELL-able inventory only; seeds and unplaced animals are excluded.",
                "Mark uses current displayed prices and is not realized liquidation Cash.",
            ],
            "crop": [
                "Current displayed crop price is frozen for valuation.",
                "Existing in-field yield is included.",
                "Non-ongoing crops assume remaining no-fertilizer WATER opportunities can be supplied and harvest occurs before decay.",
                "Ongoing crops assume survival and timely harvest so max-held does not block future base production.",
                "Future fertilizer bonus, worker movement/action cost, market interaction and future price changes are excluded.",
            ],
            "animal": [
                "Current displayed product price is frozen for valuation.",
                "Existing held product plus future base production opportunities through season end are included.",
                "Animal survival with adequate FEED and timely harvest is assumed.",
                "CARE bonus, feed replacement cost, fertilizer value, future market interaction and future price changes are excluded.",
            ],
            "capacity": [
                "Empty-tile turns are a physical capacity measure, not money.",
                "Current hand-turns only count hands already hired at the snapshot; day-start snapshots reset hands to zero.",
                "No Cash value is assigned to capacity in this v0.",
            ],
        },
        "boundary": [
            "Cash is Fact.",
            "Inventory/Production marks are Valuation with explicit assumptions, not realized profit.",
            "Capacity stays physical and is not added to monetary marks.",
            "No total economic score is formed.",
            "No causal claim or Combat Rule is generated by this analysis.",
        ],
    }

    out_json = Path("sb01_economic_layers_v0.json")
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    compact = {
        "battle_count": len(cases),
        "terminal": payload["terminal_absolute"],
        "days": {
            d: {
                "cash_gap": aggregate_days[d]["cash"]["mean_gap_opponent_minus_self"],
                "inventory_gap": aggregate_days[d]["liquidatable_inventory_display_mark"]["mean_gap_opponent_minus_self"],
                "crop_gap": aggregate_days[d]["committed_crop_current_price_potential_mark"]["mean_gap_opponent_minus_self"],
                "animal_gap": aggregate_days[d]["committed_animal_base_current_price_potential_mark"]["mean_gap_opponent_minus_self"],
                "committed_gap": aggregate_days[d]["committed_production_same_basis_subtotal"]["mean_gap_opponent_minus_self"],
                "self_cash_not_behind": aggregate_days[d]["cross_layer"]["self_cash_not_behind_cases"],
                "hidden_committed_ahead": aggregate_days[d]["cross_layer"]["among_them_opponent_committed_production_ahead_cases"],
            }
            for d in map(str, DAYS)
        },
    }
    print("SB01_ECONOMIC_LAYERS " + json.dumps(compact, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
