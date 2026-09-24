#!/usr/bin/env python3
"""Aggregate Minimal SHEEP Lane Probe v0 fresh5."""
import glob,json,statistics,sys
from collections import Counter
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/minimal_sheep_lane_probe_v0_*.json"))
if not files:
    files=[Path(p) for p in glob.glob(str(root/"**"/"minimal_sheep_lane_probe_v0_*.json"),recursive=True)]
if not files:
    raise SystemExit("No Minimal SHEEP probe files")

rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
rows.sort(key=lambda r:int(r["seed"]))

bs=[float(r["baseline"]["terminal"]["self"]) for r in rows]
cs=[float(r["candidate"]["terminal"]["self"]) for r in rows]
bo=[float(r["baseline"]["terminal"]["opponent"]) for r in rows]
co=[float(r["candidate"]["terminal"]["opponent"]) for r in rows]
bm=[float(r["baseline"]["terminal"]["margin"]) for r in rows]
cm=[float(r["candidate"]["terminal"]["margin"]) for r in rows]
ds=[c-b for b,c in zip(bs,cs)]
dm=[c-b for b,c in zip(bm,cm)]

def state_mean(side,day,key):
    vals=[]
    for r in rows:
        v=r[side][day][key]
        vals.append(float(v))
    return mean(vals)

def comp_mean(side,day,section):
    keys=set()
    for r in rows:
        keys.update(r[side][day][section].keys())
    return {k:mean([float(r[side][day][section].get(k,0) or 0) for r in rows]) for k in sorted(keys)}

def bridge_mean(side,key):
    return mean([float(r[side]["day4_to_day8"][key]) for r in rows])

out={
 "schema":"kaggriculture.strong-origin-v2.minimal-sheep-lane-probe.fresh5.v0",
 "battle_count":len(rows),
 "baseline_absolute_mean_self":mean(bs),
 "candidate_absolute_mean_self":mean(cs),
 "delta_mean_self":mean(ds),
 "baseline_absolute_mean_opponent":mean(bo),
 "candidate_absolute_mean_opponent":mean(co),
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
 "day4":{
   "baseline_crop":comp_mean("baseline","day4","crop_count"),
   "candidate_crop":comp_mean("candidate","day4","crop_count"),
   "baseline_animal":comp_mean("baseline","day4","animal_count"),
   "candidate_animal":comp_mean("candidate","day4","animal_count"),
   "baseline_cash":state_mean("baseline","day4","cash"),
   "candidate_cash":state_mean("candidate","day4","cash"),
   "baseline_assets":state_mean("baseline","day4","productive_assets"),
   "candidate_assets":state_mean("candidate","day4","productive_assets"),
   "baseline_potential":state_mean("baseline","day4","production_potential_mark"),
   "candidate_potential":state_mean("candidate","day4","production_potential_mark")
 },
 "day4_to_day8":{
   "baseline_non_wheat_sell":bridge_mean("baseline","non_wheat_sell"),
   "candidate_non_wheat_sell":bridge_mean("candidate","non_wheat_sell"),
   "delta_non_wheat_sell":mean([float(r["delta"]["day4_to_day8_non_wheat_sell"]) for r in rows]),
   "baseline_surplus":bridge_mean("baseline","surplus_after_operating"),
   "candidate_surplus":bridge_mean("candidate","surplus_after_operating"),
   "delta_surplus":mean([float(r["delta"]["day4_to_day8_surplus"]) for r in rows]),
   "baseline_productive_spend":bridge_mean("baseline","productive_spend"),
   "candidate_productive_spend":bridge_mean("candidate","productive_spend"),
   "delta_productive_spend":mean([float(r["delta"]["day4_to_day8_productive_spend"]) for r in rows]),
 },
 "day8":{
   "baseline_assets":state_mean("baseline","day8","productive_assets"),
   "candidate_assets":state_mean("candidate","day8","productive_assets"),
   "delta_assets":mean([float(r["delta"]["day8_productive_assets"]) for r in rows]),
   "baseline_potential":state_mean("baseline","day8","production_potential_mark"),
   "candidate_potential":state_mean("candidate","day8","production_potential_mark"),
   "delta_potential":mean([float(r["delta"]["day8_production_potential"]) for r in rows]),
   "baseline_land_quadrants":state_mean("baseline","day8","land_quadrants"),
   "candidate_land_quadrants":state_mean("candidate","day8","land_quadrants"),
   "delta_land_quadrants":mean([float(r["delta"]["day8_land_quadrants"]) for r in rows]),
 },
 "cases":rows,
 "boundary":[
   "Primary authority is whole terminal effect; local bridge metrics are explanatory observations only.",
   "The probe tests trajectory/composition sensitivity, not whether SHEEP is intrinsically good.",
   "No rescue condition is added after this fresh5.",
   "A large single-seed effect is not generalized unless it persists across fresh cases."
 ]
}
Path("minimal_sheep_lane_probe_v0_fresh5.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("MINIMAL_SHEEP_LANE_FRESH5 "+json.dumps({k:v for k,v in out.items() if k!="cases"},ensure_ascii=False,separators=(",",":")))
