#!/usr/bin/env python3
import json,sys
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/plant_conflict_transform_battle_v0_*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if not rows: raise SystemExit("no inputs")

def mean(xs):return sum(xs)/len(xs) if xs else None
def med(xs):
    y=sorted(xs);n=len(y)
    return y[n//2] if n%2 else (y[n//2-1]+y[n//2])/2

bself=[r["baseline"]["terminal"]["self"] for r in rows]
cself=[r["candidate"]["terminal"]["self"] for r in rows]
bopp=[r["baseline"]["terminal"]["opponent"] for r in rows]
copp=[r["candidate"]["terminal"]["opponent"] for r in rows]
dself=[r["delta"]["terminal_self"] for r in rows]
dmargin=[r["delta"]["terminal_margin"] for r in rows]

out={
  "schema":"kaggriculture.strong-origin-v2.plant-conflict-transform-battle.aggregate.v0",
  "battle_count":len(rows),
  "terminal":{
    "baseline_absolute_mean_self":mean(bself),
    "candidate_absolute_mean_self":mean(cself),
    "paired_delta_self":mean(dself),
    "baseline_absolute_mean_opponent":mean(bopp),
    "candidate_absolute_mean_opponent":mean(copp),
    "paired_delta_opponent":mean([c-b for b,c in zip(bopp,copp)]),
    "baseline_mean_margin":mean([r["baseline"]["terminal"]["margin"] for r in rows]),
    "candidate_mean_margin":mean([r["candidate"]["terminal"]["margin"] for r in rows]),
    "paired_delta_margin":mean(dmargin),
    "improved_cases":sum(x>0 for x in dself),
    "worsened_cases":sum(x<0 for x in dself),
    "equal_cases":sum(x==0 for x in dself),
    "median_delta_self":med(dself),
    "min_delta_self":min(dself),
    "max_delta_self":max(dself),
    "baseline_wins":sum(bool(r["baseline"]["terminal"]["win"]) for r in rows),
    "candidate_wins":sum(bool(r["candidate"]["terminal"]["win"]) for r in rows),
  },
  "diagnostic":{
    "modified_turns_mean":mean([r["candidate"]["telemetry"].get("modified_turns",0) for r in rows]),
    "conflict_groups_mean":mean([r["candidate"]["telemetry"].get("conflict_groups",0) for r in rows]),
    "projected_conflict_requests_mean":mean([r["candidate"]["telemetry"].get("projected_conflict_requests",0) for r in rows]),
    "suppressed_requests_mean":mean([r["candidate"]["telemetry"].get("suppressed_requests",0) for r in rows]),
    "day5_origin4_melon_delta_mean":mean([r["delta"]["day5_origin4_melon"] for r in rows]),
    "day5_origin4_wheat_delta_mean":mean([r["delta"]["day5_origin4_wheat"] for r in rows]),
    "day5_origin4_strawberry_delta_mean":mean([r["delta"]["day5_origin4_strawberry"] for r in rows]),
  },
  "cases":[
    {
      "seed":r["seed"],"seat":r["seat"],
      "baseline_self":r["baseline"]["terminal"]["self"],
      "candidate_self":r["candidate"]["terminal"]["self"],
      "delta_self":r["delta"]["terminal_self"],
      "delta_margin":r["delta"]["terminal_margin"],
      "origin4_delta":{
        "MELON":r["delta"]["day5_origin4_melon"],
        "WHEAT":r["delta"]["day5_origin4_wheat"],
        "STRAWBERRY":r["delta"]["day5_origin4_strawberry"],
      }
    } for r in rows
  ],
  "boundary":[
    "Terminal self is the adoption signal; transformation diagnostics are not adoption criteria.",
    "Candidate changes only Day4 same-empty-tile PLANT conflict arbitration after Body projection.",
    "No new action or target is generated.",
    "No automatic adoption."
  ]
}
Path("plant_conflict_transform_battle_v0_result.json").write_text(
    json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
)
print("PLANT_CONFLICT_TRANSFORM_AGG "+json.dumps({
    "battle_count":out["battle_count"],
    "terminal":out["terminal"],
    "diagnostic":out["diagnostic"],
    "cases":out["cases"],
},ensure_ascii=False,separators=(",",":")))
