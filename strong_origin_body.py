"""Thin adapter: frozen G4 Strong Origin + provisional G8 livestock lane.

This module intentionally does not mutate g8_agent.py. It reuses only G8's
bounded livestock overlay while replacing G7 with the frozen Strong Origin.
G15 may vary COW_TARGETS and FEED_CARRY through this adapter.
"""

import os
import sys
from collections import Counter
import g8_agent as livestock
import strong_origin
import origin_role_reader
import origin_context_integrator

COW_TARGETS = livestock.COW_TARGETS
FEED_CARRY = livestock.FEED_CARRY
_LAST_TRACE = {}
_REENTRY_CONTEXT = {}
_ORIGIN_CONTEXT_RECEIVES = 0
_ORIGIN_ROLE_READS = 0
_ORIGIN_FIELD_CONTEXT_RECEIVES = 0
_ORIGIN_INTEGRATION = {}
_ORIGIN_READ_CATEGORIES = Counter()


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


def reset_telemetry():
    global _LAST_TRACE, _REENTRY_CONTEXT, _ORIGIN_CONTEXT_RECEIVES, _ORIGIN_ROLE_READS, _ORIGIN_FIELD_CONTEXT_RECEIVES, _ORIGIN_INTEGRATION, _ORIGIN_READ_CATEGORIES
    _LAST_TRACE = {}
    _REENTRY_CONTEXT = {}
    _ORIGIN_CONTEXT_RECEIVES = 0
    _ORIGIN_ROLE_READS = 0
    _ORIGIN_FIELD_CONTEXT_RECEIVES = 0
    _ORIGIN_INTEGRATION = {}
    _ORIGIN_READ_CATEGORIES.clear()
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
            global _ORIGIN_ROLE_READS, _ORIGIN_INTEGRATION, _ORIGIN_READ_CATEGORIES
            old_trace = sys.gettrace()
            internal = {}
            def tracer(frame, event, arg):
                if event == "return" and frame.f_code.co_name == "agent" and frame.f_globals.get("__name__") == "strong_origin":
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
                    })
                return tracer
            original_origin_targets = strong_origin.origin_targets

            def scaled_origin_targets(name, day, capacity):
                targets = original_origin_targets(name, day, capacity)
                if crop_commitment_scale >= 1.0:
                    return targets
                return _CommitmentScaledTargets(targets, crop_commitment_scale)

            strong_origin.origin_targets = scaled_origin_targets
            sys.settrace(tracer)
            try:
                action = strong_origin.agent(inner_obs)
            finally:
                sys.settrace(old_trace)
                strong_origin.origin_targets = original_origin_targets
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
