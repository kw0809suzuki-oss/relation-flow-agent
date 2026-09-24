#!/usr/bin/env python3
"""Harvestable STRAWBERRY Asset -> HARVEST Gate v0.

Fixed five-Battle Day20->24 observation.

Public-world quantities only:
- turn-start harvestable STRAWBERRY yield stock on crop tiles
- new harvestable STRAWBERRY yield added by public daily refresh
- exact STRAWBERRY units added to carried inventory by HARVEST
- harvestable yield losses/destruction observed on the World surface

No agent motive or internal policy interpretation is introduced.
"""
import json
import os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as body_only

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"harvestable_strawberry_gate_v0_{SEED}_seat{SEAT}.json")

turn_start = [[], []]
harvest_events = []
refresh_events = []
loss_events = []
farm_to_player = {}
main_calls = 0
current_player = None
current_day = None
current_hour = None

_original_apply = kg._apply_unit_action
_original_refresh = kg._daily_refresh_plants
_original_decay = kg._decay_plants


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


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"
    body_only.reset_telemetry()


def strawberry_tile_yield(tile, day):
    if not isinstance(tile, dict):
        return 0
    if tile.get("kind") != "PLANT" or tile.get("crop") != "STRAWBERRY":
        return 0
    if day - int(tile.get("planted_day", day)) < int(kg.CROPS["STRAWBERRY"]["first_yield_day"]):
        return 0
    return max(0, int(tile.get("yield_units", 0) or 0))


def harvestable_stock(farm, day):
    total = 0
    cells = []
    for y, row in enumerate(farm.get("tiles", []) or []):
        for x, tile in enumerate(row):
            q = strawberry_tile_yield(tile, day)
            if q > 0:
                total += q
                cells.append({"x": x, "y": y, "yield_units": q})
    return total, cells


def inv_qty(private, idx):
    invs = private.get("inventories", []) or []
    if idx >= len(invs) or not isinstance(invs[idx], dict):
        return 0
    return int(invs[idx].get("STRAWBERRY", 0) or 0)


def wrapped_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity=100):
    global main_calls, current_player, current_day, current_hour

    if idx == 0:
        player = main_calls % 2
        hour = (main_calls // 2) % int(turns_per_day)
        main_calls += 1
        current_player = player
        current_day = int(day)
        current_hour = int(hour)
        farm_to_player[id(farm)] = player

        if 20 <= day < 24:
            stock, cells = harvestable_stock(farm, day)
            turn_start[player].append({
                "day": int(day),
                "hour": int(hour),
                "harvestable_yield_stock": stock,
                "harvestable_cells": cells,
            })

    player = farm_to_player.get(id(farm), current_player)
    op = action[0] if isinstance(action, list) and action else None
    before_inv = inv_qty(private, idx)
    before_stock, _ = harvestable_stock(farm, day)

    pos = kg._farmer_position(farm, idx)
    before_tile = None
    if pos is not None:
        x, y = int(pos[0]), int(pos[1])
        before_tile = plain(farm["tiles"][y][x])

    _original_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)

    after_inv = inv_qty(private, idx)
    after_stock, _ = harvestable_stock(farm, day)
    delta_inv = after_inv - before_inv

    if 20 <= day < 24 and op == "HARVEST" and delta_inv > 0:
        harvest_events.append({
            "player": int(player),
            "day": int(day),
            "hour": int(current_hour),
            "inventory_index": int(idx),
            "units_to_carried": int(delta_inv),
            "position_before": plain(pos),
            "tile_before": before_tile,
        })

    if 20 <= day < 24 and op != "HARVEST" and after_stock < before_stock:
        loss_events.append({
            "player": int(player),
            "day": int(day),
            "hour": int(current_hour),
            "source": "unit_action",
            "action": plain(action),
            "harvestable_stock_before": before_stock,
            "harvestable_stock_after": after_stock,
            "loss": before_stock - after_stock,
        })


def tile_yields(farm, day):
    out = {}
    for y, row in enumerate(farm.get("tiles", []) or []):
        for x, tile in enumerate(row):
            out[(x, y)] = strawberry_tile_yield(tile, day)
    return out


def wrapped_refresh(farm, day, turns_per_day):
    player = farm_to_player.get(id(farm))
    before = tile_yields(farm, day)
    _original_refresh(farm, day, turns_per_day)
    after = tile_yields(farm, day + 1)

    if player is not None and 19 <= day <= 23:
        added = 0
        lost = 0
        changes = []
        for pos in sorted(set(before) | set(after)):
            b = before.get(pos, 0)
            a = after.get(pos, 0)
            if a != b:
                d = a - b
                if d > 0:
                    added += d
                else:
                    lost += -d
                changes.append({"x": pos[0], "y": pos[1], "before": b, "after": a, "delta": d})
        refresh_events.append({
            "player": int(player),
            "current_day": int(day),
            "next_day": int(day + 1),
            "added_harvestable_yield": int(added),
            "lost_harvestable_yield": int(lost),
            "changes": changes,
        })


def wrapped_decay(farm, step):
    player = farm_to_player.get(id(farm))
    day = int(step) // 24
    before = tile_yields(farm, day)
    _original_decay(farm, step)
    after = tile_yields(farm, day)
    if player is not None and 20 <= day < 24:
        lost = sum(max(0, before[p] - after.get(p, 0)) for p in before)
        if lost:
            loss_events.append({
                "player": int(player),
                "day": int(day),
                "hour": int(step) % 24,
                "source": "decay",
                "loss": int(lost),
            })


def main():
    global main_calls, current_player, current_day, current_hour
    configure()
    turn_start[0].clear(); turn_start[1].clear()
    harvest_events.clear(); refresh_events.clear(); loss_events.clear(); farm_to_player.clear()
    main_calls = 0; current_player = None; current_day = None; current_hour = None
    exact.ledger = [defaultdict(float), defaultdict(float)]
    exact.units = [defaultdict(int), defaultdict(int)]
    exact.events = []

    kg._apply_unit_action = wrapped_apply
    kg._daily_refresh_plants = wrapped_refresh
    kg._decay_plants = wrapped_decay

    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    try:
        players = [basecfg.OPPONENT, basecfg.OPPONENT]
        players[SEAT] = body_only.agent
        env.run(players)
    finally:
        kg._apply_unit_action = _original_apply
        kg._daily_refresh_plants = _original_refresh
        kg._decay_plants = _original_decay

    rewards = [float(x.reward) for x in env.state]

    by_player = {}
    for p in (0, 1):
        starts = turn_start[p]
        day20_start = next(
            (x["harvestable_yield_stock"] for x in starts if x["day"] == 20 and x["hour"] == 0),
            None,
        )
        day24_endpoint_refresh = sum(
            e["added_harvestable_yield"]
            for e in refresh_events if e["player"] == p and e["current_day"] == 23
        )
        additions_available_inside = sum(
            e["added_harvestable_yield"]
            for e in refresh_events
            if e["player"] == p and 20 <= e["current_day"] < 23
        )
        refresh_losses_inside = sum(
            e["lost_harvestable_yield"]
            for e in refresh_events
            if e["player"] == p and 20 <= e["current_day"] < 23
        )
        harvested = sum(
            e["units_to_carried"] for e in harvest_events if e["player"] == p
        )
        other_losses = sum(
            e["loss"] for e in loss_events if e["player"] == p
        )
        supply = (day20_start or 0) + additions_available_inside
        by_player[p] = {
            "day20_h0_harvestable_stock": day20_start,
            "refresh_added_available_before_day24": additions_available_inside,
            "harvestable_supply_available_in_window": supply,
            "harvest_to_carried_units": harvested,
            "refresh_harvestable_losses_inside_window": refresh_losses_inside,
            "other_harvestable_losses_inside_window": other_losses,
            "day24_h0_endpoint_refresh_addition_excluded": day24_endpoint_refresh,
            "max_turn_start_harvestable_stock": max(
                [x["harvestable_yield_stock"] for x in starts] or [0]
            ),
            "mean_turn_start_harvestable_stock": (
                sum(x["harvestable_yield_stock"] for x in starts) / len(starts)
                if starts else None
            ),
        }

    payload = {
        "schema": "kaggriculture.strong-origin-v2.harvestable-strawberry-gate.v0",
        "seed": SEED,
        "seat": SEAT,
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "window": "Day20 h0 inclusive -> Day24 h0 exclusive for actions",
        "by_player": by_player,
        "turn_start_harvestable_stock": turn_start,
        "harvest_events": harvest_events,
        "refresh_events": refresh_events,
        "loss_events": loss_events,
        "boundary": [
            "Harvestable STRAWBERRY yield means a public World tile with kind=PLANT, crop=STRAWBERRY, age >= first_yield_day, and yield_units > 0.",
            "harvestable_supply_available_in_window = Day20 h0 starting harvestable stock + positive yield additions from end-of-day refreshes that become available on Days21-23.",
            "The end-of-Day23 refresh that becomes available at Day24 h0 is recorded but excluded from the Day20->24 action window supply.",
            "Turn-start harvestable stock is a stock snapshot and is never summed across time as supply.",
            "harvest_to_carried_units counts only exact inventory additions produced by HARVEST actions on STRAWBERRY.",
            "No explanation of why a HARVEST action was or was not chosen is introduced.",
            "No Candidate or adoption decision is introduced.",
        ],
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("HARVESTABLE_STRAWBERRY_GATE " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "terminal": payload["terminal"],
        "self": by_player[SEAT],
        "opponent": by_player[1-SEAT],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
