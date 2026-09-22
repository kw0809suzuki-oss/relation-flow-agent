"""Thin adapter: frozen G4 Strong Origin + provisional G8 livestock lane.

This module intentionally does not mutate g8_agent.py. It reuses only G8's
bounded livestock overlay while replacing G7 with the frozen Strong Origin.
G15 may vary COW_TARGETS and FEED_CARRY through this adapter.
"""

import os
import sys
import copy
from collections import Counter
import g8_agent as livestock
import strong_origin_direction_v0 as strong_origin
import origin_role_reader
import origin_context_integrator
import model_selection_action_adapter_v0

COW_TARGETS = livestock.COW_TARGETS
FEED_CARRY = livestock.FEED_CARRY
_LAST_TRACE = {}
_REENTRY_CONTEXT = {}
_ORIGIN_CONTEXT_RECEIVES = 0
_ORIGIN_ROLE_READS = 0
_ORIGIN_FIELD_CONTEXT_RECEIVES = 0
_ORIGIN_INTEGRATION = {}
_ORIGIN_READ_CATEGORIES = Counter()
_DIRECTION_CONTROL_USED = False


class _CommitmentScaledTargets(dict):
    def __init__(self, values, scale):
        super().__init__(values)
        self._origin_scale = max(0.0, min(1.0, float(scale)))
        self._origin_armed = True

    def __setitem__(self, key, value):
        if not getattr(self, "_origin_armed", False) or key not in self:
            return super().__setitem__(key, value)
        current = super().get(key)
        if not isinstance(current, (int, float)) or not isinstance(value, (int, float)):
            return super().__setitem__(key, value)
        delta = value - current
        scaled = int(abs(delta) * self._origin_scale)
        adjusted = current + (scaled if delta > 0 else -scaled)
        return super().__setitem__(key, adjusted)


def _crop_commitment_scale(integration):
    if os.getenv("ORIGIN_CROP_COMMITMENT", "0") != "1":
        return 1.0
    context = dict(integration or {})
    if not context.get("field_context_present", False):
        return 1.0
    if float(context.get("field_evidence", 0.0) or 0.0) <= 0.0 and not context.get("outer_meaning_present", False):
        return 1.0
    native_strength = float(context.get("native_strength", 0.0) or 0.0)
    commitment = float(context.get("commitment", 0.0) or 0.0)
    if native_strength <= 0.0:
        return 1.0
    return max(0.0, min(1.0, commitment / native_strength))



def _apply_candidate_selection_priority(action, integration):
    """Prioritize a selected BUY_SEED order without deleting or resizing orders."""
    context = dict(integration or {})
    selection = dict(context.get("candidate_selection", {}) or {})
    chosen = selection.get("selected_candidate")
    if not isinstance(action, dict) or not isinstance(chosen, (list, tuple)):
        return action, False

    market = list(action.get("market", []) or [])
    seed_indices = [
        i for i, order in enumerate(market)
        if isinstance(order, (list, tuple)) and order and order[0] == "BUY_SEED"
    ]
    if not seed_indices:
        return action, False

    selected_index = None
    for i in seed_indices:
        if list(market[i]) == list(chosen):
            selected_index = i
            break
    if selected_index is None:
        return action, False

    first_seed = seed_indices[0]
    if selected_index == first_seed:
        return action, False

    revised = copy.deepcopy(action)
    revised_market = list(revised.get("market", []) or [])
    selected_order = revised_market.pop(selected_index)
    revised_market.insert(first_seed, selected_order)
    revised["market"] = revised_market
    return revised, True

def reset_telemetry():
    global _LAST_TRACE, _REENTRY_CONTEXT, _ORIGIN_CONTEXT_RECEIVES, _ORIGIN_ROLE_READS, _ORIGIN_FIELD_CONTEXT_RECEIVES, _ORIGIN_INTEGRATION, _ORIGIN_READ_CATEGORIES, _DIRECTION_CONTROL_USED
    _LAST_TRACE = {}
    _REENTRY_CONTEXT = {}
    _ORIGIN_CONTEXT_RECEIVES = 0
    _ORIGIN_ROLE_READS = 0
    _ORIGIN_FIELD_CONTEXT_RECEIVES = 0
    _ORIGIN_INTEGRATION = {}
    _ORIGIN_READ_CATEGORIES.clear()
    _DIRECTION_CONTROL_USED = False
    return strong_origin.reset_telemetry()


def set_reentry_context(context):
    global _REENTRY_CONTEXT
    _REENTRY_CONTEXT = dict(context or {})


def get_reentry_context():
    return dict(_REENTRY_CONTEXT)


def get_origin_integration():
    return dict(_ORIGIN_INTEGRATION)


def get_telemetry():
    base = dict(strong_origin.get_telemetry())
    base["origin_role_context_receives"] = _ORIGIN_CONTEXT_RECEIVES
    base["origin_role_reads"] = _ORIGIN_ROLE_READS
    base["origin_field_context_receives"] = _ORIGIN_FIELD_CONTEXT_RECEIVES
    base["origin_role_read_categories"] = dict(_ORIGIN_READ_CATEGORIES)
    return base


def get_last_trace():
    return dict(_LAST_TRACE)


def agent(obs):
    global _LAST_TRACE, _ORIGIN_CONTEXT_RECEIVES, _ORIGIN_ROLE_READS, _ORIGIN_FIELD_CONTEXT_RECEIVES, _ORIGIN_INTEGRATION, _ORIGIN_READ_CATEGORIES
    current_context = dict(_REENTRY_CONTEXT)
    applied_integration = dict(_ORIGIN_INTEGRATION)
    crop_commitment_scale = _crop_commitment_scale(applied_integration)
    if current_context.get("matched_count", 0) > 0:
        _ORIGIN_CONTEXT_RECEIVES += 1
    if current_context.get("field_description_connected") and current_context.get("field_description"):
        _ORIGIN_FIELD_CONTEXT_RECEIVES += 1
    livestock.COW_TARGETS = COW_TARGETS
    livestock.FEED_CARRY = FEED_CARRY

    previous_base = livestock.g7
    captured = {}

    class _ObservedBase:
        @staticmethod
        def agent(inner_obs):
            global _ORIGIN_ROLE_READS, _ORIGIN_INTEGRATION, _ORIGIN_READ_CATEGORIES, _DIRECTION_CONTROL_USED
            old_trace = sys.gettrace()
            internal = {}
            def tracer(frame, event, arg):
                if event == "return" and frame.f_code.co_name == "agent" and frame.f_globals.get("__name__") == strong_origin.__name__:
                    loc = frame.f_locals
                    internal.update({
                        "strategy_name": loc.get("strategy_name"),
                        "targets": dict(loc.get("targets", {})),
                        "best_crop": loc.get("best_crop"),
                        "scores": dict(loc.get("scores", {})),
                        "market": list(loc.get("market", [])),
                        "farmer_action": loc.get("farmer_action"),
                        "hand_actions": list(loc.get("hand_actions", [])),
                        "distortion": getattr(loc.get("xdecision"), "distortion", 0.0),
                        "counter_opportunity": loc.get("opportunity", 0.0),
                        "counter_weight": loc.get("cweight", 0.0),
                        "money": (loc.get("me") or {}).get("money") if isinstance(loc.get("me"), dict) else None,
                        "reserve": loc.get("reserve"),
                        "remaining_days": loc.get("remaining_days"),
                        "empty_tile_count": len(loc.get("empty_tiles", []) or []),
                        "seed_stock": dict((loc.get("private") or {}).get("seeds", {}) or {}) if isinstance(loc.get("private"), dict) else {},
                        "live_plants": {k: len(v) for k, v in dict(loc.get("my_plants", {}) or {}).items()},
                        "native_targets_before_direction": dict(loc.get("native_targets", {}) or {}),
                        "direction_targets_after": dict(loc.get("targets", {}) or {}),
                        "direction_applied": bool(loc.get("direction_applied", False)),
                        "direction_crop": loc.get("direction_crop"),
                    })
                return tracer
            original_origin_targets = strong_origin.origin_targets

            def scaled_origin_targets(name, day, capacity):
                targets = original_origin_targets(name, day, capacity)
                if crop_commitment_scale >= 1.0:
                    return targets
                return _CommitmentScaledTargets(targets, crop_commitment_scale)

            strong_origin.origin_targets = scaled_origin_targets
            guided_generation = os.getenv("ORIGIN_MODEL_SELECTION_GUIDED_GENERATION", "0") == "1"
            directional_state_read = os.getenv("ORIGIN_MODEL_DIRECTIONAL_STATE_READ", "0") == "1"
            control_mode = os.getenv("ORIGIN_DIRECTION_CONTROL_MODE", "").strip().lower()
            selected_direction = dict(applied_integration.get("candidate_direction", {}) or {})
            alternative_direction = dict(applied_integration.get("candidate_alternative_direction", {}) or {})
            comparable_entry = bool(selected_direction and alternative_direction)

            direction_to_apply = None
            if directional_state_read:
                direction_to_apply = selected_direction
            elif not _DIRECTION_CONTROL_USED and comparable_entry:
                if control_mode == "selected":
                    direction_to_apply = selected_direction
                elif control_mode == "alternative":
                    direction_to_apply = alternative_direction

            strong_origin.set_model_selection(
                applied_integration.get("candidate_selection") if guided_generation else None
            )
            strong_origin.set_model_direction(direction_to_apply)
            captured["selection_guided_generation_enabled"] = bool(guided_generation)
            captured["selection_guided_crop"] = strong_origin.get_model_selected_crop()
            captured["directional_state_read_enabled"] = bool(directional_state_read or direction_to_apply)
            captured["direction_control_mode"] = control_mode or "none"
            captured["direction_control_comparable_entry"] = comparable_entry
            captured["applied_candidate_direction"] = dict(direction_to_apply or {})
            captured["selected_candidate_direction"] = selected_direction
            captured["alternative_candidate_direction"] = alternative_direction
            sys.settrace(tracer)
            try:
                action = strong_origin.agent(inner_obs)
            finally:
                sys.settrace(old_trace)
                strong_origin.origin_targets = original_origin_targets
                strong_origin.set_model_selection(None)
                strong_origin.set_model_direction(None)
            if captured.get("internal", {}).get("direction_applied"):
                _DIRECTION_CONTROL_USED = True
            captured["direction_control_used"] = bool(_DIRECTION_CONTROL_USED)
            captured["native_base_action"] = copy.deepcopy(action)
            action_use = {
                "selection_available": False,
                "market_priority_changed": False,
                "plant_priority_changed": False,
            }
            if os.getenv("ORIGIN_MODEL_SELECTION_TO_ACTION", "0") == "1":
                action, action_use = model_selection_action_adapter_v0.apply(
                    inner_obs, action, applied_integration
                )
            captured["selection_priority_applied"] = bool(
                action_use.get("market_priority_changed") or action_use.get("plant_priority_changed")
            )
            captured["selection_action_use"] = dict(action_use)
            captured["applied_candidate_selection"] = dict(applied_integration.get("candidate_selection", {}) or {})
            captured["base_action"] = action
            captured["internal"] = internal
            captured["origin_reading"] = origin_role_reader.read(current_context, internal)
            if captured["origin_reading"].get("role_present"):
                _ORIGIN_ROLE_READS += 1
                category = captured["origin_reading"].get("origin_strategy_observed") or "UNKNOWN"
                _ORIGIN_READ_CATEGORIES[category] += 1
            captured["origin_integration"] = origin_context_integrator.integrate(internal, captured["origin_reading"])
            _ORIGIN_INTEGRATION = dict(captured["origin_integration"])
            return action

        @staticmethod
        def reset_telemetry():
            return strong_origin.reset_telemetry()

        @staticmethod
        def get_telemetry():
            return strong_origin.get_telemetry()

    livestock.g7 = _ObservedBase
    try:
        final_action = livestock.agent(obs)
        base_action = captured.get("base_action", {})
        _LAST_TRACE = {
            "reentry_context": current_context,
            "base_action": base_action,
            "native_base_action": captured.get("native_base_action", {}),
            "selection_priority_applied": bool(captured.get("selection_priority_applied", False)),
            "selection_guided_generation_enabled": bool(captured.get("selection_guided_generation_enabled", False)),
            "selection_guided_crop": captured.get("selection_guided_crop"),
            "directional_state_read_enabled": bool(captured.get("directional_state_read_enabled", False)),
            "applied_candidate_direction": dict(captured.get("applied_candidate_direction", {})),
            "selected_candidate_direction": dict(captured.get("selected_candidate_direction", {})),
            "alternative_candidate_direction": dict(captured.get("alternative_candidate_direction", {})),
            "direction_control_mode": captured.get("direction_control_mode"),
            "direction_control_comparable_entry": bool(captured.get("direction_control_comparable_entry", False)),
            "direction_control_used": bool(captured.get("direction_control_used", False)),
            "selection_action_use": dict(captured.get("selection_action_use", {})),
            "applied_candidate_selection": dict(captured.get("applied_candidate_selection", {})),
            "final_action": final_action,
            "overlay_changed_farmer": base_action.get("farmer") != final_action.get("farmer"),
            "overlay_changed_hands": base_action.get("hands") != final_action.get("hands"),
            "overlay_changed_market": base_action.get("market") != final_action.get("market"),
            "internal": dict(captured.get("internal", {})),
            "origin_reading": dict(captured.get("origin_reading", {})),
            "origin_integration": dict(captured.get("origin_integration", {})),
            "applied_origin_integration": applied_integration,
            "crop_commitment_enabled": os.getenv("ORIGIN_CROP_COMMITMENT", "0") == "1",
            "crop_commitment_scale": round(crop_commitment_scale, 6),
        }
        return final_action
    finally:
        livestock.g7 = previous_base
