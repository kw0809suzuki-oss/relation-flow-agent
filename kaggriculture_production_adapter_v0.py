from __future__ import annotations

import copy
from dataclasses import asdict
from typing import Any, Dict

from semantic_kernel_v2 import ActionIntent, Rule, StateSnapshot, evaluate, plan, resolve


WHEAT3_COST = 30
LAND_PRICES = {1: 1000, 2: 2000, 3: 4000}


def observation_to_snapshot(obs: Dict[str, Any]) -> StateSnapshot:
    player = int(obs["player"])
    farm = obs["farms"][player]
    private = obs.get("private", {}) or {}
    seeds = private.get("seeds", {}) or {}
    quadrants = len(farm.get("unlocked_quadrants", []))
    land_cost = LAND_PRICES.get(quadrants, 0)
    return StateSnapshot({
        "day": int(obs.get("day", 0)),
        "cash": int(farm.get("money", 0)),
        "land_count": quadrants,
        "land_cost": int(land_cost),
        "wheat_seeds": int(seeds.get("WHEAT", 0)),
    })


def build_shadow_rules(snapshot: StateSnapshot):
    land_cost = snapshot.get("land_cost")
    wheat = Rule(
        id="A_WHEAT3",
        version="production-shadow-v0",
        trigger=lambda s: s.get("cash") < 1000,
        action=ActionIntent(
            id="act-buy-seed-wheat-3",
            kind="BUY_SEED_WHEAT_3",
            claims={"cash": WHEAT3_COST},
            requires=lambda s: s.get("cash") >= WHEAT3_COST,
        ),
    )
    land = Rule(
        id="B_LAND",
        version="production-shadow-v0",
        trigger=lambda s: s.get("cash") >= 970 and s.get("land_cost") > 0,
        action=ActionIntent(
            id="act-buy-land",
            kind="BUY_LAND",
            claims={"cash": land_cost} if land_cost else {},
            requires=lambda s: s.get("land_cost") > 0 and s.get("cash") >= s.get("land_cost"),
        ),
    )
    return (wheat, land)


def observe_semantics(obs: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = observation_to_snapshot(obs)
    eligible, trace = evaluate(snapshot, build_shadow_rules(snapshot))
    selected, trace = resolve(snapshot, eligible, trace)
    bundle, trace = plan(snapshot, selected, trace)
    return {
        "snapshot": dict(snapshot.values),
        "eligible_rule_ids": list(trace.eligible_rule_ids),
        "selected_rule_ids": list(trace.selected_rule_ids),
        "rejection_reasons": [list(item) for item in trace.rejection_reasons],
        "plan_status": trace.plan_status,
        "plan_reason": trace.plan_reason,
        "planned_action_ids": list(trace.planned_action_ids),
        "shadow_only": True,
        "would_emit_action_intents": [] if bundle is None else [action.kind for action in bundle],
    }


def attach_emitted_action(record: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(record)
    out["emitted_action"] = copy.deepcopy(action)
    return out
