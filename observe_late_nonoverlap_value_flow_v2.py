#!/usr/bin/env python3
"""Late non-overlapping end-to-end Value Flow observer v2.

Desk coordinate: Remaining Time x Value Flow.
Restrict to Day25-29 and extract non-overlapping observed sequences:
DROP -> next SELL -> next BUY_ (optional), advancing past the accepted sequence.
This avoids manufacturing many overlapping cycles from repeated DROP events.

Descriptive only; policy unchanged; action names are markers, not causes.
"""
import copy, json, statistics
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

OPPONENT=base.OPPONENT
def mean(xs): return statistics.mean(xs) if xs else None

def names(bundle):
    out=[]
    if not isinstance(bundle,dict): return out
    f=bundle.get("farmer")
    if isinstance(f,(list,tuple)) and f: out.append(str(f[0]))
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
        b=agent.agent(obs)
        trace.append({"turn":turn,"day":int(obs.get("day",0)),"money":money,
                      "names":names(b),"actions":copy.deepcopy(b)})
        turn+=1
        return b
    players=[OPPONENT,OPPONENT]; players[seat]=observed; env.run(players)
    terminal=float(env.state[seat].reward)

    cycles=[]; i=0
    while i < len(trace):
        row=trace[i]
        if row["day"]<25 or "DROP" not in row["names"]:
            i+=1; continue
        sell=next((j for j in range(i,min(len(trace),i+7))
                   if "SELL" in trace[j]["names"]),None)
        if sell is None:
            i+=1; continue
        buy=next((j for j in range(sell+1,min(len(trace),sell+7))
                  if any(n.startswith("BUY_") for n in trace[j]["names"])),None)
        end=buy if buy is not None else sell
        pre=max(0,i-3)
        cycles.append({
          "start_turn":i,"start_day":row["day"],"sell_turn":sell,"buy_turn":buy,
          "end_turn":end,"flow_turns":end-i,
          "money_start":row["money"],"money_end":trace[end]["money"],
          "money_delta":trace[end]["money"]-row["money"],
          "pre3_names":[x["names"] for x in trace[pre:i]],
          "flow_names":[x["names"] for x in trace[i:end+1]],
          "reinvested":buy is not None})
        i=end+1
    return {"seed":seed,"seat":seat,"terminal_self":terminal,"cycles":cycles}

def summary(rows):
    cs=[c for r in rows for c in r["cycles"]]
    if not cs: return {"matches":len(rows),"cycles":0}
    return {"matches":len(rows),"cycles":len(cs),
      "mean_flow_turns":mean([c["flow_turns"] for c in cs]),
      "mean_money_delta":mean([c["money_delta"] for c in cs]),
      "positive_rate":sum(c["money_delta"]>0 for c in cs)/len(cs),
      "reinvestment_rate":sum(c["reinvested"] for c in cs)/len(cs),
      "fast_close_rate":sum(c["flow_turns"]<=3 for c in cs)/len(cs),
      "throughput":mean([c["money_delta"]/max(1,c["flow_turns"]) for c in cs])}

def main():
    rows=[play(int(s),int(seat)) for s,seat in base.DEFAULT_CASES]
    ranked=sorted(rows,key=lambda r:r["terminal_self"]); n=min(4,max(1,len(ranked)//3))
    low,high=ranked[:n],ranked[-n:]
    out={"schema":"late-nonoverlap-value-flow.v2","objective":"terminal self",
      "coordinate":"Remaining Time x Value Flow","window":"Day25-29",
      "flow":"DROP -> next SELL -> next BUY_ if observed",
      "non_overlapping":True,"policy_mutated":False,"causal_attribution":False,
      "low_terminal":summary(low),"high_terminal":summary(high),"all_matches":rows,
      "boundary":"money_delta is observed cash movement across the sequence, not profit/value attribution"}
    open("late_nonoverlap_value_flow_v2.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("LATE_NONOVERLAP_VALUE_FLOW_V2 "+json.dumps({"low":out["low_terminal"],"high":out["high_terminal"]},separators=(",",":")))

if __name__=="__main__": main()
