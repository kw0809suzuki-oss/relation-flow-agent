"""Commitment Intensity Cap v0.

Battle candidate built on Investment Completion Coordinate v0.

Hypothesis (experimental, not established):
Among post-D14 SEED orders that are already full-cycle completable, a single
commitment that consumes too much of current liquid cash may be harmful.

Intervention:
- First apply Investment Completion Coordinate v0 unchanged.
- Then suppress only a remaining BUY_SEED order when:
      seed_cost / current_pre_action_cash > 0.025
- No other action is changed.

The 2.5% cap is an experimental boundary derived from the prior 10-case
observation. It is not treated as a rule or adopted policy.
"""

import copy
import investment_completion_coordinate_v0 as completion
from strong_origin import SEED_COST

CAP=0.025
_state={}

def reset_experiment():
    global _state
    _state={
        "turn":0,
        "seed_orders_after_completion":0,
        "seed_orders_allowed_intensity":0,
        "seed_orders_removed_intensity":0,
        "events":[],
    }
    completion.reset_experiment()

def set_probe_enabled(enabled):
    completion.set_probe_enabled(enabled)

def set_attribution_enabled(enabled):
    completion.set_attribution_enabled(enabled)

def _is_seed(a):
    return isinstance(a,(list,tuple)) and len(a)>=3 and a[0]=="BUY_SEED"

def _seed_cost(a):
    if not _is_seed(a):
        return None
    crop=a[1]
    qty=float(a[2] or 0)
    unit=SEED_COST.get(crop)
    if unit is None:
        return None
    return float(unit)*qty

def agent(obs):
    if not _state:
        reset_experiment()

    turn=_state["turn"]
    _state["turn"]+=1

    actions=completion.agent(obs)
    if not isinstance(actions,dict):
        return actions

    day=int(obs.get("day",0) or 0)
    if day < completion.D14:
        return actions

    me=obs["farms"][obs["player"]]
    cash=float(me.get("money",0) or 0)
    market=list(actions.get("market",[]) or [])
    revised=[]
    changed=False

    for a in market:
        if not _is_seed(a):
            revised.append(a)
            continue

        _state["seed_orders_after_completion"]+=1
        cost=_seed_cost(a)
        intensity=None if cost is None or cash<=0 else cost/cash
        remove=(intensity is not None and intensity>CAP)

        event={
            "day":day,
            "turn":turn,
            "action":copy.deepcopy(a),
            "pre_action_cash":cash,
            "seed_cost":cost,
            "commitment_intensity":intensity,
            "cap":CAP,
        }

        if remove:
            _state["seed_orders_removed_intensity"]+=1
            event["kind"]="remove"
            event["reason"]="commitment_intensity_above_cap"
            changed=True
        else:
            _state["seed_orders_allowed_intensity"]+=1
            event["kind"]="allow"
            event["reason"]="commitment_intensity_within_cap_or_unmeasured"
            revised.append(a)

        _state["events"].append(event)

    if not changed:
        return actions

    out=copy.deepcopy(actions)
    out["market"]=revised
    return out

def get_experiment_telemetry():
    return {
        **copy.deepcopy(_state),
        "completion":completion.get_experiment_telemetry(),
    }

def get_trace():
    return completion.get_trace()
