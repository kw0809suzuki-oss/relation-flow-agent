"""WHEAT Market Netting v0.

Minimal intervention:
Only on day 10-20, when the final action contains both SELL WHEAT and
BUY_PRODUCT WHEAT on the same turn, replace the opposite gross orders with
one net WHEAT market order (or none if perfectly balanced).

Everything else is passed through unchanged.
"""

import copy
import g17_agent as base

_TRACE = {"modified_turns":0,"overlap_units_removed":0.0}

def reset_telemetry():
    global _TRACE
    _TRACE={"modified_turns":0,"overlap_units_removed":0.0}
    if hasattr(base,"reset_telemetry"):
        base.reset_telemetry()

def get_telemetry():
    return dict(_TRACE)

def set_probe_enabled(v):
    if hasattr(base,"set_probe_enabled"): base.set_probe_enabled(v)

def set_attribution_enabled(v):
    if hasattr(base,"set_attribution_enabled"): base.set_attribution_enabled(v)

def agent(obs):
    action=base.agent(obs)
    day=int(obs.get("day",0) or 0)
    if not (10 <= day <= 20):
        return action

    market=list(action.get("market",[]) or [])
    sell=sum(float(o[2]) for o in market
             if isinstance(o,(list,tuple)) and len(o)>=3 and o[0]=="SELL" and o[1]=="WHEAT" and isinstance(o[2],(int,float)))
    buy=sum(float(o[2]) for o in market
            if isinstance(o,(list,tuple)) and len(o)>=3 and o[0]=="BUY_PRODUCT" and o[1]=="WHEAT" and isinstance(o[2],(int,float)))
    if sell <= 0 or buy <= 0:
        return action

    overlap=min(sell,buy)
    first_idx=min(i for i,o in enumerate(market)
                  if isinstance(o,(list,tuple)) and len(o)>=3 and o[1]=="WHEAT" and o[0] in ("SELL","BUY_PRODUCT"))

    kept=[]
    for o in market:
        if isinstance(o,(list,tuple)) and len(o)>=3 and o[1]=="WHEAT" and o[0] in ("SELL","BUY_PRODUCT"):
            continue
        kept.append(o)

    net=sell-buy
    replacement=None
    if net > 0:
        replacement=["SELL","WHEAT",int(net) if float(net).is_integer() else net]
    elif net < 0:
        q=-net
        replacement=["BUY_PRODUCT","WHEAT",int(q) if float(q).is_integer() else q]

    # Insert at the earliest removed WHEAT order position, clipped to the shorter list.
    if replacement is not None:
        kept.insert(min(first_idx,len(kept)),replacement)

    out=copy.deepcopy(action)
    out["market"]=kept
    _TRACE["modified_turns"] += 1
    _TRACE["overlap_units_removed"] += overlap
    return out
