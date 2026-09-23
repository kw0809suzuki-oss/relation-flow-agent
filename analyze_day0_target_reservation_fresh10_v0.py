#!/usr/bin/env python3
import json,statistics,sys
from pathlib import Path

def mean(xs):return sum(xs)/len(xs) if xs else None
def median(xs):return statistics.median(xs) if xs else None

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("day0_target_reservation_pair_*.json"))
if not files:files=sorted(root.glob("**/day0_target_reservation_pair_*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]

bs=[r["baseline"]["self"] for r in rows];cs=[r["candidate"]["self"] for r in rows]
bo=[r["baseline"]["opponent"] for r in rows];co=[r["candidate"]["opponent"] for r in rows]
bm=[r["baseline"]["margin"] for r in rows];cm=[r["candidate"]["margin"] for r in rows]
ds=[r["delta_self"] for r in rows];dm=[r["delta_margin"] for r in rows]

out={
 "schema":"kaggriculture.day0-target-reservation.fresh10.v0",
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
 "self_improved":sum(x>0 for x in ds),"self_worsened":sum(x<0 for x in ds),"self_equal":sum(x==0 for x in ds),
 "margin_improved":sum(x>0 for x in dm),"margin_worsened":sum(x<0 for x in dm),"margin_equal":sum(x==0 for x in dm),
 "baseline_wins":sum(x>0 for x in bm),"candidate_wins":sum(x>0 for x in cm),
 "baseline_day0_collision_mean":mean([r["baseline"]["day0_plant_collision"] for r in rows]),
 "candidate_day0_collision_mean":mean([r["candidate"]["day0_plant_collision"] for r in rows]),
 "baseline_day1_melon_mean":mean([r["baseline"]["day1_melon_planted"] for r in rows]),
 "candidate_day1_melon_mean":mean([r["candidate"]["day1_melon_planted"] for r in rows]),
 "median_delta_self":median(ds),"min_delta_self":min(ds),"max_delta_self":max(ds),
 "median_delta_margin":median(dm),"min_delta_margin":min(dm),"max_delta_margin":max(dm),
 "cases":rows,
 "boundary":["Terminal result remains adoption authority.","Behavior checks only verify the candidate touched the observed mechanism.","No rescue condition is added after this paired run."]
}
Path("day0_target_reservation_fresh10_v0.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("DAY0_TARGET_RESERVATION_FRESH10 "+json.dumps({k:v for k,v in out.items() if k!="cases"},ensure_ascii=False,separators=(",",":")))
