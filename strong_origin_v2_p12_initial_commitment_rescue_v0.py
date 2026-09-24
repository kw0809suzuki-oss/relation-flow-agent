"""P12 Initial Commitment Rescue v0.

Body-only v0 is preserved. Only while candidate.agent executes, the Strong
Origin module inside strong_origin_body is swapped to the already-frozen
Day0 target-reservation variant. That variant differs only on Day0 work-target
reservation and behaves as frozen Strong Origin afterward.
"""
import strong_origin_body
import strong_origin_v2_body_only_v0 as body_only
import strong_origin_day0_target_reservation_v0 as reserved_origin

def _call(fn,*args,**kwargs):
    old=strong_origin_body.strong_origin
    strong_origin_body.strong_origin=reserved_origin
    try:
        return fn(*args,**kwargs)
    finally:
        strong_origin_body.strong_origin=old

def agent(obs):
    return _call(body_only.agent,obs)

def reset_telemetry():
    return _call(body_only.reset_telemetry)

def get_telemetry():
    return body_only.get_telemetry()
