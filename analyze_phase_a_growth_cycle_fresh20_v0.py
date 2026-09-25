#!/usr/bin/env python3
import glob,json,statistics
from collections import Counter
from pathlib import Path

paths=sorted(Path(p) for p in glob.glob("phase-a-growth-cycle-artifacts/**/phase_a_growth_cycle_fresh20_v0_*.json",recursive=True))
if len(paths)!=20: raise SystemExit(f"Expected 20 cases, got {len(paths)}")
rows=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

def mean(xs):return sum(xs)/len(xs)
def med(xs):return statistics.median(xs)

bs=[r["active_wr02"]["terminal"]["self"] for r in rows]
cs=[r["cycle"]["terminal"]["self"] for r in rows]
bm=[r["active_wr02"]["terminal"]["margin"] for r in rows]
cm=[r["cycle"]["terminal"]["margin"] for r in rows]
bo=[r["active_wr02"]["terminal"]["opponent"] for r in rows]
co=[r["cycle"]["terminal"]["opponent"] for r in rows]
ds=[r["paired_delta"]["self"] for r in rows]
dm=[r["paired_delta"]["margin"] for r in rows]

stage_turns=Counter()
transition_reasons=Counter()
for r in rows:
    stage_turns.update(r["cycle"]["telemetry"].get("stage_turns",{}))
    for t in r["cycle"]["telemetry"].get("transitions",[]):
        transition_reasons[t.get("reason","unknown")]+=1

payload={
  "schema":"kaggriculture.phase-a-growth-cycle.fresh20.result.v0",
  "battle_count":20,
  "active_wr02":{
    "absolute_mean_self":mean(bs),"absolute_median_self":med(bs),
    "absolute_mean_opponent":mean(bo),"absolute_mean_margin":mean(bm),
    "wins":sum(x>0 for x in bm),"min_self":min(bs),"max_self":max(bs),
  },
  "cycle":{
    "absolute_mean_self":mean(cs),"absolute_median_self":med(cs),
    "absolute_mean_opponent":mean(co),"absolute_mean_margin":mean(cm),
    "wins":sum(x>0 for x in cm),"min_self":min(cs),"max_self":max(cs),
  },
  "paired":{
    "baseline_absolute_mean_self":mean(bs),
    "candidate_absolute_mean_self":mean(cs),
    "mean_delta_self":mean(ds),
    "median_delta_self":med(ds),
    "mean_delta_margin":mean(dm),
    "improved_cases":sum(x>0 for x in ds),
    "worsened_cases":sum(x<0 for x in ds),
    "equal_cases":sum(x==0 for x in ds),
    "min_delta_self":min(ds),"max_delta_self":max(ds),
  },
  "stage_turns":dict(stage_turns),
  "transition_reasons":dict(transition_reasons),
  "cases":[{
    "seed":r["seed"],"seat":r["seat"],
    "active_wr02_self":r["active_wr02"]["terminal"]["self"],
    "cycle_self":r["cycle"]["terminal"]["self"],
    "delta_self":r["paired_delta"]["self"],
    "stage_turns":r["cycle"]["telemetry"].get("stage_turns",{}),
    "transitions":r["cycle"]["telemetry"].get("transitions",[]),
  } for r in rows],
  "boundary":[
    "Terminal self is the adoption gate.",
    "Stage telemetry is descriptive only.",
    "A non-positive result closes this Growth Cycle v0, not the Phase A objective."
  ]
}
Path("phase_a_growth_cycle_fresh20_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE_A_GROWTH_CYCLE_RESULT "+json.dumps({
  "active":payload["active_wr02"],"cycle":payload["cycle"],
  "paired":payload["paired"],"stage_turns":payload["stage_turns"],
  "transition_reasons":payload["transition_reasons"]
},ensure_ascii=False,separators=(",",":")))
