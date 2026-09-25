#!/usr/bin/env python3
import glob,json
from pathlib import Path

pred=json.loads(Path("phase_a_instruction_predictions_fresh10_v0.json").read_text(encoding="utf-8"))
paths=sorted(Path(p) for p in glob.glob("phase-a-instruction-outcome-artifacts/**/phase_a_takeoff_fresh20_v0_*.json",recursive=True))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
if len(rows)!=10: raise SystemExit(f"Expected 10 outcome cases, got {len(rows)}")

ARMS=("hold","surface_first","throughput_first","engine_first")

def terminals(r):
    return {
      "hold":float(r["active_wr02"]["terminal"]["self"]),
      "surface_first":float(r["candidates"]["surface_first"]["terminal"]["self"]),
      "throughput_first":float(r["candidates"]["throughput_first"]["terminal"]["self"]),
      "engine_first":float(r["candidates"]["engine_first"]["terminal"]["self"]),
    }

cases=[]
for r in sorted(rows,key=lambda x:x["seed"]):
    vals=terminals(r)
    best=max(vals.values())
    winners=sorted(k for k,v in vals.items() if v==best)
    cases.append({"seed":r["seed"],"seat":r["seat"],"terminal_self":vals,"oracle_best_self":best,"winners":winners})

scores={}
for vid,v in pred["variants"].items():
    picked=[]
    hits=0
    regrets=[]
    deltas_vs_hold=[]
    per_case=[]
    for c in cases:
        choice=v["predictions"][str(c["seed"])]
        val=c["terminal_self"][choice]
        regret=c["oracle_best_self"]-val
        hit=choice in c["winners"]
        hits+=int(hit)
        picked.append(val)
        regrets.append(regret)
        deltas_vs_hold.append(val-c["terminal_self"]["hold"])
        per_case.append({"seed":c["seed"],"choice":choice,"chosen_self":val,"winners":c["winners"],"oracle_best_self":c["oracle_best_self"],"regret":regret,"hit":hit})
    scores[vid]={
      "hits":hits,
      "accuracy":hits/len(cases),
      "mean_chosen_terminal_self":sum(picked)/len(picked),
      "mean_delta_vs_hold":sum(deltas_vs_hold)/len(deltas_vs_hold),
      "mean_terminal_regret":sum(regrets)/len(regrets),
      "median_terminal_regret":sorted(regrets)[len(regrets)//2-1:len(regrets)//2+1] if len(regrets)%2==0 else sorted(regrets)[len(regrets)//2],
      "max_terminal_regret":max(regrets),
      "cases":per_case,
    }

hold_mean=sum(c["terminal_self"]["hold"] for c in cases)/len(cases)
oracle_mean=sum(c["oracle_best_self"] for c in cases)/len(cases)

payload={
  "schema":"kaggriculture.phase-a-instruction-eval.fresh10.result.v0",
  "battle_count":len(cases),
  "hold_absolute_mean_self":hold_mean,
  "oracle_absolute_mean_self":oracle_mean,
  "oracle_delta_vs_hold":oracle_mean-hold_mean,
  "scores":scores,
  "cases":cases,
  "boundary":[
    "Predictions were committed before these four-arm outcome Battles were run.",
    "A prediction counts as a hit when its arm is tied for maximum terminal self.",
    "Terminal regret is oracle best self minus chosen arm self.",
    "This evaluates instruction-to-direction judgment on saved World State; it is not yet an online Battle policy adoption test."
  ]
}
Path("phase_a_instruction_eval_fresh10_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE_A_INSTRUCTION_EVAL "+json.dumps({
 "hold_mean":hold_mean,"oracle_mean":oracle_mean,
 "scores":{k:{x:v[x] for x in ("hits","accuracy","mean_chosen_terminal_self","mean_delta_vs_hold","mean_terminal_regret","max_terminal_regret")} for k,v in scores.items()}
},ensure_ascii=False,separators=(",",":")))
