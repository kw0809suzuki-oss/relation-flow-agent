"""Crop Maintenance Protection v0.

Minimal intervention:
During day 5-12 only, if the Strong Origin base action requests WATER / PLANT /
HARVEST for a unit slot and the livestock overlay changed that slot, restore the
exact base action for that slot. Market actions and all other unit actions remain
unchanged.
"""

import copy
import g17_agent as current

CROP_ACTIONS={"WATER","PLANT","HARVEST"}
_stats={}

def reset_telemetry():
    global _stats
    current.reset_telemetry()
    _stats={
      "turns":0,"eligible_slots":0,"protected_slots":0,
      "protected_water":0,"protected_plant":0,"protected_harvest":0,
      "days":{}
    }

def set_probe_enabled(enabled):
    current.set_probe_enabled(enabled)

def set_attribution_enabled(enabled):
    current.set_attribution_enabled(enabled)

def _latest_snapshot():
    trace=current.get_trace() or {}
    snaps=((((trace.get("observe") or {}).get("body") or {}).get("snapshots")) or [])
    return snaps[-1] if snaps else {}

def _verb(action):
    return str(action[0]) if isinstance(action,(list,tuple)) and action else None

def _restore_slot(final_action, base_action, slot):
    if slot=="farmer":
        final_action["farmer"]=copy.deepcopy(base_action.get("farmer"))
        return
    if not slot.startswith("hand"):
        return
    idx=int(slot[4:])
    hands=list(final_action.get("hands",[]) or [])
    base_hands=list(base_action.get("hands",[]) or [])
    while len(hands) < len(base_hands):
        hands.append(["PASS"])
    if idx < len(base_hands):
        hands[idx]=copy.deepcopy(base_hands[idx])
        final_action["hands"]=hands

def agent(obs):
    global _stats
    if not _stats: reset_telemetry()
    action=current.agent(obs)
    _stats["turns"]+=1
    day=int(obs.get("day",0) or 0)
    if not (5 <= day <= 12):
        return action

    snap=_latest_snapshot()
    base_action=dict(snap.get("base_action",{}) or {})
    final=copy.deepcopy(action)

    pairs=[("farmer",base_action.get("farmer"),final.get("farmer"))]
    base_hands=list(base_action.get("hands",[]) or [])
    final_hands=list(final.get("hands",[]) or [])
    n=max(len(base_hands),len(final_hands))
    for i in range(n):
        b=base_hands[i] if i < len(base_hands) else None
        a=final_hands[i] if i < len(final_hands) else None
        pairs.append((f"hand{i}",b,a))

    changed=False
    dayrec=_stats["days"].setdefault(str(day),{"eligible":0,"protected":0})
    for slot,b,a in pairs:
        vb=_verb(b)
        if vb not in CROP_ACTIONS:
            continue
        _stats["eligible_slots"]+=1; dayrec["eligible"]+=1
        if b==a:
            continue
        _restore_slot(final,base_action,slot)
        _stats["protected_slots"]+=1; dayrec["protected"]+=1
        _stats[f"protected_{vb.lower()}"]+=1
        changed=True

    return final

def get_telemetry():
    base=dict(current.get_telemetry())
    base["crop_protection"]=copy.deepcopy(_stats)
    return base
