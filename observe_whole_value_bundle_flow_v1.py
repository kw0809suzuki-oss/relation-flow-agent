#!/usr/bin/env python3
"""Whole Value Bundle Flow observer v1.

Desk coordinate: whole-flow bundle.
Treat each late non-overlapping cycle as one bundle transition:
pre-sell resource bundle -> sell bundle -> reinvest bundle -> retained cash.

Descriptive only. No policy mutation. Bundle composition is observational.
"""
import copy, json, statistics
from collections import Counter
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

OPPONENT=base.OPPONENT
PRODUCTS=("WHEAT","MILK","FERTILIZER")
def mean(xs): return statistics.mean(xs) if xs else None

def stock(obs):
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
    return dict(qty), value, copy.deepcopy(prices)

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
        qty,val,prices=stock(obs)
        b=agent.agent(obs); sells,buys,names=parse(b)
        trace.append({"turn":turn,"day":int(obs.get("day",0)),"money":money,
                      "qty":qty,"stock_value":val,"prices":prices,
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
        srow=trace[sell_i]; brow=trace[buy_i] if buy_i is not None else None
        pre=trace[max(0,sell_i-6)]

        sell_bundle=Counter()
        for a in srow["sells"]:
            item=a[1] if len(a)>1 else None
            q=float(a[2]) if len(a)>2 and isinstance(a[2],(int,float)) else 1.0
            sell_bundle[item]+=q

        buy_bundle=Counter()
        if brow:
            for a in brow["buys"]:
                kind=str(a[0]) if a else "UNKNOWN"
                item=a[1] if len(a)>1 else None
                q=float(a[2]) if len(a)>2 and isinstance(a[2],(int,float)) else 1.0
                buy_bundle[f"{kind}:{item}"]+=q

        cycles.append({
          "start_turn":i,"sell_turn":sell_i,"buy_turn":buy_i,"end_turn":end,
          "flow_turns":end-i,
          "throughput":(trace[end]["money"]-row["money"])/max(1,end-i),
          "money_delta":trace[end]["money"]-row["money"],
          "cash_retained":trace[end]["money"],
          "pre_bundle":{k:float(pre["qty"].get(k,0)) for k in PRODUCTS},
          "presell_bundle":{k:float(srow["qty"].get(k,0)) for k in PRODUCTS},
          "pre_bundle_value":pre["stock_value"],
          "presell_bundle_value":srow["stock_value"],
          "sell_bundle":dict(sell_bundle),
          "buy_bundle":dict(buy_bundle),
        })
        i=end+1
    return {"seed":seed,"seat":seat,"terminal_self":terminal,"cycles":cycles}

def band(xs):
    if not xs: return {"count":0}
    sell=Counter(); buy=Counter()
    for c in xs:
        sell.update(c["sell_bundle"]); buy.update(c["buy_bundle"])
    return {
      "count":len(xs),
      "mean_throughput":mean([c["throughput"] for c in xs]),
      "mean_money_delta":mean([c["money_delta"] for c in xs]),
      "mean_cash_retained":mean([c["cash_retained"] for c in xs]),
      "mean_pre_bundle_value":mean([c["pre_bundle_value"] for c in xs]),
      "mean_presell_bundle_value":mean([c["presell_bundle_value"] for c in xs]),
      "mean_pre_WHEAT":mean([c["pre_bundle"]["WHEAT"] for c in xs]),
      "mean_pre_MILK":mean([c["pre_bundle"]["MILK"] for c in xs]),
      "mean_presell_WHEAT":mean([c["presell_bundle"]["WHEAT"] for c in xs]),
      "mean_presell_MILK":mean([c["presell_bundle"]["MILK"] for c in xs]),
      "sell_bundle_totals":sell.most_common(),
      "buy_bundle_totals":buy.most_common(),
    }

def summarize(rows):
    cs=[c for r in rows for c in r["cycles"]]
    ranked=sorted(cs,key=lambda c:c["throughput"])
    n=max(1,len(ranked)//3)
    return {"all":band(cs),"low_throughput":band(ranked[:n]),"high_throughput":band(ranked[-n:]),"cycles":cs}

def main():
    rows=[play(int(s),int(seat)) for s,seat in base.DEFAULT_CASES]
    ranked=sorted(rows,key=lambda r:r["terminal_self"]); n=min(4,max(1,len(ranked)//3))
    out={"schema":"whole-value-bundle-flow.v1","objective":"terminal self",
      "coordinate":"Whole Value Bundle Flow","window":"Day25-29",
      "bundle":"pre-sell resources -> sell bundle -> reinvest bundle -> retained cash",
      "policy_mutated":False,"causal_attribution":False,
      "low_terminal":summarize(ranked[:n]),"high_terminal":summarize(ranked[-n:]),
      "boundary":"bundle statistics are observational and do not prove resource conversion causality"}
    open("whole_value_bundle_flow_v1.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("WHOLE_VALUE_BUNDLE_FLOW_V1 "+json.dumps({
      "low_low":out["low_terminal"]["low_throughput"],
      "low_high":out["low_terminal"]["high_throughput"],
      "high_low":out["high_terminal"]["low_throughput"],
      "high_high":out["high_terminal"]["high_throughput"]
    },separators=(",",":")))

if __name__=="__main__": main()
