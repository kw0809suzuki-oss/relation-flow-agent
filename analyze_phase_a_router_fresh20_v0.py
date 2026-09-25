#!/usr/bin/env python3
import glob,json,statistics
from collections import Counter
from pathlib import Path

paths=sorted(Path(p) for p in glob.glob("phase-a-router-artifacts/**/phase_a_router_fresh20_v0_*.json",recursive=True))
if len(paths)!=20: raise SystemExit(f"Expected 20 cases, got {len(paths)}")
rows=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

def mean(xs): return sum(xs)/len(xs)
def med(xs): return statistics.median(xs)

bself=[r["active_wr02"]["terminal"]["self"] for r in rows]
cself=[r["router"]["terminal"]["self"] for r in rows]
bopp=[r["active_wr02"]["terminal"]["opponent"] for r in rows]
copp=[r["router"]["terminal"]["opponent"] for r in rows]
bmargin=[r["active_wr02"]["terminal"]["margin"] for r in rows]
cmargin=[r["router"]["terminal"]["margin"] for r in rows]
ds=[r["paired_delta"]["self"] for r in rows]
dm=[r["paired_delta"]["margin"] for r in rows]

mode_days=Counter()
for r in rows:
    mode_days.update(r["router"]["telemetry"].get("mode_days",{}))

payload={
  "schema":"kaggriculture.phase-a-router.fresh20.result.v0",
  "battle_count":20,
  "active_wr02":{
    "absolute_mean_self":mean(bself),
    "absolute_median_self":med(bself),
    "absolute_mean_opponent":mean(bopp),
    "absolute_mean_margin":mean(bmargin),
    "wins":sum(x>0 for x in bmargin),
    "min_self":min(bself),"max_self":max(bself),
  },
  "router":{
    "absolute_mean_self":mean(cself),
    "absolute_median_self":med(cself),
    "absolute_mean_opponent":mean(copp),
    "absolute_mean_margin":mean(cmargin),
    "wins":sum(x>0 for x in cmargin),
    "min_self":min(cself),"max_self":max(cself),
  },
  "paired":{
    "baseline_absolute_mean_self":mean(bself),
    "candidate_absolute_mean_self":mean(cself),
    "mean_delta_self":mean(ds),
    "median_delta_self":med(ds),
    "mean_delta_margin":mean(dm),
    "improved_cases":sum(x>0 for x in ds),
    "worsened_cases":sum(x<0 for x in ds),
    "equal_cases":sum(x==0 for x in ds),
    "min_delta_self":min(ds),"max_delta_self":max(ds),
  },
  "router_mode_days":dict(mode_days),
  "cases":[{
    "seed":r["seed"],"seat":r["seat"],
    "active_wr02_self":r["active_wr02"]["terminal"]["self"],
    "router_self":r["router"]["terminal"]["self"],
    "delta_self":r["paired_delta"]["self"],
    "mode_days":r["router"]["telemetry"].get("mode_days",{}),
  } for r in rows],
  "boundary":[
    "Adoption is decided by terminal self, not routing frequency.",
    "Router mode counts are reference telemetry only.",
    "A non-positive result does not prove State-routing impossible; it closes only this Router v0."
  ]
}
Path("phase_a_router_fresh20_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE_A_ROUTER_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))
