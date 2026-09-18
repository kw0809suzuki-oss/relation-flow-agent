#!/usr/bin/env python3
"""Late Value-Flow Entry Observer v1.

Start from the Desk coordinate, not a candidate control:
Remaining Time x Value Flow.  Reuse the Wave-v1 money trough definition, then
inspect the *actual baseline action bundle* at late troughs (Day25-29).

Descriptive only.  This observer does not mutate policy and does not assume BUY
is the flow entry.
"""
import copy, json, statistics
from collections import Counter, defaultdict
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

OPPONENT = base.OPPONENT


def mean(xs):
    return statistics.mean(xs) if xs else None


def action_names(bundle):
    out=[]
    if not isinstance(bundle,dict):
        return out
    farmer=bundle.get("farmer")
    if isinstance(farmer,(list,tuple)) and farmer:
        out.append("farmer:"+str(farmer[0]))
    for a in bundle.get("hands",[]) or []:
        if isinstance(a,(list,tuple)) and a:
            out.append("hands:"+str(a[0]))
    for a in bundle.get("market",[]) or []:
        if isinstance(a,(list,tuple)) and a:
            out.append("market:"+str(a[0]))
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
                      "actions":copy.deepcopy(bundle),"action_names":action_names(bundle)})
        turn+=1
        return bundle
    players=[OPPONENT,OPPONENT]; players[seat]=observed; env.run(players)
    terminal=float(env.state[seat].reward)

    pts=[]
    for x in trace:
        if not pts or x["money"] != pts[-1]["money"]: pts.append(x)
        else: pts[-1]=x

    late=[]
    for i in range(1,len(pts)-1):
        if pts[i]["money"] < pts[i-1]["money"] and pts[i]["money"] < pts[i+1]["money"]:
            trough=pts[i]
            if trough["day"] < 25: continue
            peak=None
            for j in range(i+1,len(pts)-1):
                if pts[j]["money"] > pts[j-1]["money"] and pts[j]["money"] > pts[j+1]["money"]:
                    peak=pts[j]; break
            if peak:
                late.append({"trough_turn":trough["turn"],"trough_day":trough["day"],
                  "trough_money":trough["money"],"entry_actions":trough["actions"],
                  "entry_action_names":trough["action_names"],"peak_turn":peak["turn"],
                  "peak_day":peak["day"],"peak_money":peak["money"],
                  "recovery_turns":peak["turn"]-trough["turn"],
                  "recovery_gain":peak["money"]-trough["money"]})
    return {"seed":seed,"seat":seat,"terminal_self":terminal,"late_waves":late}


def group_summary(rows):
    names=Counter(); slow=Counter(); gains=defaultdict(list); turns=defaultdict(list)
    waves=[w for r in rows for w in r["late_waves"]]
    for w in waves:
        key="+".join(w["entry_action_names"]) or "NO_ACTION"
        names[key]+=1; gains[key].append(w["recovery_gain"]); turns[key].append(w["recovery_turns"])
        if w["recovery_turns"] >= 2: slow[key]+=1
    return {"matches":len(rows),"wave_count":len(waves),
      "mean_recovery_turns":mean([w["recovery_turns"] for w in waves]),
      "mean_recovery_gain":mean([w["recovery_gain"] for w in waves]),
      "entry_patterns":[{"pattern":k,"count":n,"slow_ge2_count":slow[k],
        "mean_recovery_turns":mean(turns[k]),"mean_recovery_gain":mean(gains[k])}
        for k,n in names.most_common()]}


def main():
    rows=[play(int(seed),int(seat)) for seed,seat in base.DEFAULT_CASES]
    ranked=sorted(rows,key=lambda r:r["terminal_self"]); n=min(4,max(1,len(ranked)//3))
    low,high=ranked[:n],ranked[-n:]
    out={"schema":"late-value-flow-entry-observer.v1","objective":"terminal self",
      "coordinate":"Remaining Time x Value Flow",
      "question":"what actual baseline action bundle sits at Day25-29 money-wave troughs, especially slow recoveries?",
      "policy_mutated":False,"causal_attribution":False,
      "low_terminal":group_summary(low),"high_terminal":group_summary(high),
      "all_matches":rows}
    open("late_value_flow_entry_v1.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("LATE_VALUE_FLOW_ENTRY_V1 "+json.dumps({"low":out["low_terminal"],"high":out["high_terminal"]},separators=(",",":")))

if __name__=="__main__": main()
