"""Minimal Turn108 WHEAT-seed suppression experiment.

Intervention target:
- exact turn 108 only
- remove only BUY_SEED WHEAT 3 from market actions
- leave all other actions untouched

Reachability evidence is recorded per match.
"""
import whole_flow_control_agent as v6

TARGET_TURN=108
_turn=-1
_activations=[]

def reset_experiment():
    global _turn,_activations
    _turn=-1
    _activations=[]

def get_activations():
    return list(_activations)

def _is_target(a):
    return isinstance(a,(list,tuple)) and len(a)>=3 and a[0]=="BUY_SEED" and a[1]=="WHEAT" and int(a[2])==3

def agent(obs):
    global _turn
    _turn += 1
    actions=v6.agent(obs)
    if _turn != TARGET_TURN or not isinstance(actions,dict):
        return actions
    market=list(actions.get("market",[]) or [])
    if not any(_is_target(a) for a in market):
        return actions
    revised=dict(actions)
    revised["market"]=[a for a in market if not _is_target(a)]
    _activations.append({
        "turn":_turn,
        "before_market":market,
        "after_market":revised["market"],
        "target_removed":True,
    })
    return revised
