#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"crop_demand_execution_gap_v0_{SEED}.json")

CROP={"WATER","HARVEST","PLANT"}

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    for k in ["OUTER_MEANING_OPTION_PRESERVATION_DAY","OUTER_MEANING_REALIZABLE_CAPACITY_DAY","OUTER_MEANING_CONVERSION_PATH_DAY","OUTER_MEANING_GUIDED_CONVERSION_DAY"]:
        os.environ.pop(k,None)
    os.environ["OUTER_MEANING_OBJECTIVE_PRESSURE_DAY"]="14"
    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"
    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1"
    os.environ["ORIGIN_GUIDANCE_MODE"]="objective_pressure_guidance"
    combat.set_probe_enabled(True); combat.set_attribution_enabled(True); combat.reset_telemetry()

def snapshots():
    return ((((combat.get_trace() or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def crop_tiles(obs):
    me=obs["farms"][obs["player"]]
    n=0
    for row in me.get("tiles",[]) or []:
        for tile in row:
            if isinstance(tile,dict) and tile.get("kind")=="PLANT":
                n+=1
    return n

def flat(action):
    out={}
    if not isinstance(action,dict): return out
    out["farmer"]=action.get("farmer")
    for i,a in enumerate(action.get("hands",[]) or []):
        out[f"hand{i}"]=a
    return out

def verb(a):
    return str(a[0]) if isinstance(a,(list,tuple)) and a else None

def main():
    configure()
    turn_state={}
    def wrapped(obs):
        t=len(turn_state)
        turn_state[t]={"day":int(obs.get("day",0) or 0),"crop_tiles":crop_tiles(obs)}
        return combat.agent(obs)

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=wrapped
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    ss=snapshots()

    day_last={}
    for t,s in turn_state.items():
        if 4 <= s["day"] <= 13:
            day_last[s["day"]]=(t,s["crop_tiles"])

    loss_days=[]
    precursor_turns=set()
    for d in range(5,13):
        if d in day_last and d+1 in day_last:
            delta=day_last[d+1][1]-day_last[d][1]
            if delta < 0:
                loss_days.append({"day":d,"crop_delta_next_day":delta})
                # last six turns of the source day; dedupe globally
                ds=[int(s.get("turn",-1)) for s in ss if int(s.get("day",0) or 0)==d]
                for t in ds[-6:]:
                    if t>=0: precursor_turns.add(t)

    rows=[]
    totals={"base_crop_demand":0,"actual_crop_execution":0,"missed_crop_exec":0,
            "overlay_changed_slots":0,"missed_due_to_changed_slot":0,
            "base_water":0,"actual_water":0,
            "base_harvest":0,"actual_harvest":0,
            "base_plant":0,"actual_plant":0}
    for s in ss:
        t=int(s.get("turn",-1))
        if t not in precursor_turns: continue
        b=flat(s.get("base_action",{}) or {})
        a=flat(s.get("action",{}) or {})
        slot_rows=[]
        for slot in sorted(set(b)|set(a)):
            bv, av=b.get(slot),a.get(slot)
            vb,va=verb(bv),verb(av)
            changed=bv!=av
            base_crop=vb in CROP
            actual_crop=va in CROP
            if base_crop:
                totals["base_crop_demand"]+=1
                totals[f"base_{vb.lower()}"]+=1
            if actual_crop:
                totals["actual_crop_execution"]+=1
                totals[f"actual_{va.lower()}"]+=1
            if changed: totals["overlay_changed_slots"]+=1
            missed=base_crop and not actual_crop
            if missed:
                totals["missed_crop_exec"]+=1
                if changed: totals["missed_due_to_changed_slot"]+=1
            if base_crop or actual_crop or changed:
                slot_rows.append({
                  "slot":slot,"base":bv,"actual":av,"base_verb":vb,"actual_verb":va,
                  "changed":changed,"base_crop":base_crop,"actual_crop":actual_crop,
                  "missed_crop_execution":missed
                })
        rows.append({"turn":t,"day":s.get("day"),"slots":slot_rows})

    payload={
      "schema":"kaggriculture.crop-demand-execution-gap.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "crop_loss_days":loss_days,
      "unique_precursor_turns":len(precursor_turns),
      "summary":totals,
      "turns":rows,
      "boundary":"Requested-vs-executed crop work only; no inference about why crop tiles disappeared."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"loss_days":loss_days,"turns":len(precursor_turns),"summary":totals},ensure_ascii=False))

if __name__=="__main__": main()
