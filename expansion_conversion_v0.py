"""Expansion Conversion Model v0 wrapper.

Swaps only the Strong Origin crop-work allocator while the candidate executes.
The rest of the G17 / Whole Flow stack remains unchanged.
"""
import whole_flow_control_agent as baseline
import strong_origin_body
import strong_origin_expansion_conversion_v0 as candidate_origin


def _call(fn,*args,**kwargs):
    old=strong_origin_body.strong_origin
    strong_origin_body.strong_origin=candidate_origin
    try:
        return fn(*args,**kwargs)
    finally:
        strong_origin_body.strong_origin=old


def agent(obs):
    return _call(baseline.agent,obs)


def reset_telemetry():
    return _call(baseline.reset_telemetry)


def set_control_enabled(enabled):
    return baseline.set_control_enabled(enabled)


def set_probe_enabled(enabled):
    return baseline.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    return baseline.set_attribution_enabled(enabled)


def get_telemetry():
    return baseline.get_telemetry()


def get_trace():
    return baseline.get_trace()
