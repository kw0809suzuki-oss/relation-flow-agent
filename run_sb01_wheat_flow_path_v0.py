#!/usr/bin/env python3
"""SB-01 WHEAT flow path observer v0.\n\nRun marker: preflight 7001.

Policy/action generation is unchanged.
The public market processor is replaced with a logging-equivalent copy, as in
the exact Cash ledger, and WHEAT stock is sampled immediately before/after each
market phase.

Observed path for Day0..7:
  initial WHEAT
  -> between-market net stock changes
  -> realized BUY_PRODUCT:WHEAT / SELL:WHEAT
  -> first Day8 WHEAT stock

No stock decrease is interpreted as feed/need/waste in this observer.
"""
import json, os
from collections import defaultdict
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])

market_rows=[[],[]]
purchase_rows=[[],[]]
_call_index=0

def cfgget(obj,key,default):
    if isinstance(obj,dict): return obj.get(key,default)
    return getattr(obj,key,default)

def getv(obj,key,default=None):
    if isinstance(obj,dict): return obj.get(key,default)
    try: return getattr(obj,key)
    except Exception: return default

def wheat_parts(private):
    shed=getv(private,"shed",{}) or {}
    invs=getv(private,"inventories",[]) or []
    shed_w=int(getv(shed,"WHEAT",0) or 0)
    carried=0
    for inv in invs:
        carried += int(getv(inv,"WHEAT",0) or 0)
    return {"shed":shed_w,"carried":carried,"total":shed_w+carried}

def demand_state(farm,private):
    by=defaultdict(int); unfed_by=defaultdict(int); unfed_streak_by=defaultdict(int)
    tiles=getv(farm,"tiles",[]) or []
    for row in tiles:
        for tile in row or []:
            if not isinstance(tile,dict):
                try:
                    animal=getv(tile,"animal",None)
                except Exception:
                    animal=None
            else:
                animal=tile.get("animal")
            if not animal: continue
            by[str(animal)] += 1
            fed=bool(getv(tile,"fed_today",False))
            if not fed:
                unfed_by[str(animal)] += 1
            streak=int(getv(tile,"consecutive_unfed",0) or 0)
            if streak>0:
                unfed_streak_by[str(animal)] += 1
    wp=wheat_parts(private)
    return {
      "wheat":wp,
      "animals_on_farm":dict(sorted(by.items())),
      "unfed_animals":dict(sorted(unfed_by.items())),
      "animals_with_unfed_streak":dict(sorted(unfed_streak_by.items())),
      "animal_total":sum(by.values()),
      "unfed_total":sum(unfed_by.values()),
      "hands":len(getv(farm,"hands",[]) or []),
      "money":float(getv(farm,"money",0) or 0),
    }

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def measured_process_market(state,env):
    global _call_index
    obs0=state[0].observation
    day=int(getv(obs0,"day",0) or 0); hour=int(getv(obs0,"hour",0) or 0)
    market=obs0.market; farms=obs0.farms
    privates=[s.observation.private for s in state]
    board_size=int(cfgget(env.configuration,"boardSize",10))
    max_orders=max(1,int(cfgget(env.configuration,"maxMarketOrdersPerTurn",10)))
    hire_mult=int(cfgget(env.configuration,"farmHandCostMult",kg.FARM_HAND_COST_MULT))
    shed_capacity=int(cfgget(env.configuration,"shedCapacity",100))

    tracked=day < 8
    rows=[None,None]
    if tracked:
        for p in (0,1):
            rows[p]={
              "call_index":_call_index,"day":day,"hour":hour,
              "pre_market":demand_state(farms[p],privates[p]),
              "buy_wheat_units":0,"buy_wheat_cash":0.0,
              "sell_wheat_units":0,"sell_wheat_cash":0.0,
              "post_market":None,
            }

    queues=[]
    for s in state:
        action=s.action if isinstance(s.action,dict) else {}
        m=action.get("market",[]) if isinstance(action,dict) else []
        queues.append(list(m)[:max_orders] if isinstance(m,list) else [])

    max_len=max((len(q) for q in queues),default=0)
    purchase_by_player=[None,None]

    for i in range(max_len):
        order_states=[]
        for p,q in enumerate(queues):
            order_states.append(kg._parse_order(q[i]) if i<len(q) else None)

        for p,ostate in enumerate(order_states):
            if ostate is None: continue
            op=ostate["type"]
            if op=="HIRE":
                kg._do_hire(farms[p],privates[p],board_size,hire_mult)
                order_states[p]=None
            elif op=="BUY_LAND":
                kg._do_buy_land(farms[p],board_size)
                order_states[p]=None

        guard=0
        while True:
            guard+=1
            if guard>=100000: break
            quoted=[None,None]
            for p,ostate in enumerate(order_states):
                if ostate is None or ostate["remaining"]<=0: continue
                op=ostate["type"]; item=ostate["item"]
                if op=="SELL" and item in kg.PRODUCTS:
                    quoted[p]=("SELL",item,kg.market_price(item,market["inventory"][item],market.get("params")),ostate)
                elif op=="BUY_PRODUCT" and item in ("WHEAT","FERTILIZER"):
                    quoted[p]=("BUY_PRODUCT",item,kg.market_price(item,market["inventory"][item]-1,market.get("params")),ostate)
                elif op=="BUY_SEED" and item in kg.CROPS:
                    quoted[p]=("BUY_SEED",item,kg.CROPS[item]["seed"],ostate)
                elif op=="BUY_ANIMAL" and item in kg.ANIMALS:
                    quoted[p]=("BUY_ANIMAL",item,kg.ANIMALS[item]["cost"],ostate)
                else:
                    order_states[p]=None
            if all(q is None for q in quoted): break

            committed=False
            for p,q in enumerate(quoted):
                if q is None: continue
                op,item,price,ostate=q
                before_money=float(farms[p]["money"])
                before_wheat=wheat_parts(privates[p])["total"]
                if tracked and op=="BUY_PRODUCT" and item=="WHEAT" and purchase_by_player[p] is None:
                    purchase_by_player[p]={
                      "call_index":_call_index,"day":day,"hour":hour,
                      "state_before_first_buy":demand_state(farms[p],privates[p]),
                      "market_inventory_wheat_before_first_buy":int(market["inventory"].get("WHEAT",0) or 0),
                      "units":0,"cash":0.0,"state_after_market":None,
                    }
                    purchase_rows[p].append(purchase_by_player[p])
                ok=kg._commit_unit(op,item,price,farms[p],privates[p],market,shed_capacity)
                after_money=float(farms[p]["money"])
                if ok:
                    delta=after_money-before_money
                    if tracked and item=="WHEAT":
                        if op=="BUY_PRODUCT":
                            rows[p]["buy_wheat_units"]+=1
                            rows[p]["buy_wheat_cash"]+=-delta
                            if purchase_by_player[p] is not None:
                                purchase_by_player[p]["units"]+=1
                                purchase_by_player[p]["cash"]+=-delta
                        elif op=="SELL":
                            rows[p]["sell_wheat_units"]+=1
                            rows[p]["sell_wheat_cash"]+=delta
                    ostate["remaining"]-=1
                    committed=True
                else:
                    order_states[p]=None
            if not committed: break

        kg._refresh_prices(market)

    if tracked:
        for p in (0,1):
            rows[p]["post_market"]=demand_state(farms[p],privates[p])
            market_rows[p].append(rows[p])
            if purchase_by_player[p] is not None:
                purchase_by_player[p]["state_after_market"]=demand_state(farms[p],privates[p])
    _call_index += 1

def first_day8_wheat(env,p):
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<=p: continue
        obs=getv(step[p],"observation",None)
        if obs is None: continue
        if int(getv(obs,"day",-1) or -1)==8:
            return wheat_parts(getv(obs,"private",{}) or {})["total"]
    return None

def summarize_player(p,initial,day8):
    rows=market_rows[p]
    prev=float(initial)
    between=[]
    buy=sell=0
    market_phase_errors=[]
    for row in rows:
        pre=float(row["pre_market"]["wheat"]["total"])
        post=float(row["post_market"]["wheat"]["total"])
        delta=pre-prev
        between.append({"call_index":row["call_index"],"day":row["day"],"hour":row["hour"],"delta":delta})
        market_net=row["buy_wheat_units"]-row["sell_wheat_units"]
        market_phase_errors.append((post-pre)-market_net)
        buy += int(row["buy_wheat_units"]); sell += int(row["sell_wheat_units"])
        prev=post
    tail=float(day8)-prev if day8 is not None else None
    if tail is not None:
        between.append({"call_index":None,"day":8,"hour":0,"delta":tail,"segment":"after_last_day7_market_to_day8_start"})
    vals=[float(x["delta"]) for x in between]
    nonmarket_net=sum(vals)
    gross_decrease=sum(-x for x in vals if x<0)
    gross_increase=sum(x for x in vals if x>0)
    reconstructed=float(initial)+nonmarket_net+buy-sell
    return {
      "initial_wheat":initial,
      "day8_start_wheat":day8,
      "buy_units":buy,
      "sell_units":sell,
      "between_market_net_change":nonmarket_net,
      "between_market_gross_decrease":gross_decrease,
      "between_market_gross_increase":gross_increase,
      "reconstructed_day8":reconstructed,
      "mass_balance_error":None if day8 is None else reconstructed-float(day8),
      "market_phase_max_abs_error":max([abs(x) for x in market_phase_errors],default=0.0),
      "between_market_segments":between,
      "market_rows":rows,
      "purchase_events":purchase_rows[p],
    }

def main():
    configure()
    original=kg._process_market
    kg._process_market=measured_process_market
    try:
        env=make("kaggriculture",configuration={"seed":SEED},debug=False)
        initial=[wheat_parts(env.state[p].observation.private)["total"] for p in (0,1)]
        players=[base.OPPONENT,base.OPPONENT]; players[SEAT]=combat.agent
        env.run(players)
        terminal=[float(x.reward) for x in env.state]
        day8=[first_day8_wheat(env,p) for p in (0,1)]
    finally:
        kg._process_market=original

    players_out=[summarize_player(p,initial[p],day8[p]) for p in (0,1)]
    self_row=players_out[SEAT]; opp_row=players_out[1-SEAT]
    payload={
      "schema":"kaggriculture.sb01.wheat-flow-path.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":terminal[SEAT],"opponent":terminal[1-SEAT],"margin":terminal[SEAT]-terminal[1-SEAT]},
      "self":self_row,"opponent":opp_row,"players":players_out,
      "boundary":[
        "Policy and Action generation are unchanged.",
        "Market execution is a logging-equivalent copy of the confirmed public processor.",
        "WHEAT stock is total across shed plus carried inventories, so PICKUP/DROP alone does not change total stock.",
        "Between-market stock change is observed net movement only; no cause such as FEED, HARVEST, necessity, excess, or waste is assigned.",
        "Day8 start stock is the first retained Day8 observation before Day8 actions."
      ]
    }
    out=f"sb01_wheat_flow_path_{SEED}.json"
    with open(out,"w",encoding="utf-8") as f:
        json.dump(payload,f,ensure_ascii=False,indent=2);f.write("\n")
    print("SB01_WHEAT_FLOW_PATH "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "self":{"buy":self_row["buy_units"],"sell":self_row["sell_units"],"nonmarket_net":self_row["between_market_net_change"],"day8":self_row["day8_start_wheat"],"error":self_row["mass_balance_error"],"market_error":self_row["market_phase_max_abs_error"],"purchase_events":len(self_row["purchase_events"])},
      "opponent":{"buy":opp_row["buy_units"],"sell":opp_row["sell_units"],"nonmarket_net":opp_row["between_market_net_change"],"day8":opp_row["day8_start_wheat"],"error":opp_row["mass_balance_error"],"market_error":opp_row["market_phase_max_abs_error"],"purchase_events":len(opp_row["purchase_events"])}
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
