#!/usr/bin/env python3
"""Battle Asset Position Map v0.

Join one fixed Battle trace to Asset State Schedule v0.
World schedule stays fixed; Battle only supplies asset instances.

Observation only:
- asset type
- origin day
- held output units
- harvest eligibility now
- next public production/output boundary
- remaining turns to that boundary
No value score, market price, cause, or policy interpretation.
"""
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ.get("BATTLE_SEED","7351"))
SEAT=int(os.environ.get("BATTLE_SEAT","0"))
SCHEDULE=Path("asset_state_schedule_v0.json")
OUT=Path(f"battle_asset_position_map_v0_{SEED}_seat{SEAT}.json")
TARGET_DAYS=set(range(12,19))

def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    return str(v)

def getv(x,key,default=None):
    if isinstance(x,dict): return x.get(key,default)
    try:return getattr(x,key)
    except Exception:return default

def next_day_boundary(origin_day, offsets, day, hour, tpd):
    now=day*tpd+hour
    targets=[(origin_day+int(off))*tpd for off in offsets]
    future=[t for t in targets if t>=now]
    if not future:return None,None
    t=min(future)
    return t//tpd,t-now

def instance_from_tile(tile,x,y,day,hour,tpd,schedule):
    if not isinstance(tile,dict):return None
    if tile.get("kind")=="PLANT" and tile.get("crop") in schedule["assets"]:
        typ=str(tile["crop"]); spec=schedule["assets"][typ]
        origin=int(tile.get("planted_day",day))
        age=day-origin
        held=int(tile.get("yield_units",0) or 0)
        p=spec["production"]
        if p["mode"]=="ongoing_automatic_day_boundary":
            offsets=list(p["base_output_event_day_offsets"])
            nxt_day,remaining=next_day_boundary(origin,offsets,day,hour,tpd)
            harvest_eligible=age>=int(p["harvest_eligible_from_day_offset"]) and held>0
            phase=("HELD_OUTPUT" if held>0 else ("WAITING_SCHEDULED_OUTPUT" if remaining is not None else "SCHEDULE_COMPLETE"))
            next_boundary_kind="scheduled_output"
        else:
            window=list(p["water_yield_window_day_offsets"])
            now_age=age
            if now_age<min(window):
                next_off=min(window)
                nxt_day=origin+next_off
                remaining=nxt_day*tpd-(day*tpd+hour)
                phase="PRE_OUTPUT_FORMATION_WINDOW"
            elif now_age<=max(window):
                nxt_day=day
                remaining=0
                phase="OUTPUT_FORMATION_WINDOW_OPEN"
            else:
                nxt_day=None;remaining=None;phase="OUTPUT_FORMATION_WINDOW_CLOSED"
            harvest_eligible=age>=int(p["first_harvest_eligible_day_offset"]) and held>0
            next_boundary_kind="eligible_water_output_window"
        return {
          "asset_type":typ,"asset_class":"crop","x":x,"y":y,
          "origin_day":origin,"age_days":age,"held_output_units":held,
          "harvest_eligible_now":bool(harvest_eligible),
          "phase":phase,
          "next_boundary_kind":next_boundary_kind,
          "next_boundary_day":nxt_day,
          "turns_to_next_boundary":remaining,
        }

    animal=tile.get("animal")
    if animal in schedule["assets"]:
        typ=str(animal);spec=schedule["assets"][typ];p=spec["production"]
        origin=int(tile.get("placed_day",day));age=day-origin
        held=int(tile.get("yield_units",0) or 0)
        first=int(p["first_output_day_offset"]);interval=int(p["repeat_interval_days"])
        if day < origin+first:
            next_off=first
        else:
            elapsed=day-(origin+first)
            n=(elapsed+interval-1)//interval
            next_off=first+n*interval
        nxt_day=(origin+next_off)
        remaining=nxt_day*tpd-(day*tpd+hour)
        if remaining<0:
            remaining=0
        phase="HELD_OUTPUT" if held>0 else ("OUTPUT_BOUNDARY_NOW" if remaining==0 else "WAITING_SCHEDULED_OUTPUT")
        return {
          "asset_type":typ,"asset_class":"animal","x":x,"y":y,
          "origin_day":origin,"age_days":age,"held_output_units":held,
          "harvest_eligible_now":bool(held>0),
          "phase":phase,
          "next_boundary_kind":"scheduled_output",
          "next_boundary_day":nxt_day,
          "turns_to_next_boundary":remaining,
          "consecutive_unfed":int(tile.get("consecutive_unfed",0) or 0),
        }
    return None

def summarize(instances):
    by_type={}
    for z in instances:
        typ=z["asset_type"]
        r=by_type.setdefault(typ,{
          "count":0,"held_output_units":0,"harvest_ready_count":0,
          "boundary_now_count":0,"within_24_turns_count":0,"within_72_turns_count":0,
          "turns_to_boundaries":[]
        })
        r["count"]+=1
        r["held_output_units"]+=z["held_output_units"]
        if z["harvest_eligible_now"]:r["harvest_ready_count"]+=1
        t=z["turns_to_next_boundary"]
        if t is not None:
            r["turns_to_boundaries"].append(t)
            if t==0:r["boundary_now_count"]+=1
            if 0<=t<=24:r["within_24_turns_count"]+=1
            if 0<=t<=72:r["within_72_turns_count"]+=1
    return by_type

def main():
    schedule=json.loads(SCHEDULE.read_text(encoding="utf-8"))
    tpd=int(schedule["world"]["default_turns_per_day"])

    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=body_only.agent
    env.run(players)

    checkpoints=[]
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<2:continue
        so=plain(getv(step[SEAT],"observation"))
        oo=plain(getv(step[1-SEAT],"observation"))
        if not isinstance(so,dict) or not isinstance(oo,dict):continue
        day=int(so.get("day",0) or 0);hour=int(so.get("hour",0) or 0)
        if day not in TARGET_DAYS or hour!=0:continue

        sides={}
        for label,obs,pidx in (("self",so,SEAT),("opponent",oo,1-SEAT)):
            farm=(obs.get("farms") or [{},{}])[pidx]
            instances=[]
            for y,row in enumerate(farm.get("tiles",[]) or []):
                for x,tile in enumerate(row or []):
                    z=instance_from_tile(tile,x,y,day,hour,tpd,schedule)
                    if z:instances.append(z)
            sides[label]={"instances":instances,"summary_by_type":summarize(instances)}
        checkpoints.append({"day":day,"hour":hour,**sides})

    rewards=[float(x.reward) for x in env.state]
    payload={
      "schema":"kaggriculture.battle-asset-position-map.v0",
      "schedule_id":schedule["schedule_id"],
      "public_rule_commit":schedule["world"]["public_rule_commit"],
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "checkpoints":checkpoints,
      "boundary":[
        "Battle trace contributes asset instances only; State timing comes from Asset State Schedule v0.",
        "No market price, asset value, expected score, Candidate, Action diagnosis, or causal explanation.",
        "For nonongoing crops, turns_to_next_boundary identifies the public eligible WATER/output-formation window, not a guaranteed production event.",
        "For ongoing crops and animals, scheduled boundary is a public day-boundary opportunity conditional on survival."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BATTLE_ASSET_POSITION_MAP "+json.dumps({
      "seed":SEED,"seat":SEAT,"checkpoint_count":len(checkpoints),
      "terminal":payload["terminal"],
      "days":[{
        "day":c["day"],
        "self":c["self"]["summary_by_type"],
        "opponent":c["opponent"]["summary_by_type"]
      } for c in checkpoints]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
