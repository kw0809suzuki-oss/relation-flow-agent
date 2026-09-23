#!/usr/bin/env python3
import json, os
from pathlib import Path
from collections import Counter
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"hire_settlement_cost_v0_{SEED}.json")

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

def parse_market(action, prices):
    hire=0; sell_face=0.0; buy_face=0.0
    for o in (action.get("market",[]) if isinstance(action,dict) else []) or []:
        if not isinstance(o,(list,tuple)) or not o: continue
        cmd=str(o[0])
        if cmd=="HIRE":
            hire+=1
        elif len(o)>=3 and isinstance(o[2],(int,float)):
            item=str(o[1]); qty=float(o[2]); px=float(prices.get(item,0) or 0)
            if cmd=="SELL": sell_face += px*qty
            elif cmd in ("BUY_PRODUCT","BUY_SEED","BUY_ANIMAL"): buy_face += px*qty
    return hire,sell_face,buy_face

def main():
    configure()
    rows=[]
    pending=None

    def wrapped(obs):
        nonlocal pending
        me=obs["farms"][obs["player"]]
        day=int(obs.get("day",0) or 0)
        now_money=float(me.get("money",0) or 0)
        now_hands=len(me.get("hands",[]) or [])

        if pending is not None:
            pending["after_day"]=day
            pending["money_after"]=now_money
            pending["hands_after"]=now_hands
            pending["money_delta"]=now_money-pending["money_before"]
            pending["hands_delta"]=now_hands-pending["hands_before"]
            pending["priced_market_net_face"]=pending["sell_face_value"]-pending["priced_buy_face_value"]
            pending["money_residual_after_priced_market_face"]=pending["money_delta"]-pending["priced_market_net_face"]
            pending["hire_settlement_proxy"]=pending["hands_delta"]>0
            rows.append(pending)
            pending=None

        action=combat.agent(obs)
        if 10 <= day <= 15:
            prices=dict((obs.get("market",{}) or {}).get("prices",{}) or {})
            hire,sell_face,buy_face=parse_market(action,prices)
            if hire>0:
                pending={
                  "day":day,
                  "money_before":now_money,
                  "hands_before":now_hands,
                  "hire_requests":hire,
                  "sell_face_value":sell_face,
                  "priced_buy_face_value":buy_face
                }
        return action

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=wrapped
    env.run(players)
    rewards=[float(s.reward) for s in env.state]

    settled=[x for x in rows if x["hire_settlement_proxy"]]
    unsettled=[x for x in rows if not x["hire_settlement_proxy"]]

    def avg(xs,key):
        return sum(x[key] for x in xs)/len(xs) if xs else None

    payload={
      "schema":"kaggriculture.hire-settlement-cost.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "summary":{
        "hire_request_turns":len(rows),
        "settlement_proxy_turns":len(settled),
        "unsettled_request_turns":len(unsettled),
        "settled_mean_hands_delta":avg(settled,"hands_delta"),
        "settled_mean_money_residual":avg(settled,"money_residual_after_priced_market_face"),
        "unsettled_mean_money_residual":avg(unsettled,"money_residual_after_priced_market_face")
      },
      "turns":rows,
      "boundary":"hands_delta>0 is a settlement proxy; no assumed HIRE price and no causal attribution."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,**payload["summary"]},ensure_ascii=False))

if __name__=="__main__": main()
