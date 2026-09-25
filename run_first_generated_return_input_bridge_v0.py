#!/usr/bin/env python3
"""First generated Return -> productive Input cash bridge v0.

A generated Return is restricted to realized SELL of a non-WHEAT product whose
initial on-hand quantity is zero and which cannot be externally BUY_PRODUCTed.
Thus the sold unit must have entered inventory through the farm's output path.

The first bridge is the earliest productive market order that becomes
unaffordable when cumulative prior generated-Return SELL cash is removed from
actual cash before that order.

Observation only. No motive, optimality, or later-production causality claimed.
"""
import json,os
from pathlib import Path
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg
import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body

SEED=int(os.environ["BATTLE_SEED"]);SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"first_generated_return_input_bridge_v0_{SEED}_seat{SEAT}.json")
PRODUCTIVE={"BUY_SEED","BUY_ANIMAL","BUY_LAND","HIRE"}
EXACT_RETURN_ITEMS={"MELON","STRAWBERRY","MILK","WOOL","EGG"}
events=[]; gen_cash=[0.0,0.0]; initial_on_hand=None

def cfgget(obj,key,default):
    if isinstance(obj,dict):return obj.get(key,default)
    return getattr(obj,key,default)

def stock(obs,p,item):
    pr=obs[p].private
    shed=pr.shed if hasattr(pr,"shed") else {}
    qty=int(shed.get(item,0) or 0)
    for inv in pr.inventories:
        qty+=int(inv.get(item,0) or 0)
    return qty

def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0";os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body.reset_telemetry()

def measured_market(state,env):
    obs0=state[0].observation; market=obs0.market;farms=obs0.farms
    priv=[s.observation.private for s in state]
    day=int(obs0.day);hour=int(obs0.hour)
    board_size=int(cfgget(env.configuration,"boardSize",10))
    max_orders=max(1,int(cfgget(env.configuration,"maxMarketOrdersPerTurn",10)))
    hire_mult=int(cfgget(env.configuration,"farmHandCostMult",kg.FARM_HAND_COST_MULT))
    shed_capacity=int(cfgget(env.configuration,"shedCapacity",100))
    queues=[]
    for s in state:
        a=s.action if isinstance(s.action,dict) else {}
        m=a.get("market",[]) if isinstance(a,dict) else []
        queues.append(list(m)[:max_orders] if isinstance(m,list) else [])
    for order_i in range(max((len(q) for q in queues),default=0)):
        sts=[kg._parse_order(q[order_i]) if order_i<len(q) else None for q in queues]
        for p,st in enumerate(sts):
            if st is None:continue
            op=st["type"]
            if op=="HIRE":
                before=float(farms[p]["money"]);without=before-gen_cash[p]
                kg._do_hire(farms[p],priv[p],board_size,hire_mult)
                after=float(farms[p]["money"]);delta=after-before
                if delta:
                    cost=-delta;events.append({"player":p,"day":day,"hour":hour,"op":"HIRE","item":None,
                      "cash_before":before,"cash_after":after,"cost":cost,"generated_return_cash_before":gen_cash[p],
                      "cash_without_generated_return":without,"generated_return_necessary":gen_cash[p]>0 and without<cost})
                sts[p]=None
            elif op=="BUY_LAND":
                before=float(farms[p]["money"]);without=before-gen_cash[p]
                kg._do_buy_land(farms[p],board_size)
                after=float(farms[p]["money"]);delta=after-before
                if delta:
                    cost=-delta;events.append({"player":p,"day":day,"hour":hour,"op":"BUY_LAND","item":None,
                      "cash_before":before,"cash_after":after,"cost":cost,"generated_return_cash_before":gen_cash[p],
                      "cash_without_generated_return":without,"generated_return_necessary":gen_cash[p]>0 and without<cost})
                sts[p]=None
        guard=0
        while True:
            guard+=1
            if guard>100000:break
            quoted=[None,None]
            for p,st in enumerate(sts):
                if st is None or st["remaining"]<=0:continue
                op,item=st["type"],st["item"]
                if op=="SELL" and item in kg.PRODUCTS:
                    quoted[p]=(op,item,kg.market_price(item,market["inventory"][item],market.get("params")),st)
                elif op=="BUY_PRODUCT" and item in ("WHEAT","FERTILIZER"):
                    quoted[p]=(op,item,kg.market_price(item,market["inventory"][item]-1,market.get("params")),st)
                elif op=="BUY_SEED" and item in kg.CROPS:
                    quoted[p]=(op,item,kg.CROPS[item]["seed"],st)
                elif op=="BUY_ANIMAL" and item in kg.ANIMALS:
                    quoted[p]=(op,item,kg.ANIMALS[item]["cost"],st)
                else: sts[p]=None
            if all(x is None for x in quoted):break
            any_ok=False
            for p,q in enumerate(quoted):
                if q is None:continue
                op,item,price,st=q
                before=float(farms[p]["money"]);without=before-gen_cash[p]
                ok=kg._commit_unit(op,item,price,farms[p],priv[p],market,shed_capacity)
                after=float(farms[p]["money"])
                if ok:
                    delta=after-before
                    generated_return=False
                    if op=="SELL" and item in EXACT_RETURN_ITEMS and initial_on_hand[p].get(item,0)==0:
                        gen_cash[p]+=delta;generated_return=True
                    rec={"player":p,"day":day,"hour":hour,"op":op,"item":item,"price":float(price),
                         "cash_before":before,"cash_after":after,"cash_delta":delta,
                         "generated_return_sell":generated_return}
                    if op in PRODUCTIVE:
                        cost=-delta;rec.update({"cost":cost,"generated_return_cash_before":gen_cash[p],
                         "cash_without_generated_return":without,
                         "generated_return_necessary":gen_cash[p]>0 and without<cost})
                    events.append(rec);st["remaining"]-=1;any_ok=True
                else:sts[p]=None
            if not any_ok:break
        kg._refresh_prices(market)

def main():
    global initial_on_hand
    configure();events.clear();gen_cash[0]=gen_cash[1]=0.0
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    obs=env.state[0].observation
    initial_on_hand=[{i:stock([obs,obs],p,i) for i in EXACT_RETURN_ITEMS} for p in (0,1)]
    original=kg._process_market;kg._process_market=measured_market
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT];players[SEAT]=body.agent;env.run(players)
    finally:kg._process_market=original
    rewards=[float(x.reward) for x in env.state]
    first={}
    for p in (0,1):
        xs=[e for e in events if e["player"]==p and e["op"] in PRODUCTIVE and e.get("generated_return_necessary")]
        first[str(p)]=xs[0] if xs else None
    ret=[e for e in events if e.get("generated_return_sell")]
    payload={"schema":"kaggriculture.first-generated-return-input-bridge.v0","seed":SEED,"seat":SEAT,
      "initial_on_hand":initial_on_hand,"first_by_player":first,
      "generated_return_sells":ret,
      "productive_events":[e for e in events if e["op"] in PRODUCTIVE],
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "boundary":[
       "Generated Return is restricted to non-WHEAT products with zero initial on-hand and no external BUY_PRODUCT path.",
       "This proves cash necessity on the actual outflow path only.",
       "It does not yet prove that the identified input causes later Production."
      ]}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("FIRST_GENERATED_RETURN_INPUT_BRIDGE "+json.dumps({"seed":SEED,"seat":SEAT,
      "self":first[str(SEAT)],"opponent":first[str(1-SEAT)],
      "generated_return_sell_count":{"self":sum(e["player"]==SEAT for e in ret),"opponent":sum(e["player"]==1-SEAT for e in ret)}},
      ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
