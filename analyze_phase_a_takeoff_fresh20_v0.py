#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path

MODES=("surface_first","throughput_first","engine_first")
paths=sorted(Path(p) for p in glob.glob("phase-a-takeoff-artifacts/**/phase_a_takeoff_fresh20_v0_*.json",recursive=True))
if len(paths)!=20: raise SystemExit(f"Expected 20 cases, got {len(paths)}")
rows=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

def mean(xs): return sum(xs)/len(xs)
def med(xs): return statistics.median(xs)

def arm_summary(getter):
    selfv=[getter(r)["self"] for r in rows]
    opp=[getter(r)["opponent"] for r in rows]
    margin=[getter(r)["margin"] for r in rows]
    return {
      "absolute_mean_self":mean(selfv),
      "absolute_median_self":med(selfv),
      "absolute_mean_opponent":mean(opp),
      "absolute_mean_margin":mean(margin),
      "wins":sum(x>0 for x in margin),
      "min_self":min(selfv),"max_self":max(selfv),
    }

active=arm_summary(lambda r:r["active_wr02"]["terminal"])
cands={m:arm_summary(lambda r,m=m:r["candidates"][m]["terminal"]) for m in MODES}
paired={}
for m in MODES:
    ds=[r["paired_delta"][m]["self"] for r in rows]
    dm=[r["paired_delta"][m]["margin"] for r in rows]
    paired[m]={
      "baseline_absolute_mean_self":active["absolute_mean_self"],
      "candidate_absolute_mean_self":cands[m]["absolute_mean_self"],
      "mean_delta_self":mean(ds),
      "median_delta_self":med(ds),
      "mean_delta_margin":mean(dm),
      "improved_cases":sum(x>0 for x in ds),
      "worsened_cases":sum(x<0 for x in ds),
      "equal_cases":sum(x==0 for x in ds),
      "min_delta_self":min(ds),"max_delta_self":max(ds),
    }

cases=[]
for r in rows:
    cases.append({
      "seed":r["seed"],"seat":r["seat"],
      "active_wr02_self":r["active_wr02"]["terminal"]["self"],
      "candidate_self":{m:r["candidates"][m]["terminal"]["self"] for m in MODES},
      "delta_self":{m:r["paired_delta"][m]["self"] for m in MODES},
    })

payload={
  "schema":"kaggriculture.phase-a-takeoff.fresh20.result.v0",
  "battle_count":20,
  "active_wr02":active,
  "candidates":cands,
  "paired_vs_active_wr02":paired,
  "cases":cases,
  "boundary":[
    "Primary comparison is each Phase A pattern against the current Active Model WR-02.",
    "Every Bundle records baseline absolute mean self, candidate absolute mean self, and delta.",
    "No candidate is adopted from local behavior; terminal self decides.",
    "These are broad Phase A patterns, not claims that LAND, HIRE, or a specific crop is the unique causal mechanism."
  ]
}
Path("phase_a_takeoff_fresh20_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PHASE_A_TAKEOFF_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))
