#!/usr/bin/env python3
import json, os
from pathlib import Path
from collections import Counter,defaultdict
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"item_value_density_v0_{SEED}.json")

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
    p=obs["private"]; c=Counter()
    for k,v in (p.get("shed",{}) or {}).items():
        if isinstance(v,(int,float)): c[str(k)]+=float(v)
    for inv in p.get("inventories",[]) or []:
        for k,v in (inv or {}).items():
            if isinstance(v,(int,float)): c[str(k)]+=float(v)
    return dict(c)

def main():
    configure()
    day_states=defaultdict(list)
    day_orders=defaultdict(lambda:defaultdict(lambda:{"sell_units":0.0,"sell_face":0.0,"buy_product_units":0.0}))

    def wrapped(obs):
        day=int(obs.get("day",0) or 0)
        me=obs["farms"][obs["player"]]
        if 10 <= day <= 20:
            day_states[day].append({"money":float(me.get("money",0) or 0),"stock":stock(obs)})
        action=combat.agent(obs)
        if 10 <= day <= 20:
            prices=dict((obs.get("market",{}) or {}).get("prices",{}) or {})
            for o in action.get("market",[]) or []:
                if not isinstance(o,(list,tuple)) or len(o)<3 or not isinstance(o[2],(int,float)):
                    continue
                cmd,item,qty=str(o[0]),str(o[1]),float(o[2])
                if cmd=="SELL":
                    day_orders[day][item]["sell_units"] += qty
                    day_orders[day][item]["sell_face"] += qty*float(prices.get(item,0) or 0)
                elif cmd=="BUY_PRODUCT":
                    day_orders[day][item]["buy_product_units"] += qty
        return action

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=wrapped
    env.run(players)
    rewards=[float(s.reward) for s in env.state]

    days=[]
    for d in range(10,21):
        states=day_states.get(d,[])
        if not states: continue
        start=states[0]; end=states[-1]
        keys=set(start["stock"])|set(end["stock"])|set(day_orders[d])
        items={}
        total_units=sum(v["sell_units"] for v in day_orders[d].values())
        total_face=sum(v["sell_face"] for v in day_orders[d].values())
        for item in sorted(keys):
            od=day_orders[d][item]
            su=od["sell_units"]; sf=od["sell_face"]; bp=od["buy_product_units"]
            st=float(start["stock"].get(item,0) or 0); en=float(end["stock"].get(item,0) or 0)
            items[item]={
              "sell_units":su,
              "sell_face_value":sf,
              "sell_value_per_unit":(sf/su if su else None),
              "sell_units_share":(su/total_units if total_units else 0.0),
              "sell_value_share":(sf/total_face if total_face else 0.0),
              "stock_start":st,
              "stock_end":en,
              "stock_delta":en-st,
              "buy_product_units":bp,
              "materialized_units_proxy":en-st+su-bp
            }
        days.append({
          "day":d,
          "money_start":start["money"],"money_end":end["money"],
          "total_sell_units":total_units,"total_sell_face_value":total_face,
          "items":items
        })

    payload={
      "schema":"kaggriculture.item-value-density.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "days":days,
      "boundary":[
        "SELL is order-side proxy, not settlement receipt.",
        "Private stock is availability context, not guaranteed sellable stock.",
        "Materialized units is an accounting proxy and may include concurrent consumption or placement."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"self":rewards[SEAT],"days":len(days)},ensure_ascii=False))

if __name__=="__main__": main()
