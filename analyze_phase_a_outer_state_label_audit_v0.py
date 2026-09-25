#!/usr/bin/env python3
import glob,json
from collections import Counter,defaultdict
from pathlib import Path

paths=sorted(Path(p) for p in glob.glob("phase-a-outer-state-artifacts/**/phase_a_outer_state_v0_*.json",recursive=True))
if len(paths)!=20: raise SystemExit(f"Expected 20 outer-State cases, got {len(paths)}")
states=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

battle=json.loads(Path("phase_a_takeoff_fresh20_v0_result.json").read_text(encoding="utf-8"))
battle_by_seed={int(r["seed"]):r for r in battle["cases"]}

FEATURES=(
  "cash","quadrants","unlocked_tiles","empty_tiles","productive_tiles",
  "plants","animals","workers","productive_occupancy","productive_per_worker",
  "seed_total",
)
LABELS=("hold","surface_first","throughput_first","engine_first")


def mean(xs): return sum(xs)/len(xs) if xs else None


cases=[]
label_counts=Counter()
group=defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

for s in sorted(states,key=lambda x:int(x["seed"])):
    seed=int(s["seed"])
    b=battle_by_seed[seed]
    values={
      "hold":float(b["active_wr02_self"]),
      "surface_first":float(b["candidate_self"]["surface_first"]),
      "throughput_first":float(b["candidate_self"]["throughput_first"]),
      "engine_first":float(b["candidate_self"]["engine_first"]),
    }
    best=max(values.values())
    winners=[k for k,v in values.items() if v==best]
    winner=winners[0] if len(winners)==1 else "tie:"+"+".join(winners)
    label_counts[winner]+=1

    cps={}
    for day in ("0","4","8"):
        z=s["checkpoints"].get(day)
        cps[day]=z
        if z and len(winners)==1:
            for f in FEATURES:
                group[day][winner][f].append(float(z[f]))

    cases.append({
      "seed":seed,
      "seat":s["seat"],
      "winner":winner,
      "terminal_self_by_direction":values,
      "best_delta_vs_hold":best-values["hold"],
      "checkpoints":cps,
    })

group_summary={}
for day,by_label in group.items():
    group_summary[day]={}
    for label,by_feature in by_label.items():
        group_summary[day][label]={
          "n":sum(1 for c in cases if c["winner"]==label and c["checkpoints"].get(day)),
          "features":{
            f:{
              "mean":mean(xs),
              "min":min(xs) if xs else None,
              "max":max(xs) if xs else None,
            } for f,xs in by_feature.items()
        }}

payload={
  "schema":"kaggriculture.phase-a-outer-state-label-audit.result.v0",
  "battle_count":20,
  "label_counts":dict(label_counts),
  "features":list(FEATURES),
  "group_summary":group_summary,
  "cases":cases,
  "boundary":[
    "Labels come only from already-observed terminal self in the four-arm Phase A Battle.",
    "Features come only from WR-02 self-visible outer State at Day0 / Day4 / Day8.",
    "No classifier, threshold, policy rule, or causal claim is introduced here.",
    "This audit asks only whether terminal-winning directions visibly occupy different outer-State regions."
  ]
}
Path("phase_a_outer_state_label_audit_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE_A_OUTER_STATE_LABEL_AUDIT "+json.dumps({
  "label_counts":payload["label_counts"],
  "group_summary":payload["group_summary"]
},ensure_ascii=False,separators=(",",":")))
