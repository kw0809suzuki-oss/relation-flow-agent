"""Strong Origin v2 Non-preemptive Livestock Probe v0.

Body-only is unchanged. Candidate swaps only the G8 livestock arbitration:
new livestock jobs cannot replace an active Strong Origin base action.
Already-engaged livestock work may continue.

No crop action is forced and no crop target, COW target, market rule, LAND,
HIRE, or D14 rule is added.
"""
import strong_origin_body as body
import strong_origin_v2_body_only_v0 as body_only
import g8_nonpreemptive_livestock_v0 as nonpreemptive


def _call(fn,*args,**kwargs):
    old=body.livestock
    body.livestock=nonpreemptive
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
    out["nonpreemptive_livestock_probe_v0"]=True
    return out
