#!/usr/bin/env python3
"""NR-01 SCAN v0.

Observation-only fresh Battle scanner for the Current body:
Baseline + WR-02.

For every self turn it records:
  State_t + Current Action_t + interpreter execution result + next observed state.

The scanner never mutates Current's action. It emits a compact candidate event
only when all of these are observed together:
  - multiple Current PLANT requests from the same position,
  - sufficient seed stock for those requests,
  - another empty unlocked tile exists at State_t,
  - at least one request fails in the World as TARGET_TILE_NOT_EMPTY.

The raw trace remains available as an artifact; the aggregate job produces the
small Evidence Packet used by Flow-chan.
"""
import copy
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as current

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"nr01_scan_raw_{SEED}.json")

_current_day = -1
_current_hour = -1
_self_farm_id = None
_self_farm_obj = None
_active_exec_self_farm_id = None
_projected = {}
_order = []
_execution = defaultdict(list)


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


def tile_at(farm, pos):
    if pos is None:
        return None
    x, y = int(pos[0]), int(pos[1])
    try:
        return copy.deepcopy(farm["tiles"][y][x])
    except Exception:
        return None


def unit_positions(me):
    return [tuple(me["farmer"])] + [tuple(x) for x in (me.get("hands", []) or [])]


def empty_positions(me):
    out = []
    for y, row in enumerate(me.get("tiles", []) or []):
        for x, tile in enumerate(row or []):
            if tile is None:
                out.append((x, y))
    return out


def plant_counts(me):
    counts = Counter()
    for row in me.get("tiles", []) or []:
        for tile in row or []:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                counts[str(tile.get("crop"))] += 1
    return dict(counts)


def is_plant(a):
    return isinstance(a, (list, tuple)) and len(a) >= 2 and a[0] == "PLANT"


def reason_for_plant_noop(before_tile, before_seeds, effective_action, projected_action):
    crop = projected_action[1] if len(projected_action) > 1 else None
    if effective_action and effective_action[0] == "PASS":
        return "ATOMIC_PLANT_BLOCKED_OR_FILTERED"
    if before_tile is not None:
        return "TARGET_TILE_NOT_EMPTY"
    if int(before_seeds.get(crop, 0) or 0) <= 0:
        return "NO_SEED"
    return "PLANT_NO_STATE_CHANGE_OTHER"


def _is_self_farm(farm):
    if id(farm) == _self_farm_id:
        return True
    if _self_farm_obj is not None:
        try:
            return farm == _self_farm_obj
        except Exception:
            return False
    return False


def wrapped_apply(original):
    def inner(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity=100):
        global _active_exec_self_farm_id
        key = (_current_day, _current_hour)

        if idx == 0:
            _active_exec_self_farm_id = (
                id(farm) if key in _projected and _is_self_farm(farm) else None
            )
        is_self = id(farm) == _active_exec_self_farm_id

        pos = kg._farmer_position(farm, idx)
        before_tile = tile_at(farm, pos)
        before_seeds = copy.deepcopy(private.get("seeds", {}) or {})
        invs = private.get("inventories", []) or []
        before_inv = copy.deepcopy(invs[idx] if 0 <= idx < len(invs) else {})

        projected_action = None
        if is_self and key in _projected:
            units = _projected[key]["unit_actions"]
            if 0 <= idx < len(units):
                projected_action = copy.deepcopy(units[idx])

        original(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)

        after_pos = kg._farmer_position(farm, idx)
        after_tile = tile_at(farm, after_pos)
        after_seeds = copy.deepcopy(private.get("seeds", {}) or {})
        invs2 = private.get("inventories", []) or []
        after_inv = copy.deepcopy(invs2[idx] if 0 <= idx < len(invs2) else {})

        if is_self and key in _projected:
            changed = (
                before_tile != after_tile
                or before_seeds != after_seeds
                or before_inv != after_inv
                or tuple(pos or ()) != tuple(after_pos or ())
            )
            success = False
            reason = None
            if projected_action:
                op = projected_action[0]
                if op == "PLANT" and len(projected_action) > 1:
                    crop = projected_action[1]
                    success = (
                        isinstance(after_tile, dict)
                        and after_tile.get("kind") == "PLANT"
                        and after_tile.get("crop") == crop
                        and before_tile is None
                    )
                    if not success:
                        reason = reason_for_plant_noop(
                            before_tile, before_seeds, action, projected_action
                        )
                elif op in ("NORTH", "SOUTH", "EAST", "WEST"):
                    success = tuple(pos or ()) != tuple(after_pos or ())
                elif op == "WATER":
                    success = isinstance(after_tile, dict) and bool(after_tile.get("watered_today", False))
                elif op == "HARVEST":
                    success = before_inv != after_inv or before_tile != after_tile
                else:
                    success = changed
            _execution[key].append(
                {
                    "unit_index": idx,
                    "projected_action": plain(projected_action),
                    "effective_action_seen_by_apply": plain(action),
                    "position_before": list(pos) if pos is not None else None,
                    "position_after": list(after_pos) if after_pos is not None else None,
                    "tile_before": plain(before_tile),
                    "tile_after": plain(after_tile),
                    "seed_before": plain(before_seeds),
                    "seed_after": plain(after_seeds),
                    "inventory_before": plain(before_inv),
                    "inventory_after": plain(after_inv),
                    "success": bool(success),
                    "state_changed": bool(changed),
                    "noop_reason": reason,
                }
            )

    return inner


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"
    current.reset_telemetry()


def previous_turns(rows, row_index, unit_indices, n=3):
    out = []
    for prev in rows[max(0, row_index - n): row_index]:
        positions = prev["state_t"]["unit_positions"]
        actions = prev["action_t"]["unit_actions"]
        members = []
        for idx in unit_indices:
            members.append(
                {
                    "unit_index": idx,
                    "position": positions[idx] if idx < len(positions) else None,
                    "action": actions[idx] if idx < len(actions) else None,
                }
            )
        out.append(
            {
                "day": prev["day"],
                "hour": prev["hour"],
                "members": members,
            }
        )
    return out


def seed_acquisitions(rows):
    """Infer realized Current BUY_SEED inflow from State_t -> State_t+1.

    Unit actions execute before market orders. Therefore:
      seed_after_units = seed_before - successful_PLANTs
      realized_market_inflow = seed_next - seed_after_units

    We only call it a Current acquisition when the same turn also contains a
    Current BUY_SEED order for that crop.
    """
    out = []
    for row_index, row in enumerate(rows):
        nxt = row.get("state_t1")
        if nxt is None:
            continue

        successful_plants = Counter()
        for e in row.get("execution_result_t", []):
            a = e.get("projected_action")
            if e.get("success") and is_plant(a):
                successful_plants[str(a[1])] += 1

        issued = Counter()
        full = row.get("action_t", {}).get("full", {}) or {}
        for order in full.get("market", []) or []:
            if isinstance(order, (list, tuple)) and len(order) >= 2 and order[0] == "BUY_SEED":
                qty = int(order[2]) if len(order) >= 3 else 1
                issued[str(order[1])] += qty

        before = row["state_t"].get("seeds", {}) or {}
        after = nxt.get("seeds", {}) or {}
        crops = set(before) | set(after) | set(issued)
        for crop in sorted(crops):
            seed_after_units = int(before.get(crop, 0) or 0) - int(successful_plants.get(crop, 0) or 0)
            inferred_inflow = int(after.get(crop, 0) or 0) - seed_after_units
            if issued.get(crop, 0) > 0 and inferred_inflow > 0:
                out.append({
                    "row_index": row_index,
                    "day": row["day"],
                    "hour": row["hour"],
                    "crop": crop,
                    "issued_qty": int(issued[crop]),
                    "inferred_realized_qty": int(inferred_inflow),
                    "seed_before": int(before.get(crop, 0) or 0),
                    "seed_next": int(after.get(crop, 0) or 0),
                })
    return out


def build_scan_events(rows):
    events = []
    acquisitions = seed_acquisitions(rows)
    for row_index, row in enumerate(rows):
        positions = row["state_t"]["unit_positions"]
        actions = row["action_t"]["unit_actions"]
        groups = defaultdict(list)
        for idx, action in enumerate(actions):
            if not is_plant(action) or idx >= len(positions):
                continue
            groups[tuple(positions[idx])].append(idx)

        by_unit = {int(x["unit_index"]): x for x in row["execution_result_t"]}
        for pos, unit_indices in groups.items():
            if len(unit_indices) < 2:
                continue

            requests = [actions[idx] for idx in unit_indices]
            request_counts = Counter(a[1] for a in requests)
            seed_stock = row["state_t"]["seeds"]
            seed_sufficient = all(
                int(seed_stock.get(crop, 0) or 0) >= qty
                for crop, qty in request_counts.items()
            )

            results = [by_unit.get(idx) for idx in unit_indices if idx in by_unit]
            successes = sum(bool(x and x.get("success")) for x in results)
            failures = [x for x in results if x and not x.get("success")]
            failure_reasons = Counter(x.get("noop_reason") for x in failures)
            target_not_empty = int(failure_reasons.get("TARGET_TILE_NOT_EMPTY", 0))

            empties = [tuple(x) for x in row["state_t"]["empty_positions"]]
            target_was_empty = pos in empties
            alternate_empties = [list(x) for x in empties if x != pos]

            prior_acquisition = {}
            for crop in request_counts:
                xs = [
                    e for e in acquisitions
                    if e["row_index"] < row_index and e["crop"] == crop
                ]
                prior_acquisition[crop] = xs[-1] if xs else None
            resource_origin_confirmed = all(
                prior_acquisition.get(crop) is not None for crop in request_counts
            )

            qualifies = (
                target_was_empty
                and seed_sufficient
                and resource_origin_confirmed
                and len(alternate_empties) > 0
                and target_not_empty > 0
            )

            next_state = row.get("state_t1")
            delta_state = None
            if next_state is not None:
                delta_state = {
                    "empty_tiles": int(next_state["empty_tiles"]) - int(row["state_t"]["empty_tiles"]),
                    "plant_total": int(next_state["plant_total"]) - int(row["state_t"]["plant_total"]),
                    "plants_by_crop_before": row["state_t"]["plants_by_crop"],
                    "plants_by_crop_after": next_state["plants_by_crop"],
                }

            events.append(
                {
                    "qualifies": bool(qualifies),
                    "boundary": "movement/allocation -> productive execution",
                    "day": row["day"],
                    "hour": row["hour"],
                    "same_position": list(pos),
                    "unit_indices": unit_indices,
                    "front": {
                        "plant_requests": len(unit_indices),
                        "requests_by_crop": dict(request_counts),
                        "actions": requests,
                    },
                    "back": {
                        "workers": row["state_t"]["workers"],
                        "empty_tiles": row["state_t"]["empty_tiles"],
                        "alternate_empty_tiles": len(alternate_empties),
                        "available_seed": seed_stock,
                        "seed_sufficient_for_requests": bool(seed_sufficient),
                        "prior_current_seed_acquisition": prior_acquisition,
                        "resource_origin_confirmed": bool(resource_origin_confirmed),
                        "target_was_empty": bool(target_was_empty),
                    },
                    "world": {
                        "success": successes,
                        "failed": len(failures),
                        "failure_reasons": dict(failure_reasons),
                        "execution": results,
                    },
                    "previous_turns": previous_turns(rows, row_index, unit_indices, 3),
                    "state_t1": next_state,
                    "delta_state": delta_state,
                    "guard": {
                        "resource_state_present": bool(seed_sufficient),
                        "resource_generated_or_acquired_by_current": bool(resource_origin_confirmed),
                        "current_productive_action_generated": True,
                        "world_failure_observed": target_not_empty > 0,
                        "alternate_empty_capacity_observed": len(alternate_empties) > 0,
                    },
                }
            )
    return events


def main():
    global _current_day, _current_hour, _self_farm_id, _self_farm_obj
    configure()

    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    _self_farm_obj = env.state[0].observation.farms[SEAT]
    _self_farm_id = id(_self_farm_obj)

    def observed(obs):
        global _current_day, _current_hour, _self_farm_id, _self_farm_obj
        _current_day = int(obs.get("day", -1))
        _current_hour = int(obs.get("hour", -1))
        key = (_current_day, _current_hour)

        me = obs["farms"][obs["player"]]
        _self_farm_obj = me
        _self_farm_id = id(me)

        action = current.agent(obs)
        positions = unit_positions(me)
        units = [copy.deepcopy(action.get("farmer", ["PASS"]))]
        units.extend(copy.deepcopy(action.get("hands", []) or []))

        empties = empty_positions(me)
        snapshot = {
            "day": _current_day,
            "hour": _current_hour,
            "money": float(me.get("money", 0) or 0),
            "workers": len(positions),
            "unit_positions": [list(x) for x in positions],
            "empty_positions": [list(x) for x in empties],
            "empty_tiles": len(empties),
            "seeds": plain((obs.get("private", {}) or {}).get("seeds", {}) or {}),
            "plants_by_crop": plant_counts(me),
        }
        snapshot["plant_total"] = sum(snapshot["plants_by_crop"].values())

        _projected[key] = {
            "state_t": snapshot,
            "action": plain(action),
            "unit_actions": plain(units),
        }
        _order.append(key)
        return action

    original_apply = kg._apply_unit_action
    kg._apply_unit_action = wrapped_apply(original_apply)
    try:
        players = [basecfg.OPPONENT, basecfg.OPPONENT]
        players[SEAT] = observed
        env.run(players)
    finally:
        kg._apply_unit_action = original_apply

    rows = []
    for i, key in enumerate(_order):
        p = _projected[key]
        row = {
            "day": key[0],
            "hour": key[1],
            "state_t": p["state_t"],
            "action_t": {
                "full": p["action"],
                "unit_actions": p["unit_actions"],
            },
            "execution_result_t": plain(_execution.get(key, [])),
        }
        if i + 1 < len(_order):
            row["state_t1"] = _projected[_order[i + 1]]["state_t"]
        else:
            row["state_t1"] = None
        rows.append(row)

    scan_events = build_scan_events(rows)
    qualifying = [x for x in scan_events if x["qualifies"]]
    rewards = [float(x.reward) for x in env.state]

    payload = {
        "schema": "kaggriculture.nr01-scan.raw.v0",
        "seed": SEED,
        "seat": SEAT,
        "current_identity": "Baseline + WR-02",
        "scanner_policy_mutated": False,
        "raw_turns": rows,
        "scan_events": scan_events,
        "qualifying_event_count": len(qualifying),
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "close_scope_contract": {
            "rule": "Close target equals the exact transform exercised by an A/B test.",
            "forbidden": [
                "Do not expand a rejected repair to the whole Day4 planting surface.",
                "Do not expand a rejected repair to Available Resource -> Productive State.",
                "Do not infer lack of Current intent from unused resources.",
            ],
        },
        "boundary": [
            "SCAN is observation-only.",
            "Current Action is recorded before World execution and is not mutated by the scanner.",
            "Resource/World state and execution outcome are paired on the same turn.",
            "Candidate status is not adoption.",
        ],
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "NR01_SCAN_RAW "
        + json.dumps(
            {
                "seed": SEED,
                "seat": SEAT,
                "qualifying_event_count": len(qualifying),
                "first_qualifying": qualifying[0] if qualifying else None,
                "terminal": payload["terminal"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
