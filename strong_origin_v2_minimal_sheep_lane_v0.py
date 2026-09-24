"""Strong Origin v2 Minimal SHEEP Lane Probe v0.

Baseline Body-only is unchanged. During candidate.agent only, Strong Origin
Body's livestock overlay is swapped from frozen G8 to the minimal SHEEP probe.

Direct intended difference:
- preserve native COW target;
- once the two-COW entrance is reachable, buy at most one SHEEP through Day4;
- reuse generic pasture/feed/care/harvest/fertilizer/drop mechanics.

No crop, LAND, HIRE, D14 closure, or post-Day4 strategy rule is added here.
"""
import strong_origin_body as body
import strong_origin_v2_body_only_v0 as body_only
import g8_minimal_sheep_lane_v0 as sheep_livestock


def _call(fn,*args,**kwargs):
    old=body.livestock
    body.livestock=sheep_livestock
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
    out["minimal_sheep_lane_probe_v0"]=True
    return out
