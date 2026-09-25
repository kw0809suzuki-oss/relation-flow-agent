#!/usr/bin/env python3
import glob,json
from collections import Counter,defaultdict
from pathlib import Path

paths=sorted(Path(p) for p in glob.glob("phase-a-world-state-artifacts/**/phase_a_world_state_v0_*.json",recursive=True))
if len(paths)!=20: raise SystemExit(f"Expected 20 cases, got {len(paths)}")
states=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
battle=json.loads(Path("phase_a_takeoff_fresh20_v0_result.json").read_text(encoding="utf-8"))
battle_by_seed={int(r["seed"]):r for r in battle["cases"]}

def flatten(prefix,obj,out):
    if isinstance(obj,dict):
        for k,v in sorted(obj.items()):
            flatten(prefix+"."+str(k) if prefix else str(k),v,out)
    elif isinstance(obj,(int,float,bool)):
        out[prefix]=float(obj)

cases=[]
label_counts=Counter()
group=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))

for s in sorted(states,key=lambda x:int(x["seed"])):
    seed=int(s["seed"]);b=battle_by_seed[seed]
    vals={
      "hold":float(b["active_wr02_self"]),
      "surface_first":float(b["candidate_self"]["surface_first"]),
      "throughput_first":float(b["candidate_self"]["throughput_first"]),
      "engine_first":float(b["candidate_self"]["engine_first"]),
    }
    best=max(vals.values())
    winners=[k for k,v in vals.items() if v==best]
    winner=winners[0] if len(winners)==1 else "tie:"+"+".join(winners)
    label_counts[winner]+=1
    cps={}
    for day in ("4","8"):
        z=s["checkpoints"].get(day)
        cps[day]=z
        if z and len(winners)==1:
            flat={};flatten("",z,flat)
            for f,v in flat.items():
                if f in ("day","hour"):continue
                group[day][winner][f].append(v)
    cases.append({
      "seed":seed,"seat":s["seat"],"winner":winner,
      "terminal_self_by_direction":vals,
      "best_delta_vs_hold":best-vals["hold"],
      "checkpoints":cps,
    })

summary={}
for day,by_label in group.items():
    summary[day]={}
    for label,features in by_label.items():
        summary[day][label]={
          f:{"mean":sum(xs)/len(xs),"min":min(xs),"max":max(xs)}
          for f,xs in features.items()
        }

payload={
  "schema":"kaggriculture.phase-a-world-state-label-audit.result.v0",
  "battle_count":20,
  "label_counts":dict(label_counts),
  "group_summary":summary,
  "cases":cases,
  "boundary":[
    "Winning-direction labels come from already-observed terminal self.",
    "Features are observable World State only.",
    "No classifier, threshold, policy rule, or causal claim is introduced."
  ]
}
Path("phase_a_world_state_label_audit_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE_A_WORLD_STATE_LABEL_AUDIT "+json.dumps({"label_counts":payload["label_counts"]},ensure_ascii=False,separators=(",",":")))
