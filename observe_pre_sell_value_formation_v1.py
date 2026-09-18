#!/usr/bin/env python3
"""Pre-sell value formation observer v1.

Desk coordinate: Remaining Time x Value Flow.
For Day25-29 non-overlapping cycles, inspect 6 turns before SELL:
product quantities/stock value trajectory -> SELL quantity/value -> reinvestment.
Descriptive only; policy unchanged.
"""
import copy, json, statistics
from collections import Counter
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

OPPONENT=base.OPPONENT
PRODUCTS=("WHEAT","MILK","FERTILIZER")
def mean(xs): return statistics.mean(xs) if xs else None

def product_state(obs):
    private=obs.get("private",{}) or {}
    stores=[private.get("shed",{}) or {}]
    stores.extend(private.get("inventories",[]) or [])
    qty=Counter()
    for st in stores:
        if isinstance(st,dict):
            for k,v in st.items():
                if isinstance(v,(int,float)): qty[k]+=float(v)
    prices=((obs.get("market",{}) or {}).get("prices",{}) or {})
    value=sum(float(prices.get(k,0))*q for k,q in qty.items() if isinstance(prices.get(k),(int,float)))
    return {"qty":dict(qty),"value":value}

def parse(bundle):
    sells=[]; buys=[]; names=[]
    if not isinstance(bundle,dict): return sells,buys,names
    f=bundle.get("farmer")
    if isinstance(f,(list,tuple)) and f: names.append(str(f[0]))
    for sec in ("hands","market"):
        for a in bundle.get(sec,[]) or []:
            if isinstance(a,(list,tuple)) and a:
                op=str(a[0]); names.append(op)
                if op=="SELL": sells.append(list(a))
                elif op.startswith("BUY_"): buys.append(list(a))
    return sells,buys,names

def play(seed,seat):
    base._configure_baseline()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    trace=[]; turn=0
    def observed(obs):
        nonlocal turn
        p=int(obs["player"]); money=float(obs["farms"][p].get("money",0))
        ps=product_state(obs)
        b=agent.agent(obs); sells,buys,names=parse(b)
        trace.append({"turn":turn,"day":int(obs.get("day",0)),"money":money,
                      "stock_qty":ps["qty"],"stock_value":ps["value"],
                      "prices":copy.deepcopy(((obs.get("market",{}) or {}).get("prices",{}) or {})),
                      "sells":sells,"buys":buys,"names":names})
        turn+=1
        return b
    players=[OPPONENT,OPPONENT]; players[seat]=observed; env.run(players)
    terminal=float(env.state[seat].reward)

    cycles=[]; i=0
    while i<len(trace):
        row=trace[i]
        if row["day"]<25 or "DROP" not in row["names"]:
            i+=1; continue
        sell_i=next((j for j in range(i,min(len(trace),i+7)) if trace[j]["sells"]),None)
        if sell_i is None:
            i+=1; continue
        buy_i=next((j for j in range(sell_i+1,min(len(trace),sell_i+7)) if trace[j]["buys"]),None)
        end=buy_i if buy_i is not None else sell_i
        srow=trace[sell_i]
        pre_start=max(0,sell_i-6)
        pre=trace[pre_start:sell_i+1]
        sell_qty=sum(float(a[2]) if len(a)>2 and isinstance(a[2],(int,float)) else 1.0 for a in srow["sells"])
        sell_items=[a[1] if len(a)>1 else None for a in srow["sells"]]
        cycles.append({
          "start_turn":i,"sell_turn":sell_i,"buy_turn":buy_i,"end_turn":end,
          "throughput":(trace[end]["money"]-row["money"])/max(1,end-i),
          "money_delta":trace[end]["money"]-row["money"],
          "sell_qty":sell_qty,"sell_items":sell_items,
          "stock_value_tminus6":pre[0]["stock_value"],
          "stock_value_presell":srow["stock_value"],
          "stock_value_growth":srow["stock_value"]-pre[0]["stock_value"],
          "wheat_tminus6":pre[0]["stock_qty"].get("WHEAT",0),
          "wheat_presell":srow["stock_qty"].get("WHEAT",0),
          "milk_tminus6":pre[0]["stock_qty"].get("MILK",0),
          "milk_presell":srow["stock_qty"].get("MILK",0),
          "trajectory":[{"turn":x["turn"],"money":x["money"],"stock_value":x["stock_value"],
                         "WHEAT":x["stock_qty"].get("WHEAT",0),"MILK":x["stock_qty"].get("MILK",0)}
                        for x in pre]
        })
        i=end+1
    return {"seed":seed,"seat":seat,"terminal_self":terminal,"cycles":cycles}

def band(xs):
    return {
      "count":len(xs),
      "mean_throughput":mean([c["throughput"] for c in xs]),
      "mean_money_delta":mean([c["money_delta"] for c in xs]),
      "mean_sell_qty":mean([c["sell_qty"] for c in xs]),
      "mean_stock_value_tminus6":mean([c["stock_value_tminus6"] for c in xs]),
      "mean_stock_value_presell":mean([c["stock_value_presell"] for c in xs]),
      "mean_stock_value_growth":mean([c["stock_value_growth"] for c in xs]),
      "mean_wheat_tminus6":mean([c["wheat_tminus6"] for c in xs]),
      "mean_wheat_presell":mean([c["wheat_presell"] for c in xs]),
      "mean_milk_tminus6":mean([c["milk_tminus6"] for c in xs]),
      "mean_milk_presell":mean([c["milk_presell"] for c in xs]),
    }

def summarize(rows):
    cs=[c for r in rows for c in r["cycles"]]
    ranked=sorted(cs,key=lambda c:c["throughput"])
    n=max(1,len(ranked)//3)
    return {"all":band(cs),"low_throughput":band(ranked[:n]),"high_throughput":band(ranked[-n:]),"cycles":cs}

def main():
    rows=[play(int(s),int(seat)) for s,seat in base.DEFAULT_CASES]
    ranked=sorted(rows,key=lambda r:r["terminal_self"]); n=min(4,max(1,len(ranked)//3))
    out={"schema":"pre-sell-value-formation.v1","objective":"terminal self",
      "coordinate":"Remaining Time x Value Flow","window":"Day25-29",
      "question":"does strong late throughput arise from larger value formation before SELL, or mainly from sell/reinvestment timing?",
      "policy_mutated":False,"causal_attribution":False,
      "low_terminal":summarize(ranked[:n]),"high_terminal":summarize(ranked[-n:]),
      "boundary":"stock_value is shed+carried product stock at observed market prices; descriptive, not production/profit"}
    open("pre_sell_value_formation_v1.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("PRE_SELL_VALUE_FORMATION_V1 "+json.dumps({
      "low_low":out["low_terminal"]["low_throughput"],"low_high":out["low_terminal"]["high_throughput"],
      "high_low":out["high_terminal"]["low_throughput"],"high_high":out["high_terminal"]["high_throughput"]
    },separators=(",",":")))

if __name__=="__main__": main()
