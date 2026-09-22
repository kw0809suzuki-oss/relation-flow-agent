#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("artifacts/**/coarse_boundary_hysteresis_v0_*.json",recursive=True)]
sd=[r["hysteresis_vs_coarse"]["self_diff"] for r in rows]
md=[r["hysteresis_vs_coarse"]["margin_diff"] for r in rows]
bd=[r["hysteresis_vs_coarse"]["boundary_change_diff"] for r in rows]
payload={
 "schema":"kaggriculture.coarse-boundary-hysteresis.aggregate.v0",
 "cases":len(rows),
 "hysteresis_vs_coarse":{
   "improved":sum(v>0 for v in sd),
   "worsened":sum(v<0 for v in sd),
   "tied":sum(v==0 for v in sd),
   "mean_self_diff":statistics.mean(sd) if sd else None,
   "sum_self_diff":sum(sd),
   "mean_margin_diff":statistics.mean(md) if md else None,
   "sum_margin_diff":sum(md),
   "mean_boundary_change_diff":statistics.mean(bd) if bd else None,
   "sum_boundary_change_diff":sum(bd),
   "per_seed":[{"seed":r["seed"],**r["hysteresis_vs_coarse"]} for r in rows]
 },
 "hypothesis_status":"working_hypothesis"
}
Path("coarse_boundary_hysteresis_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
