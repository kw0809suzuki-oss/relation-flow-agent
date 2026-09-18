#!/usr/bin/env python3
"""Late slow-wave throughput observer v1.

Desk coordinate: Remaining Time x Value Flow.
Within Day25-29 waves with recovery >=2 turns, compare throughput
(recovery_gain/recovery_turns) and the actual entry action bundles.
Descriptive only; policy unchanged.
"""
import json, statistics
from collections import Counter, defaultdict
import observe_late_value_flow_entry_v1 as src

def mean(xs): return statistics.mean(xs) if xs else None

def summarize(waves):
    vals=[]
    for w in waves:
        t=w["recovery_turns"]
        if t>=2:
            x=dict(w); x["throughput"]=w["recovery_gain"]/t
            x["pattern"]="+".join(w["entry_action_names"]) or "NO_ACTION"
            vals.append(x)
    if not vals: return {"count":0}
    ranked=sorted(vals,key=lambda x:x["throughput"])
    n=max(1,len(ranked)//3)
    low,high=ranked[:n],ranked[-n:]
    def band(xs):
        pats=Counter(x["pattern"] for x in xs)
        action=Counter(a for x in xs for a in x["entry_action_names"])
        return {"count":len(xs),"mean_throughput":mean([x["throughput"] for x in xs]),
          "mean_gain":mean([x["recovery_gain"] for x in xs]),
          "mean_turns":mean([x["recovery_turns"] for x in xs]),
          "patterns":pats.most_common(),"actions":action.most_common()}
    return {"count":len(vals),"overall":band(vals),"low_throughput":band(low),
            "high_throughput":band(high),"waves":vals}

def main():
    rows=[src.play(int(seed),int(seat)) for seed,seat in src.base.DEFAULT_CASES]
    ranked=sorted(rows,key=lambda r:r["terminal_self"]); n=min(4,max(1,len(ranked)//3))
    low_rows,high_rows=ranked[:n],ranked[-n:]
    low=[w for r in low_rows for w in r["late_waves"]]
    high=[w for r in high_rows for w in r["late_waves"]]
    out={"schema":"late-slow-wave-throughput.v1","objective":"terminal self",
      "coordinate":"Remaining Time x Value Flow","filter":"trough day 25-29 and recovery_turns>=2",
      "throughput_definition":"recovery_gain/recovery_turns; descriptive cash throughput, not profit",
      "policy_mutated":False,"causal_attribution":False,
      "low_terminal":summarize(low),"high_terminal":summarize(high)}
    open("late_slow_wave_throughput_v1.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("LATE_SLOW_WAVE_THROUGHPUT_V1 "+json.dumps({
      "low":out["low_terminal"].get("overall"),"high":out["high_terminal"].get("overall"),
      "low_low":out["low_terminal"].get("low_throughput"),"low_high":out["low_terminal"].get("high_throughput"),
      "high_low":out["high_terminal"].get("low_throughput"),"high_high":out["high_terminal"].get("high_throughput")
    },separators=(",",":")))

if __name__=="__main__": main()
