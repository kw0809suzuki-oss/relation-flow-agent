#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

paths=sorted(Path(p) for p in glob.glob("wr03-fresh20-artifacts/**/wr03_fresh20_v0_*.json",recursive=True))
if len(paths)!=20: raise SystemExit(f"Expected 20 artifacts, found {len(paths)}")
rows=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
arms=("body","wr02","wr03","bundle")
out={"schema":"kaggriculture.wr03.fresh20.result.v0","battle_count":20,"arms":{}}
for arm in arms:
    sv=[r["results"][arm]["terminal"]["self"] for r in rows]
    ov=[r["results"][arm]["terminal"]["opponent"] for r in rows]
    mg=[r["results"][arm]["terminal"]["margin"] for r in rows]
    out["arms"][arm]={
      "absolute_mean_self":mean(sv),
      "absolute_median_self":median(sv),
      "absolute_mean_opponent":mean(ov),
      "absolute_mean_margin":mean(mg),
      "wins":sum(x>0 for x in mg),
      "min_self":min(sv),"max_self":max(sv),
    }

def paired(a,b):
    ds=[r["results"][a]["terminal"]["self"]-r["results"][b]["terminal"]["self"] for r in rows]
    dm=[r["results"][a]["terminal"]["margin"]-r["results"][b]["terminal"]["margin"] for r in rows]
    return {
      "mean_delta_self":mean(ds),"median_delta_self":median(ds),
      "mean_delta_margin":mean(dm),
      "improved_cases":sum(x>0 for x in ds),
      "worsened_cases":sum(x<0 for x in ds),
      "equal_cases":sum(x==0 for x in ds),
      "min_delta_self":min(ds),"max_delta_self":max(ds),
    }

out["paired"]={
  "wr02_vs_body":paired("wr02","body"),
  "wr03_vs_body":paired("wr03","body"),
  "bundle_vs_body":paired("bundle","body"),
  "bundle_vs_wr02":paired("bundle","wr02"),
  "bundle_vs_wr03":paired("bundle","wr03"),
}
out["wr03_connection"]={
 "standalone_return_signals":sum(r["results"]["wr03"]["telemetry"].get("wr03_return_signals",0) for r in rows),
 "standalone_active_turns":sum(r["results"]["wr03"]["telemetry"].get("wr03_active_turns",0) for r in rows),
 "standalone_surface_closures":sum(r["results"]["wr03"]["telemetry"].get("wr03_surface_closures",0) for r in rows),
 "bundle_return_signals":sum(r["results"]["bundle"]["telemetry"].get("wr03",{}).get("wr03_return_signals",0) for r in rows),
 "bundle_active_turns":sum(r["results"]["bundle"]["telemetry"].get("wr03",{}).get("wr03_active_turns",0) for r in rows),
 "bundle_surface_closures":sum(r["results"]["bundle"]["telemetry"].get("wr03",{}).get("wr03_surface_closures",0) for r in rows),
}
out["cases"]=[{
 "seed":r["seed"],"seat":r["seat"],
 "self":{a:r["results"][a]["terminal"]["self"] for a in arms},
 "bundle_vs_wr02":r["results"]["bundle"]["terminal"]["self"]-r["results"]["wr02"]["terminal"]["self"],
} for r in rows]
out["boundary"]=[
 "Primary adoption comparison is WR-02 versus WR-02+WR-03.",
 "All arms are paired on identical fresh seed/seat cases.",
 "Report absolute mean self for every arm and paired deltas; do not infer adoption from local telemetry alone."
]
Path("wr03_fresh20_v0_result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("WR03_FRESH20_RESULT "+json.dumps(out,ensure_ascii=False,separators=(",",":")))
