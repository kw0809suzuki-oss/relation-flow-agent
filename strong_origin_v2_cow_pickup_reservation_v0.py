"""Strong Origin v2 COW Pickup Reservation Probe v0.

Single arbitration change:
within one decision pass, do not emit more shed COW PICKUP requests than the
COW quantity currently present in the shed.

Everything else remains Body-only v0.
"""
import strong_origin_body as body
import strong_origin_v2_body_only_v0 as body_only
import g8_cow_pickup_reservation_v0 as pickup_reserved


def _call(fn,*args,**kwargs):
    old=body.livestock
    body.livestock=pickup_reserved
    try:
        return fn(*args,**kwargs)
    finally:
        body.livestock=old


def agent(obs):
    return _call(body_only.agent,obs)


def reset_telemetry():
    return _call(body_only.reset_telemetry)


def get_telemetry():
    out=dict(body_only.get_telemetry())
    out["cow_pickup_reservation_probe_v0"]=True
    return out
