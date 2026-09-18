#!/usr/bin/env python3
"""End-to-end Value Flow observer v1.

Observe one continuous game flow:
value formation / pickup -> placement(drop) -> liquidation(sell) -> reinvestment(buy)
and measure how quickly/largely it closes back into money.

Descriptive only. No policy mutation and no claim that action names are causes.
"""
import copy, json, statistics
from collections import Counter, defaultdict
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

OPPONENT = base.OPPONENT

def mean(xs): return statistics.mean(xs) if xs else None

def names(bundle):
    out=[]
    if not isinstance(bundle,dict): return out
    farmer=bundle.get("farmer")
    if isinstance(farmer,(list,tuple)) and farmer: out.append(str(farmer[0]))
    for sec in ("hands","market"):
        for a in bundle.get(sec,[]) or []:
            if isinstance(a,(list,tuple)) and a: out.append(str(a[0]))
    return out

def play(seed,seat):
    base._configure_baseline()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    trace=[]; turn=0
    def observed(obs):
        nonlocal turn
        p=int(obs["player"]); money=float(obs["farms"][p].get("money",0))
        bundle=agent.agent(obs)
        trace.append({"turn":turn,"day":int(obs.get("day",0)),"money":money,
                      "actions":copy.deepcopy(bundle),"names":names(bundle)})
        turn+=1
        return bundle
    players=[OPPONENT,OPPONENT]; players[seat]=observed; env.run(players)
    terminal=float(env.state[seat].reward)

    cycles=[]
    # anchor on DROP because prior observation shows it as a strong marker, then
    # inspect nearby formation, SELL, and first subsequent BUY without assuming causality.
    for i,row in enumerate(trace):
        if "DROP" not in row["names"]: continue
        j0=max(0,i-3); j1=min(len(trace),i+7)
        window=trace[j0:j1]
        sell_idx=next((k for k in range(i,min(len(trace),i+6)) if any(n.startswith("SELL") for n in trace[k]["names"])),None)
        buy_idx=None
        if sell_idx is not None:
            buy_idx=next((k for k in range(sell_idx+1,min(len(trace),sell_idx+7))
                          if any(n.startswith("BUY_") for n in trace[k]["names"])),None)
        if sell_idx is None: continue
        end=buy_idx if buy_idx is not None else sell_idx
        cycles.append({
            "drop_turn":i,"drop_day":row["day"],"sell_turn":sell_idx,
            "buy_turn":buy_idx,
            "closure_turns":end-i,
            "money_at_drop":row["money"],
            "money_at_sell":trace[sell_idx]["money"],
            "money_at_end":trace[end]["money"],
            "money_delta_drop_to_end":trace[end]["money"]-row["money"],
            "pre3_names":[x["names"] for x in trace[j0:i]],
            "drop_names":row["names"],
            "to_end_names":[x["names"] for x in trace[i:end+1]],
            "has_reinvestment":buy_idx is not None,
        })
    return {"seed":seed,"seat":seat,"terminal_self":terminal,"cycles":cycles}

def summarize(rows):
    cs=[c for r in rows for c in r["cycles"]]
    if not cs: return {"matches":len(rows),"cycles":0}
    reinv=[c for c in cs if c["has_reinvestment"]]
    fast=[c for c in cs if c["closure_turns"]<=3]
    return {
        "matches":len(rows),"cycles":len(cs),
        "mean_closure_turns":mean([c["closure_turns"] for c in cs]),
        "mean_money_delta":mean([c["money_delta_drop_to_end"] for c in cs]),
        "reinvestment_rate":sum(c["has_reinvestment"] for c in cs)/len(cs),
        "fast_close_rate":len(fast)/len(cs),
        "fast_mean_money_delta":mean([c["money_delta_drop_to_end"] for c in fast]),
        "reinvest_mean_closure_turns":mean([c["closure_turns"] for c in reinv]),
        "reinvest_mean_money_delta":mean([c["money_delta_drop_to_end"] for c in reinv]),
    }

def main():
    rows=[play(int(seed),int(seat)) for seed,seat in base.DEFAULT_CASES]
    ranked=sorted(rows,key=lambda r:r["terminal_self"]); n=min(4,max(1,len(ranked)//3))
    low,high=ranked[:n],ranked[-n:]
    out={
      "schema":"end-to-end-value-flow-observer.v1",
      "objective":"terminal self",
      "flow":"formation/pickup -> DROP placement -> SELL liquidation -> optional BUY reinvestment",
      "policy_mutated":False,"causal_attribution":False,
      "low_terminal":summarize(low),"high_terminal":summarize(high),
      "all_matches":rows,
      "boundary":"DROP is used only as an observed anchor marker; not assumed causal"
    }
    open("end_to_end_value_flow_v1.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("END_TO_END_VALUE_FLOW_V1 "+json.dumps({"low":out["low_terminal"],"high":out["high_terminal"]},separators=(",",":")))

if __name__=="__main__": main()
