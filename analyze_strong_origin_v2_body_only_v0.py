#!/usr/bin/env python3
"""Aggregate Strong Origin v2 Body-only v0 paired Battles."""
import json, statistics, sys
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/strong_origin_v2_body_only_pair_v0_*.json"))
if not files:
    raise SystemExit("No pair files")
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

out={
  "schema":"kaggriculture.strong-origin-v2.body-only.aggregate.v0",
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

  "candidate_d14_removed_orders_mean":mean([
      float((r["candidate"].get("telemetry") or {}).get("d14_removed_orders",0) or 0)
      for r in rows
  ]),

  "cases":rows,
  "boundary":[
    "Terminal self is primary authority.",
    "Candidate contains only the reconstructed body; no Catalog/Flow repair is added.",
    "If terminal self does not improve, do not explain it away by internal elegance."
  ]
}
Path("strong_origin_v2_body_only_v0_aggregate.json").write_text(
    json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
)
print("STRONG_ORIGIN_V2_BODY_ONLY_AGG "+json.dumps({
  k:v for k,v in out.items() if k!="cases"
},ensure_ascii=False,separators=(",",":")))
