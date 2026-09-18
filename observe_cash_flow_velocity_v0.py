#!/usr/bin/env python3
"""Cash Flow Velocity Observer v0.

Descriptive observer only. It does not optimize velocity and does not change the
agent. For baseline cases it links SELL-containing decisions to the next
investment decision and the next later SELL-containing decision, then compares
closed-cycle timing by terminal-score group.

A "cycle" here is only an observed action sequence:
SELL -> next BUY/HIRE/BUY_LAND/BUY_ANIMAL -> next SELL.
It is not asserted to be a causal capital cycle or profit attribution.
"""
import json, re, statistics
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

OPPONENT=base.OPPONENT
SELL_RE=re.compile(r"SELL\s+([A-Z_]+)\s+(\d+)")
INVEST_WORDS=("BUY_PRODUCT","BUY_SEED","BUY_LAND","BUY_ANIMAL","HIRE")

def action_text(a):
    if isinstance(a,str): return a
    try: return json.dumps(a,ensure_ascii=False,sort_keys=True)
    except TypeError: return repr(a)

def has_sell(s): return bool(SELL_RE.search(s))
def has_invest(s): return any(x in s for x in INVEST_WORDS)

def play(seed,seat):
    base._configure_baseline(); env=make("kaggriculture",configuration={"seed":seed},debug=False)
    trace=[]; turn=0
    def observed(obs):
        nonlocal turn
        p=int(obs["player"]); money=float(obs["farms"][p].get("money",0)); a=agent.agent(obs); s=action_text(a)
        trace.append({"turn":turn,"day":int(obs.get("day",0)),"money":money,"action":s,
                      "sell":has_sell(s),"invest":has_invest(s)})
        turn+=1; return a
    players=[OPPONENT,OPPONENT]; players[seat]=observed; env.run(players)
    reward=float(env.state[seat].reward)
    cycles=[]
    sell_idxs=[i for i,x in enumerate(trace) if x["sell"]]
    for pos,i in enumerate(sell_idxs[:-1]):
        j=next((k for k in range(i+1,len(trace)) if trace[k]["invest"]),None)
        if j is None: continue
        k=next((q for q in sell_idxs[pos+1:] if q>j),None)
        if k is None: continue
        cycles.append({
          "sell1_turn":i,"sell1_day":trace[i]["day"],"invest_turn":j,"sell2_turn":k,
          "turns_sell_to_invest":j-i,"turns_invest_to_sell":k-j,"turns_sell_to_sell":k-i,
          "money_sell1":trace[i]["money"],"money_sell2":trace[k]["money"],
          "observed_money_change":trace[k]["money"]-trace[i]["money"],
          "sell1_action":trace[i]["action"],"invest_action":trace[j]["action"],"sell2_action":trace[k]["action"]
        })
    return {"seed":seed,"seat":seat,"terminal_self":reward,"cycles":cycles,
            "closed_cycles":len(cycles)}

def mean(xs):
    return statistics.mean(xs) if xs else None

def summarize(rows):
    cs=[c for r in rows for c in r["cycles"]]
    return {"matches":len(rows),"mean_terminal":mean([r["terminal_self"] for r in rows]),
      "mean_closed_cycles":mean([r["closed_cycles"] for r in rows]),
      "mean_turns_sell_to_invest":mean([c["turns_sell_to_invest"] for c in cs]),
      "mean_turns_invest_to_sell":mean([c["turns_invest_to_sell"] for c in cs]),
      "mean_turns_sell_to_sell":mean([c["turns_sell_to_sell"] for c in cs]),
      "mean_observed_money_change":mean([c["observed_money_change"] for c in cs]),
      "cycle_count":len(cs)}

def main():
    cases=list(base.DEFAULT_CASES)
    rows=[play(int(seed),int(seat)) for seed,seat in cases]
    ranked=sorted(rows,key=lambda r:r["terminal_self"])
    n=min(4,max(1,len(ranked)//3))
    low=ranked[:n]; high=ranked[-n:]
    out={"schema":"cash-flow-velocity-observer.v0","objective":"terminal self",
      "definition":"descriptive SELL -> next investment -> next SELL action timing; not causal profit attribution",
      "all_matches":rows,"low_terminal":summarize(low),"high_terminal":summarize(high),
      "comparison":{"high_minus_low_closed_cycles":summarize(high)["mean_closed_cycles"]-summarize(low)["mean_closed_cycles"],
        "high_minus_low_sell_to_sell_turns":None if summarize(high)["mean_turns_sell_to_sell"] is None or summarize(low)["mean_turns_sell_to_sell"] is None else summarize(high)["mean_turns_sell_to_sell"]-summarize(low)["mean_turns_sell_to_sell"]}}
    with open("cash_flow_velocity_observer_v0.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2); f.write("\n")
    print("CASH_FLOW_VELOCITY_V0 "+json.dumps({"low":out["low_terminal"],"high":out["high_terminal"],"comparison":out["comparison"]},separators=(",",":")))
if __name__=="__main__": main()
