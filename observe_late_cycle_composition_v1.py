#!/usr/bin/env python3
"""Late cycle composition observer v1.

Desk coordinate: Remaining Time x Value Flow.
Use non-overlapping Day25-29 cycles and inspect the internal composition:
SELL target/value -> BUY target/cost -> cash retained after reinvestment.
Descriptive only; policy unchanged.
"""
import copy, json, statistics
from collections import Counter, defaultdict
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

OPPONENT=base.OPPONENT
def mean(xs): return statistics.mean(xs) if xs else None

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
        market=copy.deepcopy(obs.get("market",{}))
        bundle=agent.agent(obs)
        sells,buys,names=parse(bundle)
        trace.append({"turn":turn,"day":int(obs.get("day",0)),"money":money,
                      "market":market,"actions":copy.deepcopy(bundle),"sells":sells,"buys":buys,"names":names})
        turn+=1
        return bundle
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

        sell_est=0.0
        sell_items=[]
        prices=(srow.get("market") or {}).get("prices",{}) or {}
        for a in srow["sells"]:
            item=a[1] if len(a)>1 else None
            qty=float(a[2]) if len(a)>2 and isinstance(a[2],(int,float)) else 1.0
            price=prices.get(item)
            est=float(price)*qty if isinstance(price,(int,float)) else None
            if est is not None: sell_est+=est
            sell_items.append({"item":item,"qty":qty,"price":price,"estimated_gross":est})

        buy_items=[]
        if brow:
            bprices=(brow.get("market") or {}).get("prices",{}) or {}
            for a in brow["buys"]:
                buy_items.append({"action":a,"kind":a[0] if a else None,
                                  "item":a[1] if len(a)>1 else None,
                                  "market_price":bprices.get(a[1]) if len(a)>1 else None})

        cycles.append({
          "start_turn":i,"start_day":row["day"],"sell_turn":sell_i,"buy_turn":buy_i,"end_turn":end,
          "flow_turns":end-i,"money_start":row["money"],"money_at_sell":srow["money"],
          "money_after_reinvest":trace[end]["money"],"cash_retained":trace[end]["money"],
          "money_delta":trace[end]["money"]-row["money"],
          "sell_items":sell_items,"sell_estimated_gross":sell_est,
          "buy_items":buy_items,
          "throughput":(trace[end]["money"]-row["money"])/max(1,end-i)
        })
        i=end+1
    return {"seed":seed,"seat":seat,"terminal_self":terminal,"cycles":cycles}

def summarize(rows):
    cs=[c for r in rows for c in r["cycles"]]
    if not cs: return {"matches":len(rows),"cycles":0}
    ranked=sorted(cs,key=lambda c:c["throughput"])
    n=max(1,len(ranked)//3)
    low,high=ranked[:n],ranked[-n:]
    def band(xs):
        sell=Counter(); buy=Counter()
        for c in xs:
            for s in c["sell_items"]: sell[str(s["item"])]+=1
            for b in c["buy_items"]: buy[str(b["kind"])+":"+str(b["item"])]+=1
        return {
          "count":len(xs),
          "mean_throughput":mean([c["throughput"] for c in xs]),
          "mean_money_delta":mean([c["money_delta"] for c in xs]),
          "mean_sell_estimated_gross":mean([c["sell_estimated_gross"] for c in xs]),
          "mean_cash_retained":mean([c["cash_retained"] for c in xs]),
          "sell_items":sell.most_common(),
          "buy_items":buy.most_common(),
        }
    return {"all":band(cs),"low_throughput":band(low),"high_throughput":band(high),"cycles":cs}

def main():
    rows=[play(int(s),int(seat)) for s,seat in base.DEFAULT_CASES]
    ranked=sorted(rows,key=lambda r:r["terminal_self"]); n=min(4,max(1,len(ranked)//3))
    low_rows,high_rows=ranked[:n],ranked[-n:]
    out={"schema":"late-cycle-composition.v1","objective":"terminal self",
      "coordinate":"Remaining Time x Value Flow","window":"Day25-29",
      "cycle":"non-overlap DROP -> SELL -> next BUY_ if observed",
      "policy_mutated":False,"causal_attribution":False,
      "low_terminal":summarize(low_rows),"high_terminal":summarize(high_rows),
      "boundary":"sell_estimated_gross uses pre-action market price and may differ from realized sequential execution; cash_retained is state cash, not profit"}
    open("late_cycle_composition_v1.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("LATE_CYCLE_COMPOSITION_V1 "+json.dumps({
      "low_low":out["low_terminal"]["low_throughput"],
      "low_high":out["low_terminal"]["high_throughput"],
      "high_low":out["high_terminal"]["low_throughput"],
      "high_high":out["high_terminal"]["high_throughput"]
    },separators=(",",":")))

if __name__=="__main__": main()
