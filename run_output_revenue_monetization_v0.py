#!/usr/bin/env python3
import json, os
from pathlib import Path
from collections import Counter,defaultdict
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"output_revenue_monetization_v0_{SEED}.json")

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

def units(action):
    result=[]
    if not isinstance(action,dict): return result
    result.append(action.get("farmer"))
    result.extend(action.get("hands",[]) or [])
    return result

def verb(a):
    return str(a[0]) if isinstance(a,(list,tuple)) and a else None

def main():
    configure()
    states=[]
    events=[]
    def wrapped(obs):
        turn=len(states)
        day=int(obs.get("day",0) or 0)
        me=obs["farms"][obs["player"]]
        opp=obs["farms"][1-obs["player"]]
        s={
          "turn":turn,"day":day,
          "self_money":float(me.get("money",0) or 0),
          "opp_money":float(opp.get("money",0) or 0),
          "stock":stock(obs)
        }
        states.append(s)
        action=combat.agent(obs)
        if 5 <= day <= 15:
            prices=dict((obs.get("market",{}) or {}).get("prices",{}) or {})
            sells=Counter(); buys=Counter(); sell_value=0.0
            for o in action.get("market",[]) or []:
                if not isinstance(o,(list,tuple)) or len(o)<3: continue
                cmd,item,qty=str(o[0]),str(o[1]),o[2]
                if not isinstance(qty,(int,float)): continue
                if cmd=="SELL":
                    sells[item]+=qty
                    sell_value += float(prices.get(item,0) or 0)*qty
                elif cmd=="BUY_PRODUCT":
                    buys[item]+=qty
            harvests=sum(1 for a in units(action) if verb(a)=="HARVEST")
            events.append({
              "turn":turn,"day":day,
              "sell_units":dict(sells),
              "buy_product_units":dict(buys),
              "gross_sell_face_value":sell_value,
              "harvest_actions":harvests
            })
        return action

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=wrapped
    env.run(players)
    rewards=[float(s.reward) for s in env.state]

    day_states=defaultdict(list)
    for s in states:
        if 5 <= s["day"] <= 16: day_states[s["day"]].append(s)
    day_events=defaultdict(list)
    for e in events: day_events[e["day"]].append(e)

    days=[]
    for d in range(5,16):
        if not day_states.get(d): continue
        start=day_states[d][0]
        # next day first state gives post-day stock/money when available
        if day_states.get(d+1):
            end=day_states[d+1][0]
        else:
            end=day_states[d][-1]
        sells=Counter(); buys=Counter(); gross=0.0; harvest=0
        for e in day_events.get(d,[]):
            sells.update(e["sell_units"]); buys.update(e["buy_product_units"])
            gross+=e["gross_sell_face_value"]; harvest+=e["harvest_actions"]
        keys=set(start["stock"])|set(end["stock"])|set(sells)|set(buys)
        balance={}
        for k in sorted(keys):
            delta=float(end["stock"].get(k,0) or 0)-float(start["stock"].get(k,0) or 0)
            materialized=delta+float(sells.get(k,0))-float(buys.get(k,0))
            balance[k]={
              "start_stock":start["stock"].get(k,0),
              "end_stock":end["stock"].get(k,0),
              "stock_delta":delta,
              "sold_units":sells.get(k,0),
              "bought_product_units":buys.get(k,0),
              "materialized_units_proxy":materialized
            }
        days.append({
          "day":d,
          "self_money_start":start["self_money"],
          "self_money_end":end["self_money"],
          "self_money_delta":end["self_money"]-start["self_money"],
          "opp_money_start":start["opp_money"],
          "opp_money_end":end["opp_money"],
          "opp_money_delta":end["opp_money"]-start["opp_money"],
          "harvest_actions":harvest,
          "gross_sell_face_value":gross,
          "sold_units_total":sum(sells.values()),
          "buy_product_units_total":sum(buys.values()),
          "materialized_units_proxy_total":sum(v["materialized_units_proxy"] for v in balance.values()),
          "items":balance
        })

    payload={
      "schema":"kaggriculture.output-revenue-monetization.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "days":days,
      "boundary":[
        "Self stock is exact private shed+inventory accounting.",
        "Materialized units is a stock-balance proxy, not direct causal HARVEST attribution.",
        "Gross sell face value is market-order value, not isolated net cashflow.",
        "Opponent private output flow is not observed; only opponent money trajectory is compared."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"self":rewards[SEAT],"opp":rewards[1-SEAT],"days":len(days)},ensure_ascii=False))

if __name__=="__main__": main()
