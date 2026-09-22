#!/usr/bin/env python3
"""Completion Workload Separator Observer v1.

Corrected rerun of v0.
Fix:
- v0 captured the first turn of each day, which systematically observed hands
  before same-day HIRE expansion and distorted capacity/transport.
- v1 overwrites daily snapshots so the stored snapshot is the LAST observed turn
  of each requested day.
- v1 also captures PRE-ACTION workload whenever the Completion-only candidate
  actually returns a post-D14 BUY_SEED order.

No policy change. Same Completion-only candidate and same seeds.
"""

import copy, json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as current
import investment_completion_coordinate_v0 as candidate
from strong_origin import FIRST_YIELD, MAX_YIELD_DAY

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"completion_workload_separator_v1_{SEED}.json")
TOTAL_TURNS=24*30
SELLABLE=("WHEAT","STRAWBERRY","MELON","MILK","WOOL","EGG","FERTILIZER")
OBS_DAYS={14,18,22,24,26,29}

def configure_current():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    current.set_control_enabled(False)
    current.set_probe_enabled(True)
    current.set_attribution_enabled(True)
    current.reset_telemetry()

def configure_candidate():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    candidate.set_probe_enabled(True)
    candidate.set_attribution_enabled(True)
    candidate.reset_experiment()

def shed_cells(board_size):
    h=board_size//2
    return [(h-1,h-1),(h,h-1),(h-1,h),(h,h)]

def nearest_shed_distance(pos,cells):
    x,y=pos
    return min(abs(x-sx)+abs(y-sy) for sx,sy in cells)

def native_harvest_age(crop):
    if crop=="STRAWBERRY":
        return FIRST_YIELD.get(crop)
    return MAX_YIELD_DAY.get(crop)

def workload(obs,turn):
    p=int(obs["player"])
    me=obs["farms"][p]
    tiles=me.get("tiles",[]) or []
    private=obs.get("private",{}) or {}
    invs=list(private.get("inventories",[]) or [])
    positions=[me.get("farmer")]+list(me.get("hands",[]) or [])
    while len(invs)<len(positions):
        invs.append({})
    cells=shed_cells(len(tiles))

    water=harvest=weeds=animal=0
    active_crops=0
    future_crop_days=0
    for y,row in enumerate(tiles):
        for x,t in enumerate(row):
            if t=="LOCKED" or t is None or not isinstance(t,dict):
                continue
            kind=t.get("kind")
            if kind=="WEED":
                weeds+=1
            elif kind=="PLANT":
                crop=t.get("crop")
                active_crops+=1
                if not t.get("watered_today",False):
                    water+=1
                day=int(obs.get("day",0) or 0)
                age=day-int(t.get("planted_day",day) or day)
                hage=native_harvest_age(crop)
                if float(t.get("yield_units",0) or 0)>0 and hage is not None and (crop=="STRAWBERRY" or age>=hage):
                    harvest+=1
                if hage is not None:
                    future_crop_days+=max(0,int(hage)-age)
            elif kind=="PASTURE" and t.get("animal"):
                if float(t.get("yield_units",0) or 0)>0: animal+=1
                if not t.get("fed_today",False): animal+=1
                if t.get("fed_today",False) and not t.get("cared_today",False): animal+=1
                if t.get("fertilizer_available",False): animal+=1

    carried_units=0
    carried_qty=0
    transport_distance=0
    for i,pos in enumerate(positions):
        inv=invs[i] if i<len(invs) else {}
        qty=sum(int(inv.get(k,0) or 0) for k in SELLABLE) if isinstance(inv,dict) else 0
        if qty>0 and isinstance(pos,(list,tuple)) and len(pos)==2:
            carried_units+=1
            carried_qty+=qty
            transport_distance+=nearest_shed_distance(pos,cells)

    units=len(positions)
    remaining_turns=max(0,TOTAL_TURNS-turn)
    immediate=water+harvest+weeds+animal
    return {
        "day":int(obs.get("day",0) or 0),
        "turn":turn,
        "money":float(me.get("money",0) or 0),
        "units":units,
        "hands":max(0,units-1),
        "immediate_work":immediate,
        "water":water,
        "harvest":harvest,
        "weeds":weeds,
        "animal_work":animal,
        "active_crops":active_crops,
        "future_crop_days":future_crop_days,
        "carried_units":carried_units,
        "carried_qty":carried_qty,
        "transport_distance":transport_distance,
        "remaining_turns":remaining_turns,
        "remaining_capacity":units*remaining_turns,
        "immediate_per_unit":(immediate/units) if units else None,
    }

def has_seed_order(action):
    if not isinstance(action,dict):
        return False
    return any(isinstance(a,(list,tuple)) and a and a[0]=="BUY_SEED" for a in (action.get("market",[]) or []))

def play(mode):
    if mode=="baseline": configure_current()
    else: configure_candidate()

    daily_last={}
    seed_decisions=[]
    turn=0
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)

    def agent(obs):
        nonlocal turn
        pre=workload(obs,turn)
        day=pre["day"]

        action=current.agent(obs) if mode=="baseline" else candidate.agent(obs)

        if day in OBS_DAYS:
            # overwrite every call: final stored row is the last observed turn of day
            daily_last[day]=copy.deepcopy(pre)

        if mode=="candidate" and day>=14 and has_seed_order(action):
            seed_decisions.append({
                "pre":copy.deepcopy(pre),
                "market":copy.deepcopy(action.get("market",[]) or []),
            })

        turn+=1
        return action

    players=[OPPONENT,OPPONENT]
    players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {
        "self":rewards[SEAT],
        "opp":rewards[1-SEAT],
        "margin":rewards[SEAT]-rewards[1-SEAT],
        "daily_last":daily_last,
        "seed_decisions":seed_decisions,
    }

def summarize_decisions(rows):
    if not rows:
        return {"count":0}
    keys=["money","units","hands","immediate_work","future_crop_days","carried_qty","transport_distance","remaining_turns","remaining_capacity","immediate_per_unit"]
    out={"count":len(rows)}
    for k in keys:
        vals=[r["pre"][k] for r in rows if r["pre"].get(k) is not None]
        if vals:
            out["mean_"+k]=sum(vals)/len(vals)
            out["min_"+k]=min(vals)
            out["max_"+k]=max(vals)
    return out

def main():
    b=play("baseline")
    c=play("candidate")
    diff=c["self"]-b["self"]
    payload={
        "schema":"kaggriculture.completion-workload-separator.v1",
        "seed":SEED,"seat":SEAT,
        "baseline_self":b["self"],
        "candidate_self":c["self"],
        "self_diff":diff,
        "direction":"improved" if diff>0 else "worsened" if diff<0 else "equal",
        "candidate_daily_last":c["daily_last"],
        "candidate_seed_decisions":c["seed_decisions"],
        "candidate_seed_decision_summary":summarize_decisions(c["seed_decisions"]),
        "baseline_daily_last":b["daily_last"],
        "boundary":[
            "Corrected rerun of v0; v0 first-turn-of-day capacity observations are discarded.",
            "Daily snapshots are last observed turn of each requested day.",
            "Seed-decision workload is captured immediately before each actual post-D14 candidate BUY_SEED action.",
            "Observer only; no new policy, threshold, or separator is defined.",
            "Workload metrics remain descriptive proxies."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("COMPLETION_WORKLOAD_SEPARATOR_V1_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
