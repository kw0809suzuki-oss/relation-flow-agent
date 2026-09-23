#!/usr/bin/env python3
import json, os
from pathlib import Path
from collections import Counter
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"day_boundary_cash_drain_v0_{SEED}.json")

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

def stock(obs):
    p=obs["private"]
    c=Counter()
    for k,v in (p.get("shed",{}) or {}).items():
        if isinstance(v,(int,float)): c[str(k)]+=v
    for inv in p.get("inventories",[]) or []:
        for k,v in (inv or {}).items():
            if isinstance(v,(int,float)): c[str(k)]+=v
    return dict(c)

def animal_count(farm):
    n=0
    for row in farm.get("tiles",[]) or []:
        for tile in row:
            if not isinstance(tile,dict): continue
            if tile.get("animal") is not None or tile.get("kind")=="ANIMAL":
                n+=1
    return n

def state(obs):
    me=obs["farms"][obs["player"]]
    return {
      "day":int(obs.get("day",0) or 0),
      "money":float(me.get("money",0) or 0),
      "hands":len(me.get("hands",[]) or []),
      "animals":animal_count(me),
      "stock":stock(obs)
    }

def main():
    configure()
    boundaries=[]
    prev_state=None
    prev_action=None

    def wrapped(obs):
        nonlocal prev_state,prev_action
        cur=state(obs)
        if prev_state is not None and cur["day"] != prev_state["day"]:
            market=list((prev_action or {}).get("market",[]) or [])
            keys=set(prev_state["stock"])|set(cur["stock"])
            stock_change={k:float(cur["stock"].get(k,0) or 0)-float(prev_state["stock"].get(k,0) or 0) for k in sorted(keys)}
            boundaries.append({
              "from_day":prev_state["day"],
              "to_day":cur["day"],
              "money_before":prev_state["money"],
              "money_after":cur["money"],
              "money_delta":cur["money"]-prev_state["money"],
              "hands_before":prev_state["hands"],
              "hands_after":cur["hands"],
              "hands_delta":cur["hands"]-prev_state["hands"],
              "animals_before":prev_state["animals"],
              "animals_after":cur["animals"],
              "animals_delta":cur["animals"]-prev_state["animals"],
              "stock_before":prev_state["stock"],
              "stock_after":cur["stock"],
              "stock_change":stock_change,
              "prior_turn_market":market,
              "prior_turn_market_order_count":len(market),
              "prior_turn_market_empty":len(market)==0
            })
        action=combat.agent(obs)
        prev_state=cur
        prev_action=action
        return action

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=wrapped
    env.run(players)
    rewards=[float(s.reward) for s in env.state]

    kept=[b for b in boundaries if 5 <= b["from_day"] <= 20]
    payload={
      "schema":"kaggriculture.day-boundary-cash-drain.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "boundaries":kept,
      "boundary":"Day transition timing only; no mechanism label or causal attribution."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"boundaries":len(kept),"negative":sum(b["money_delta"]<0 for b in kept)},ensure_ascii=False))

if __name__=="__main__": main()
