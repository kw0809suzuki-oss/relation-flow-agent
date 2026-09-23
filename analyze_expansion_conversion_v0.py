#!/usr/bin/env python3
"""Aggregate paired Expansion Conversion Model v0 Battles."""
import json, statistics, sys
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/expansion_conversion_pair_v0_*.json"))
if not files:
    raise SystemExit("No expansion conversion pair files")
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
rows.sort(key=lambda r:int(r["seed"]))

bs=[float(r["baseline"]["self"]) for r in rows]
cs=[float(r["candidate"]["self"]) for r in rows]
bo=[float(r["baseline"]["opponent"]) for r in rows]
co=[float(r["candidate"]["opponent"]) for r in rows]
bm=[float(r["baseline"]["margin"]) for r in rows]
cm=[float(r["candidate"]["margin"]) for r in rows]
ds=[float(r["delta_self"]) for r in rows]
dm=[float(r["delta_margin"]) for r in rows]

def metric(side, path):
    vals=[]
    for r in rows:
        cur=r[side]
        for key in path:
            cur=(cur or {}).get(key)
        vals.append(float(cur or 0))
    return mean(vals)

out={
  "schema":"kaggriculture.expansion-conversion.aggregate.v0",
  "battle_count":len(rows),

  "baseline_absolute_mean_self":mean(bs),
  "candidate_absolute_mean_self":mean(cs),
  "delta_mean_self":mean(ds),

  "baseline_absolute_mean_opponent":mean(bo),
  "candidate_absolute_mean_opponent":mean(co),
  "delta_mean_opponent":mean([c-b for b,c in zip(bo,co)]),

  "baseline_mean_margin":mean(bm),
  "candidate_mean_margin":mean(cm),
  "delta_mean_margin":mean(dm),

  "baseline_wins":sum(x>0 for x in bm),
  "candidate_wins":sum(x>0 for x in cm),
  "self_improved":sum(x>0 for x in ds),
  "self_worsened":sum(x<0 for x in ds),
  "self_equal":sum(x==0 for x in ds),

  "median_delta_self":median(ds),
  "min_delta_self":min(ds),
  "max_delta_self":max(ds),

  "post_land_behavior":{
    "baseline":{
      "duplicate_plant_loss_mean":metric("baseline",["post_land_plant","same_turn_target_became_nonempty"]),
      "plant_success_mean":metric("baseline",["post_land_plant","success_unit_phase"]),
      "new_crops_mean":metric("baseline",["post_land_flow","new_crops"]),
      "occupied_delta_mean":metric("baseline",["post_land_flow","occupied_delta"]),
      "committed_delta_mean":metric("baseline",["post_land_flow","committed_delta"]),
      "cash_delta_mean":metric("baseline",["post_land_flow","cash_delta"]),
    },
    "candidate":{
      "duplicate_plant_loss_mean":metric("candidate",["post_land_plant","same_turn_target_became_nonempty"]),
      "plant_success_mean":metric("candidate",["post_land_plant","success_unit_phase"]),
      "new_crops_mean":metric("candidate",["post_land_flow","new_crops"]),
      "occupied_delta_mean":metric("candidate",["post_land_flow","occupied_delta"]),
      "committed_delta_mean":metric("candidate",["post_land_flow","committed_delta"]),
      "cash_delta_mean":metric("candidate",["post_land_flow","cash_delta"]),
    },
  },
  "cases":rows,
  "boundary":[
    "Terminal self/margin/wins are adoption authority.",
    "Behavior metrics only verify whether post-Expansion capacity conversion changed.",
    "No rescue condition is added after this paired run."
  ]
}
Path("expansion_conversion_v0_aggregate.json").write_text(
    json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
)
compact={k:v for k,v in out.items() if k!="cases"}
print("EXPANSION_CONVERSION_AGG "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))
