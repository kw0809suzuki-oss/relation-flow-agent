#!/usr/bin/env python3
"""LAND Failed-PLANT Target Filler Audit v0.

Exact SB-01 baseline replay. No policy mutation.

Scope:
For PLANT requests in turns +1..+72 after first realized LAND expansion that
fail because their target became nonempty earlier in the SAME turn, record only:
- failed unit index / crop / target
- which earlier unit index first filled that target
- the exact earlier Action
- resulting tile type

No causal or intervention conclusion is emitted.
"""
import copy, json, os
from collections import Counter
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from analyze_sb01_economic_layers_v0 import CROPS

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
WINDOW=72
OUT=Path(f"land_failed_plant_target_filler_v0_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception: pass
    if hasattr(v,"tolist"):
        try:return plain(v.tolist())
        except Exception: pass
    if hasattr(v,"item"):
        try:return plain(v.item())
        except Exception: pass
    if hasattr(v,"__dict__"):
        try:return {str(k):plain(x) for k,x in vars(v).items() if not str(k).startswith("_")}
        except Exception: pass
    return str(v)

def getv(s,k,default=None):
    if isinstance(s,dict): return s.get(k,default)
    try:return getattr(s,k)
    except Exception:return default

def unlocked_count(obs):
    p=int(obs["player"]); farm=obs["farms"][p]
    return sum(1 for row in farm.get("tiles",[]) or [] for tile in row if tile!="LOCKED")

def side_rows(steps,seat):
    out=[]
    for i,step in enumerate(steps):
        if not isinstance(step,(list,tuple)) or len(step)<=seat: continue
        obs=plain(getv(step[seat],"observation"))
        if not isinstance(obs,dict) or "farms" not in obs: continue
        out.append({"step_index":i,"obs":obs,"action":plain(getv(step[seat],"action"))})
    return out

def first_land_i(rows):
    for i in range(1,len(rows)):
        if unlocked_count(rows[i]["obs"]) > unlocked_count(rows[i-1]["obs"]):
            return i
    return None

def positions(obs):
    p=int(obs["player"]); farm=obs["farms"][p]
    return [list(farm.get("farmer",[0,0]))]+[list(x) for x in (farm.get("hands",[]) or [])]

def actions(action):
    if not isinstance(action,dict): return []
    return [action.get("farmer",["PASS"])]+list(action.get("hands",[]) or [])

def tile_at(tiles,pos):
    x,y=pos
    return tiles[y][x]

def set_tile(tiles,pos,val):
    x,y=pos; tiles[y][x]=val

def tdesc(tile):
    if tile is None:return "EMPTY"
    if tile=="LOCKED":return "LOCKED"
    if isinstance(tile,dict):
        if tile.get("crop"):return "PLANT:"+str(tile.get("crop"))
        if tile.get("animal"):return "ANIMAL:"+str(tile.get("animal"))
        return str(tile.get("kind","DICT"))
    return str(tile)

def first_fill_events_for_turn(pre_obs,action,rel):
    p=int(pre_obs["player"]); farm=pre_obs["farms"][p]
    private=pre_obs.get("private",{}) or {}
    board=copy.deepcopy(farm.get("tiles",[]) or [])
    pos=positions(pre_obs); acts=actions(action)
    pre_seeds={c:int((private.get("seeds",{}) or {}).get(c,0) or 0) for c in CROPS}
    demand=Counter()
    for a in acts:
        if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS:
            demand[a[1]]+=1
    blocked={c for c,n in demand.items() if n>pre_seeds.get(c,0)}
    seeds=dict(pre_seeds)
    filler={}  # (x,y) -> first earlier filling action
    failed=[]

    for idx,a in enumerate(acts):
        if not isinstance(a,list) or not a or idx>=len(pos): continue
        p0=pos[idx]; key=tuple(p0); before=tile_at(board,p0)
        op=a[0]

        if op=="PLANT" and len(a)>=2 and a[1] in CROPS:
            crop=a[1]
            pre_original=tile_at(farm.get("tiles",[]) or [],p0)
            if crop in blocked:
                continue
            if before=="LOCKED":
                continue
            if before is not None:
                if pre_original is None and key in filler:
                    failed.append({
                      "relative_turn":rel,
                      "failed_unit_index":idx,
                      "failed_crop":crop,
                      "target":list(p0),
                      "filler_unit_index":filler[key]["unit_index"],
                      "filler_action":filler[key]["action"],
                      "filler_op":filler[key]["op"],
                      "filler_item":filler[key]["item"],
                      "filled_tile":filler[key]["filled_tile"],
                      "unit_order_gap":idx-filler[key]["unit_index"],
                    })
                continue
            if seeds.get(crop,0)<=0:
                continue
            seeds[crop]-=1
            new={"kind":"PLANT","crop":crop}
            set_tile(board,p0,new)
            if key not in filler:
                filler[key]={
                  "unit_index":idx,
                  "action":a,
                  "op":"PLANT",
                  "item":crop,
                  "filled_tile":tdesc(new),
                }
            continue

        # Only actions that can change EMPTY -> NONEMPTY matter.
        if before=="LOCKED":
            continue
        if op=="BUILD_COOP" and before is None:
            new={"kind":"COOP"}
            set_tile(board,p0,new)
            if key not in filler:
                filler[key]={"unit_index":idx,"action":a,"op":"BUILD_COOP","item":None,"filled_tile":"COOP"}
        elif op=="BUILD_PASTURE" and before is None:
            new={"kind":"PASTURE"}
            set_tile(board,p0,new)
            if key not in filler:
                filler[key]={"unit_index":idx,"action":a,"op":"BUILD_PASTURE","item":None,"filled_tile":"PASTURE"}
        elif op=="DIG":
            if before is not None and not (isinstance(before,dict) and "animal" in before):
                set_tile(board,p0,None)
        elif op=="HARVEST" and isinstance(before,dict) and before.get("kind")=="PLANT":
            crop=before.get("crop")
            if crop in CROPS and float(before.get("yield_units",0) or 0)>0 and not CROPS[crop]["ongoing"]:
                age=int(pre_obs.get("day",0) or 0)-int(before.get("planted_day",0) or 0)
                if age>=CROPS[crop]["first"]:
                    set_tile(board,p0,None)
    return failed

def build(rows):
    li=first_land_i(rows)
    if li is None:return {"land_event_found":False,"failed_plant_fillers":[]}
    end=min(len(rows)-1,li+WINDOW)
    failed=[]
    for j in range(li+1,end+1):
        failed.extend(first_fill_events_for_turn(rows[j-1]["obs"],rows[j]["action"],j-li))
    obs=rows[li]["obs"]
    return {
      "land_event_found":True,
      "land_event":{"step_index":rows[li]["step_index"],"day":int(obs.get("day",0) or 0),"hour":int(obs.get("hour",0) or 0)},
      "window_turns":end-li,
      "failed_plant_fillers":failed,
    }

def compact(side):
    fs=side.get("failed_plant_fillers",[])
    return {
      "count":len(fs),
      "filler_op":dict(Counter(x["filler_op"] for x in fs)),
      "pairs":dict(Counter(f'{x["filler_op"]}:{x.get("filler_item")}->{x["failed_crop"]}' for x in fs)),
      "unit_order_gap":dict(Counter(str(x["unit_order_gap"]) for x in fs)),
    }

def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[base.OPPONENT,base.OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)
    steps=getattr(env,"steps",[]) or []
    s=build(side_rows(steps,SEAT)); o=build(side_rows(steps,1-SEAT))
    rewards=[float(x.reward) for x in env.state]
    payload={
      "schema":"kaggriculture.land-failed-plant-target-filler.v0",
      "seed":SEED,"seat":SEAT,"policy_mutated":False,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "self":s,"opponent":o,
      "boundary":[
        "Exact SB-01 baseline policy/runtime; no Candidate or Action mutation.",
        "Only same-turn PLANT failures caused by an earlier unit filling the same initially-empty target are retained.",
        "Filler is the first earlier unit Action that changed that target from empty to nonempty in the same turn.",
        "No causal, policy, or intervention conclusion is emitted."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LAND_FAILED_PLANT_TARGET_FILLER "+json.dumps({
      "seed":SEED,"seat":SEAT,"terminal":payload["terminal"],
      "self":compact(s),"opponent":compact(o),
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
