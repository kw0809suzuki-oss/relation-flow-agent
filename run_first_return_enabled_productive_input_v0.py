#!/usr/bin/env python3
"""First Return-enabled Productive Input v0.

Observation only. For each player, find the earliest realized productive market
order that would not have been affordable if all prior realized SELL cash were
removed while preserving the actual prior outflows.

This establishes external cash necessity only. It does not assign motive or
claim a specific sold unit paid for a specific input.
"""
import json, os
from pathlib import Path
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg
import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"first_return_enabled_productive_input_v0_{SEED}_seat{SEAT}.json")
PRODUCTIVE={"BUY_SEED","BUY_ANIMAL","BUY_LAND","HIRE"}
events=[]
cum_sell=[0.0,0.0]

def cfgget(obj,key,default):
    if isinstance(obj,dict): return obj.get(key,default)
    return getattr(obj,key,default)

def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body.reset_telemetry()

def measured_market(state,env):
    obs0=state[0].observation
    market=obs0.market
    farms=obs0.farms
    priv=[s.observation.private for s in state]
    day=int(obs0.day); hour=int(obs0.hour)
    board_size=int(cfgget(env.configuration,"boardSize",10))
    max_orders=max(1,int(cfgget(env.configuration,"maxMarketOrdersPerTurn",10)))
    hire_mult=int(cfgget(env.configuration,"farmHandCostMult",kg.FARM_HAND_COST_MULT))
    shed_capacity=int(cfgget(env.configuration,"shedCapacity",100))
    queues=[]
    for s in state:
        a=s.action if isinstance(s.action,dict) else {}
        m=a.get("market",[]) if isinstance(a,dict) else []
        queues.append(list(m)[:max_orders] if isinstance(m,list) else [])
    max_len=max((len(q) for q in queues),default=0)
    event_index=0
    for i in range(max_len):
        order_states=[]
        for p,q in enumerate(queues):
            order_states.append(kg._parse_order(q[i]) if i<len(q) else None)
        for p,ost in enumerate(order_states):
            if ost is None: continue
            op=ost["type"]
            if op=="HIRE":
                before=float(farms[p]["money"]); no_ret=before-cum_sell[p]
                kg._do_hire(farms[p],priv[p],board_size,hire_mult)
                after=float(farms[p]["money"]); delta=after-before
                if delta!=0:
                    cost=-delta
                    events.append({"player":p,"day":day,"hour":hour,"event_index":event_index,
                      "op":"HIRE","item":None,"cash_before":before,"cash_after":after,"cost":cost,
                      "prior_sell_cash":cum_sell[p],"cash_without_prior_sell":no_ret,
                      "return_necessary":no_ret < cost})
                    event_index+=1
                order_states[p]=None
            elif op=="BUY_LAND":
                before=float(farms[p]["money"]); no_ret=before-cum_sell[p]
                kg._do_buy_land(farms[p],board_size)
                after=float(farms[p]["money"]); delta=after-before
                if delta!=0:
                    cost=-delta
                    events.append({"player":p,"day":day,"hour":hour,"event_index":event_index,
                      "op":"BUY_LAND","item":None,"cash_before":before,"cash_after":after,"cost":cost,
                      "prior_sell_cash":cum_sell[p],"cash_without_prior_sell":no_ret,
                      "return_necessary":no_ret < cost})
                    event_index+=1
                order_states[p]=None
        guard=0
        while True:
            guard+=1
            if guard>=100000: break
            quoted=[None,None]
            for p,ost in enumerate(order_states):
                if ost is None or ost["remaining"]<=0: continue
                op=ost["type"]; item=ost["item"]
                if op=="SELL" and item in kg.PRODUCTS:
                    quoted[p]=("SELL",item,kg.market_price(item,market["inventory"][item],market.get("params")),ost)
                elif op=="BUY_PRODUCT" and item in ("WHEAT","FERTILIZER"):
                    quoted[p]=("BUY_PRODUCT",item,kg.market_price(item,market["inventory"][item]-1,market.get("params")),ost)
                elif op=="BUY_SEED" and item in kg.CROPS:
                    quoted[p]=("BUY_SEED",item,kg.CROPS[item]["seed"],ost)
                elif op=="BUY_ANIMAL" and item in kg.ANIMALS:
                    quoted[p]=("BUY_ANIMAL",item,kg.ANIMALS[item]["cost"],ost)
                else:
                    order_states[p]=None
            if all(q is None for q in quoted): break
            any_ok=False
            for p,q in enumerate(quoted):
                if q is None: continue
                op,item,price,ost=q
                before=float(farms[p]["money"]); no_ret=before-cum_sell[p]
                ok=kg._commit_unit(op,item,price,farms[p],priv[p],market,shed_capacity)
                after=float(farms[p]["money"])
                if ok:
                    delta=after-before
                    if op=="SELL":
                        cum_sell[p]+=delta
                    rec={"player":p,"day":day,"hour":hour,"event_index":event_index,
                         "op":op,"item":item,"price":float(price),"cash_before":before,
                         "cash_after":after,"cash_delta":delta,"prior_sell_cash":cum_sell[p]-(delta if op=="SELL" else 0)}
                    if op in PRODUCTIVE:
                        cost=-delta
                        rec.update({"cost":cost,"cash_without_prior_sell":no_ret,
                                    "return_necessary":no_ret < cost})
                    events.append(rec); event_index+=1
                    ost["remaining"]-=1; any_ok=True
                else:
                    order_states[p]=None
            if not any_ok: break
        kg._refresh_prices(market)

def main():
    configure(); events.clear(); cum_sell[0]=cum_sell[1]=0.0
    original=kg._process_market; kg._process_market=measured_market
    try:
        env=make("kaggriculture",configuration={"seed":SEED},debug=False)
        players=[basecfg.OPPONENT,basecfg.OPPONENT]; players[SEAT]=body.agent
        env.run(players)
    finally:
        kg._process_market=original
    rewards=[float(x.reward) for x in env.state]
    first={}
    for p in (0,1):
        xs=[e for e in events if e["player"]==p and e["op"] in PRODUCTIVE and e.get("return_necessary")]
        first[str(p)]=xs[0] if xs else None
    payload={"schema":"kaggriculture.first-return-enabled-productive-input.v0","seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "first_by_player":first,
      "productive_events":[e for e in events if e["op"] in PRODUCTIVE],
      "boundary":[
        "Return necessity means actual cash before the order minus all prior realized SELL cash is less than the realized order cost.",
        "This is a cash-feasibility counterfactual on the actual prior outflow path, not token-level cash lineage.",
        "BUY_PRODUCT is excluded from productive input here and treated as operating spend.",
        "No claim yet that the identified productive order created the later Production separator."
      ]}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("FIRST_RETURN_ENABLED_PRODUCTIVE_INPUT "+json.dumps({"seed":SEED,"seat":SEAT,
      "self":first[str(SEAT)],"opponent":first[str(1-SEAT)]},ensure_ascii=False,separators=(",",":")))
if __name__=="__main__": main()
