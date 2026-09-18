#!/usr/bin/env python3
"""Cash Flow Wave Observer v1.

Observe money itself as a wave. No action-name cycle assumptions.
A local trough is a candidate capital-deployment point; the following local peak
is a candidate recovery point. These are descriptive money-state transitions,
not causal profit attribution.
"""
import json, statistics
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

OPPONENT=base.OPPONENT

def mean(xs): return statistics.mean(xs) if xs else None

def play(seed,seat):
    base._configure_baseline()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    trace=[]; turn=0
    def observed(obs):
        nonlocal turn
        p=int(obs["player"]); m=float(obs["farms"][p].get("money",0))
        trace.append({"turn":turn,"day":int(obs.get("day",0)),"money":m})
        turn+=1
        return agent.agent(obs)
    players=[OPPONENT,OPPONENT]; players[seat]=observed; env.run(players)
    reward=float(env.state[seat].reward)

    # Compress equal-money plateaus so zero deltas do not manufacture extrema.
    pts=[]
    for x in trace:
        if not pts or x["money"] != pts[-1]["money"]: pts.append(x)
        else: pts[-1]=x

    waves=[]
    for i in range(1,len(pts)-1):
        if pts[i]["money"] < pts[i-1]["money"] and pts[i]["money"] < pts[i+1]["money"]:
            trough=pts[i]
            peak=None
            for j in range(i+1,len(pts)-1):
                if pts[j]["money"] > pts[j-1]["money"] and pts[j]["money"] > pts[j+1]["money"]:
                    peak=pts[j]; break
            if peak:
                waves.append({"trough_turn":trough["turn"],"trough_day":trough["day"],
                  "trough_money":trough["money"],"peak_turn":peak["turn"],"peak_day":peak["day"],
                  "peak_money":peak["money"],"recovery_turns":peak["turn"]-trough["turn"],
                  "recovery_gain":peak["money"]-trough["money"]})
    return {"seed":seed,"seat":seat,"terminal_self":reward,"waves":waves,
      "wave_count":len(waves),"mean_recovery_turns":mean([w["recovery_turns"] for w in waves]),
      "mean_recovery_gain":mean([w["recovery_gain"] for w in waves])}

def summarize(rows):
    return {"matches":len(rows),"mean_terminal":mean([r["terminal_self"] for r in rows]),
      "mean_wave_count":mean([r["wave_count"] for r in rows]),
      "mean_recovery_turns":mean([r["mean_recovery_turns"] for r in rows if r["mean_recovery_turns"] is not None]),
      "mean_recovery_gain":mean([r["mean_recovery_gain"] for r in rows if r["mean_recovery_gain"] is not None])}

def main():
    rows=[play(int(seed),int(seat)) for seed,seat in base.DEFAULT_CASES]
    ranked=sorted(rows,key=lambda r:r["terminal_self"]); n=min(4,max(1,len(ranked)//3))
    low,high=ranked[:n],ranked[-n:]
    ls,hs=summarize(low),summarize(high)
    out={"schema":"cash-flow-wave-observer.v1","objective":"terminal self",
      "definition":"money trough -> next money peak; descriptive capital deployment/recovery candidate only",
      "all_matches":rows,"low_terminal":ls,"high_terminal":hs,
      "comparison":{"high_minus_low_wave_count":hs["mean_wave_count"]-ls["mean_wave_count"],
        "high_minus_low_recovery_turns":hs["mean_recovery_turns"]-ls["mean_recovery_turns"],
        "high_minus_low_recovery_gain":hs["mean_recovery_gain"]-ls["mean_recovery_gain"]}}
    with open("cash_flow_wave_observer_v1.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2); f.write("\n")
    print("CASH_FLOW_WAVE_V1 "+json.dumps({"low":ls,"high":hs,"comparison":out["comparison"]},separators=(",",":")))
if __name__=="__main__": main()
