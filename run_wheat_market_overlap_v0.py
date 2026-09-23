#!/usr/bin/env python3
import json, os
from pathlib import Path
from collections import defaultdict
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"wheat_market_overlap_v0_{SEED}.json")

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

def wheat_orders(action, prices):
    sell_u=buy_u=0.0; sell_v=buy_v=0.0
    for o in (action.get("market",[]) if isinstance(action,dict) else []) or []:
        if not isinstance(o,(list,tuple)) or len(o)<3 or str(o[1])!="WHEAT" or not isinstance(o[2],(int,float)):
            continue
        cmd=str(o[0]); qty=float(o[2]); px=float(prices.get("WHEAT",0) or 0)
        if cmd=="SELL":
            sell_u += qty; sell_v += qty*px
        elif cmd=="BUY_PRODUCT":
            buy_u += qty; buy_v += qty*px
    return sell_u,sell_v,buy_u,buy_v

def main():
    configure()
    turns=[]; pending=None

    def wrapped(obs):
        nonlocal pending
        day=int(obs.get("day",0) or 0)
        me=obs["farms"][obs["player"]]
        money=float(me.get("money",0) or 0)

        if pending is not None:
            pending["money_after"]=money
            pending["money_delta"]=money-pending["money_before"]
            turns.append(pending)
            pending=None

        final_action=combat.agent(obs)
        if 10 <= day <= 20:
            prices=dict((obs.get("market",{}) or {}).get("prices",{}) or {})
            trace=combat.get_last_trace() if hasattr(combat,"get_last_trace") else {}
            base_action=(trace or {}).get("base_action",{}) or {}
            bs,bsv,bb,bbv=wheat_orders(base_action,prices)
            fs,fsv,fb,fbv=wheat_orders(final_action,prices)
            if fs>0 or fb>0 or bs>0 or bb>0:
                pending={
                  "day":day,
                  "money_before":money,
                  "wheat_price":float(prices.get("WHEAT",0) or 0),
                  "base_sell_units":bs,
                  "base_buy_product_units":bb,
                  "final_sell_units":fs,
                  "final_sell_face_value":fsv,
                  "final_buy_product_units":fb,
                  "final_buy_product_face_value":fbv,
                  "same_turn_overlap":bool(fs>0 and fb>0),
                  "overlap_units":min(fs,fb),
                  "net_wheat_market_units":fb-fs,
                  "net_wheat_market_face":fbv-fsv,
                  "base_sell_present":bool(bs>0),
                  "final_buy_present":bool(fb>0),
                  "overlay_opposite_surface":bool(bs>0 and fb>0)
                }
        return final_action

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=wrapped
    env.run(players)
    rewards=[float(s.reward) for s in env.state]

    byday=defaultdict(list)
    for t in turns: byday[t["day"]].append(t)
    days=[]
    for d in range(10,21):
        xs=byday.get(d,[])
        if not xs: continue
        sell=sum(x["final_sell_units"] for x in xs)
        buy=sum(x["final_buy_product_units"] for x in xs)
        days.append({
          "day":d,
          "turns_with_wheat_market":len(xs),
          "same_turn_overlap_turns":sum(1 for x in xs if x["same_turn_overlap"]),
          "overlay_opposite_surface_turns":sum(1 for x in xs if x["overlay_opposite_surface"]),
          "sell_units":sell,
          "buy_product_units":buy,
          "overlap_units":sum(x["overlap_units"] for x in xs),
          "sell_face_value":sum(x["final_sell_face_value"] for x in xs),
          "buy_product_face_value":sum(x["final_buy_product_face_value"] for x in xs),
          "net_wheat_market_units":buy-sell,
          "money_delta_sum":sum(x["money_delta"] for x in xs)
        })

    payload={
      "schema":"kaggriculture.wheat-market-overlap.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "turns":turns,"days":days,
      "boundary":[
        "Market orders are requests, not settlement receipts.",
        "Opposite same-turn WHEAT orders show action-surface conflict only.",
        "No round-trip loss or inefficiency is inferred without intervention."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"turns":len(turns),"overlap":sum(t["same_turn_overlap"] for t in turns)},ensure_ascii=False))

if __name__=="__main__": main()
