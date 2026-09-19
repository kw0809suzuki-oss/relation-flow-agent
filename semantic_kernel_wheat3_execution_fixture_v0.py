from __future__ import annotations

import copy

import whole_flow_control_agent as native
from kaggriculture_production_adapter_v0 import observation_to_snapshot
from semantic_kernel_v2 import ActionIntent, Rule, StateSnapshot, evaluate, plan, resolve


TARGET_TURN = 108
_state = {"turn": 0, "trace": []}


def set_control_enabled(enabled):
    native.set_control_enabled(enabled)


def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)


def reset_telemetry():
    global _state
    native.reset_telemetry()
    _state = {"turn": 0, "trace": []}


def _target_market_action(action):
    return (
        isinstance(action, (list, tuple))
        and len(action) >= 3
        and action[0] == "BUY_SEED"
        and action[1] == "WHEAT"
        and int(action[2]) == 3
    )


def _snapshot_with_turn(obs):
    base = observation_to_snapshot(obs)
    values = dict(base.values)
    values["turn"] = _state["turn"]
    return StateSnapshot(values)


def _rules():
    return (
        Rule(
            id="SUPPRESS_WHEAT3_T108",
            version="execution-fixture-v0",
            trigger=lambda s: s.get("turn") == TARGET_TURN,
            action=ActionIntent(
                id="intent-suppress-wheat3-t108",
                kind="SUPPRESS_BUY_SEED_WHEAT_3",
            ),
        ),
    )


def _execute_intent(native_action, bundle):
    revised = copy.deepcopy(native_action)
    execution = []

    for intent in bundle or ():
        if intent.kind != "SUPPRESS_BUY_SEED_WHEAT_3":
            execution.append({
                "intent_id": intent.id,
                "status": "unsupported",
            })
            continue

        if not isinstance(revised, dict):
            execution.append({
                "intent_id": intent.id,
                "status": "noop_action_not_dict",
            })
            continue

        market = list(revised.get("market", []) or [])
        matches = [a for a in market if _target_market_action(a)]
        if not matches:
            execution.append({
                "intent_id": intent.id,
                "status": "noop_target_absent",
                "before_market": copy.deepcopy(market),
                "after_market": copy.deepcopy(market),
            })
            continue

        after = [a for a in market if not _target_market_action(a)]
        revised["market"] = after
        execution.append({
            "intent_id": intent.id,
            "status": "applied",
            "target_removed": True,
            "before_market": copy.deepcopy(market),
            "after_market": copy.deepcopy(after),
        })

    return revised, execution


def agent(obs):
    snapshot = _snapshot_with_turn(obs)
    eligible, trace = evaluate(snapshot, _rules())
    selected, trace = resolve(snapshot, eligible, trace)
    bundle, trace = plan(snapshot, selected, trace)

    native_action = native.agent(obs)
    final_action, execution = _execute_intent(native_action, bundle)

    _state["trace"].append({
        "turn": _state["turn"],
        "day": obs.get("day"),
        "snapshot": dict(snapshot.values),
        "eligible_rule_ids": list(trace.eligible_rule_ids),
        "selected_rule_ids": list(trace.selected_rule_ids),
        "plan_status": trace.plan_status,
        "plan_reason": trace.plan_reason,
        "planned_action_ids": list(trace.planned_action_ids),
        "native_action": copy.deepcopy(native_action),
        "final_action": copy.deepcopy(final_action),
        "execution": execution,
    })
    _state["turn"] += 1
    return final_action


def get_trace():
    return {
        "semantic_execution": copy.deepcopy(_state.get("trace", [])),
        "native": native.get_trace(),
    }


def get_telemetry():
    result = dict(native.get_telemetry())
    rows = _state.get("trace", [])
    result.update({
        "semantic_execution_turns": len(rows),
        "semantic_execution_planned": sum(bool(row.get("planned_action_ids")) for row in rows),
        "semantic_execution_applied": sum(
            any(item.get("status") == "applied" for item in row.get("execution", []))
            for row in rows
        ),
    })
    return result
