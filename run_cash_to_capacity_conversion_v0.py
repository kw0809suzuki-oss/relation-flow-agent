#!/usr/bin/env python3
import json, os
from pathlib import Path
from collections import Counter
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"cash_to_capacity_conversion_v0_{SEED}.json")

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

def visible(farm):
    crops=0; animals=0; prod=0; animal_types=Counter()
    for row in farm.get("tiles",[]) or []:
        for tile in row:
            if tile=="LOCKED" or tile is None or not isinstance(tile,dict):
                continue
            kind=tile.get("kind")
            if kind=="PLANT":
                crops += 1; prod += 1
            animal=tile.get("animal")
            if animal is not None:
                animals += 1; prod += 1
                if isinstance(animal,str): animal_types[animal]+=1
                elif isinstance(animal,dict):
                    animal_types[str(animal.get("type") or animal.get("kind") or "UNKNOWN")]+=1
            elif kind=="ANIMAL":
                animals += 1; prod += 1
                animal_types[str(tile.get("type") or "UNKNOWN")]+=1
    return {
      "money":float(farm.get("money",0) or 0),
      "hands":len(farm.get("hands",[]) or []),
      "land":len(farm.get("unlocked_quadrants",[]) or []),
      "crop_tiles":crops,
      "animal_tiles":animals,
      "production_tiles":prod,
      "animal_types":dict(animal_types)
    }

def market_summary(action):
    out={"HIRE":0,"BUY_LAND":0,"BUY_ANIMAL":0,"BUY_SEED":0,"BUY_PRODUCT":0,
         "SELL":0,"other":[],"raw":[]}
    if not isinstance(action,dict): return out
    for x in action.get("market",[]) or []:
        if not isinstance(x,(list,tuple)) or not x: continue
        cmd=str(x[0]); out["raw"].append(list(x))
        if cmd in out and cmd!="other":
            if cmd in ("BUY_SEED","BUY_PRODUCT","SELL"):
                qty=x[-1] if len(x)>=3 and isinstance(x[-1],(int,float)) else 1
                out[cmd]+=qty
            else:
                out[cmd]+=1
        else: out["other"].append(list(x))
    return out

def delta(a,b):
    return {k:b[k]-a[k] for k in ["money","hands","land","crop_tiles","animal_tiles","production_tiles"]}

def main():
    configure()
    state_rows=[]; action_rows=[]

    def observed(obs):
        d=int(obs.get("day",0) or 0)
        me=obs["farms"][obs["player"]]; opp=obs["farms"][1-obs["player"]]
        state_rows.append({"turn":len(state_rows),"day":d,"self":visible(me),"opponent":visible(opp)})
        action=combat.agent(obs)
        if 5 <= d <= 12:
            action_rows.append({"turn":len(state_rows)-1,"day":d,"market":market_summary(action)})
        return action

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=observed
    env.run(players)
    rewards=[float(s.reward) for s in env.state]

    # last visible state each day
    day_end={}
    for r in state_rows:
        if 4 <= r["day"] <= 13: day_end[r["day"]]=r

    days=[]
    for d in range(5,13):
        cur=day_end.get(d); prev=day_end.get(d-1); nxt=day_end.get(d+1)
        acts=[x["market"] for x in action_rows if x["day"]==d]
        summed={k:sum(a.get(k,0) for a in acts) for k in ["HIRE","BUY_LAND","BUY_ANIMAL","BUY_SEED","BUY_PRODUCT","SELL"]}
        raw=[r for a in acts for r in a.get("raw",[])]
        rec={"day":d,"self_actions":summed,"self_market_raw":raw}
        if cur:
            rec["self_state"]=cur["self"]; rec["opponent_state"]=cur["opponent"]
        if prev and cur:
            rec["self_change_from_prior_day"]=delta(prev["self"],cur["self"])
            rec["opponent_change_from_prior_day"]=delta(prev["opponent"],cur["opponent"])
        if cur and nxt:
            rec["self_next_day_retention"]=delta(cur["self"],nxt["self"])
            rec["opponent_next_day_retention"]=delta(cur["opponent"],nxt["opponent"])
        days.append(rec)

    payload={
      "schema":"kaggriculture.cash-to-capacity-conversion.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "days":days,
      "boundary":[
        "Self investment actions are exact returned market actions.",
        "Opponent investment is not observed directly; only visible state changes are recorded.",
        "No causal or payback attribution is made."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"self":rewards[SEAT],"opp":rewards[1-SEAT]},ensure_ascii=False))

if __name__=="__main__": main()
