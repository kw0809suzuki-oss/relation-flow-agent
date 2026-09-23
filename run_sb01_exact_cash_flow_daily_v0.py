#!/usr/bin/env python3
"""SB-01 exact Cash Flow accounting preflight.

Monkeypatches ONLY Kaggriculture's public-rule market processor with a
line-for-line equivalent that logs realized Cash deltas per executed order.
Policy/action generation is unchanged.

Validation gate:
  initial Cash + sum(realized cash events) == terminal reward
for both players.
"""
import json, os
from collections import defaultdict
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])

def cfgget(obj,key,default):
    if isinstance(obj,dict):
        return obj.get(key,default)
    return getattr(obj,key,default)

ledger=[defaultdict(float),defaultdict(float)]
units=[defaultdict(int),defaultdict(int)]
daily_ledger=[defaultdict(lambda: defaultdict(float)),defaultdict(lambda: defaultdict(float))]
daily_units=[defaultdict(lambda: defaultdict(int)),defaultdict(lambda: defaultdict(int))]
events=[]

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def key(op,item=None):
    return f"{op}:{item}" if item else op

def measured_process_market(state, env):
    obs0=state[0].observation
    day=int(getattr(obs0,"day",0))
    hour=int(getattr(obs0,"hour",0))
    market=obs0.market
    farms=obs0.farms
    privates=[s.observation.private for s in state]
    board_size=int(cfgget(env.configuration,"boardSize",10))
    max_orders=max(1,int(cfgget(env.configuration,"maxMarketOrdersPerTurn",10)))
    hire_mult=int(cfgget(env.configuration,"farmHandCostMult",kg.FARM_HAND_COST_MULT))
    shed_capacity=int(cfgget(env.configuration,"shedCapacity",100))

    queues=[]
    for s in state:
        action=s.action if isinstance(s.action,dict) else {}
        m=action.get("market",[]) if isinstance(action,dict) else []
        q=list(m) if isinstance(m,list) else []
        queues.append(q[:max_orders])

    max_len=max((len(q) for q in queues),default=0)
    for i in range(max_len):
        order_states=[]
        for player_id,q in enumerate(queues):
            ostate=kg._parse_order(q[i]) if i<len(q) else None
            order_states.append(ostate)

        for player_id,ostate in enumerate(order_states):
            if ostate is None: continue
            op=ostate["type"]
            if op=="HIRE":
                before=float(farms[player_id]["money"])
                before_hires=int(farms[player_id]["hires_today"])
                kg._do_hire(farms[player_id],privates[player_id],board_size,hire_mult)
                after=float(farms[player_id]["money"])
                delta=after-before
                if delta!=0:
                    ledger[player_id]["HIRE"]+=delta
                    units[player_id]["HIRE"]+=1
                    daily_ledger[player_id][day]["HIRE"]+=delta
                    daily_units[player_id][day]["HIRE"]+=1
                    events.append({"player":player_id,"day":day,"hour":hour,"op":"HIRE","cash_delta":delta,"hires_before":before_hires})
                order_states[player_id]=None
            elif op=="BUY_LAND":
                before=float(farms[player_id]["money"])
                before_n=len(farms[player_id]["unlocked_quadrants"])
                kg._do_buy_land(farms[player_id],board_size)
                after=float(farms[player_id]["money"])
                delta=after-before
                if delta!=0:
                    ledger[player_id]["BUY_LAND"]+=delta
                    units[player_id]["BUY_LAND"]+=1
                    daily_ledger[player_id][day]["BUY_LAND"]+=delta
                    daily_units[player_id][day]["BUY_LAND"]+=1
                    events.append({"player":player_id,"day":day,"hour":hour,"op":"BUY_LAND","cash_delta":delta,"unlocked_before":before_n})
                order_states[player_id]=None

        idx_esc=0
        while True:
            idx_esc+=1
            if idx_esc>=100000: break
            quoted=[None,None]
            for player_id,ostate in enumerate(order_states):
                if ostate is None or ostate["remaining"]<=0: continue
                op=ostate["type"];item=ostate["item"]
                if op=="SELL" and item in kg.PRODUCTS:
                    quoted[player_id]=("SELL",item,kg.market_price(item,market["inventory"][item],market.get("params")),ostate)
                elif op=="BUY_PRODUCT" and item in ("WHEAT","FERTILIZER"):
                    quoted[player_id]=("BUY_PRODUCT",item,kg.market_price(item,market["inventory"][item]-1,market.get("params")),ostate)
                elif op=="BUY_SEED" and item in kg.CROPS:
                    quoted[player_id]=("BUY_SEED",item,kg.CROPS[item]["seed"],ostate)
                elif op=="BUY_ANIMAL" and item in kg.ANIMALS:
                    quoted[player_id]=("BUY_ANIMAL",item,kg.ANIMALS[item]["cost"],ostate)
                else:
                    order_states[player_id]=None
            if all(q is None for q in quoted): break

            committed_any=False
            for player_id,q in enumerate(quoted):
                if q is None: continue
                op,item,price,ostate=q
                before=float(farms[player_id]["money"])
                ok=kg._commit_unit(op,item,price,farms[player_id],privates[player_id],market,shed_capacity)
                after=float(farms[player_id]["money"])
                if ok:
                    delta=after-before
                    k=key(op,item)
                    ledger[player_id][k]+=delta
                    units[player_id][k]+=1
                    daily_ledger[player_id][day][k]+=delta
                    daily_units[player_id][day][k]+=1
                    events.append({"player":player_id,"day":day,"hour":hour,"op":op,"item":item,"price":price,"cash_delta":delta})
                    ostate["remaining"]-=1
                    committed_any=True
                else:
                    order_states[player_id]=None
            if not committed_any: break

        kg._refresh_prices(market)

OUT=f"sb01_exact_cash_flow_daily_{SEED}.json"

def main():
    configure()
    original=kg._process_market
    kg._process_market=measured_process_market
    try:
        env=make("kaggriculture",configuration={"seed":SEED},debug=False)
        players=[base.OPPONENT,base.OPPONENT]
        players[SEAT]=combat.agent
        # Initial cash from initial environment state after reset/make.
        initial=[float(env.state[i].observation.farms[i].money) for i in (0,1)]
        env.run(players)
        terminal=[float(x.reward) for x in env.state]
    finally:
        kg._process_market=original

    result=[]
    for p in (0,1):
        net=sum(ledger[p].values())
        reconstructed=initial[p]+net
        result.append({
            "player":p,
            "initial_cash":initial[p],
            "cash_flow_net":net,
            "reconstructed_terminal":reconstructed,
            "actual_terminal":terminal[p],
            "error":reconstructed-terminal[p],
            "ledger":dict(sorted(ledger[p].items())),
            "executed_units":dict(sorted(units[p].items())),
            "daily_ledger":{str(day):dict(sorted(vals.items())) for day,vals in sorted(daily_ledger[p].items())},
            "daily_executed_units":{str(day):dict(sorted(vals.items())) for day,vals in sorted(daily_units[p].items())},
        })
    self_row=result[SEAT]
    opp_row=result[1-SEAT]
    payload={
      "schema":"kaggriculture.sb01.exact-cash-flow-daily.v0",
      "seed":SEED,"seat":SEAT,
      "self":self_row,
      "opponent":opp_row,
      "players":result,
      "event_count":len(events),
      "boundary":[
        "Policy and Action generation are unchanged.",
        "Only environment market processing is replaced with a logging-equivalent implementation copied from the confirmed public rules.",
        "All ledger values are realized Cash deltas from successfully executed units/orders.",
        "This preflight is valid only if reconstruction error is exactly zero for both players."
      ]
    }
    with open(OUT,"w",encoding="utf-8") as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)
        f.write("\n")
    print("SB01_EXACT_CASH_FLOW_DAILY "+json.dumps({
        "seed":SEED,"seat":SEAT,
        "self_terminal":self_row["actual_terminal"],
        "opponent_terminal":opp_row["actual_terminal"],
        "self_error":self_row["error"],
        "opponent_error":opp_row["error"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
