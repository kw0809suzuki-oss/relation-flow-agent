#!/usr/bin/env python3
import glob,json,statistics,sys
from pathlib import Path

def mean(xs):return sum(xs)/len(xs) if xs else None
def median(xs):return statistics.median(xs) if xs else None

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/cow_pickup_reservation_probe_v0_*.json"))
if not files:
    files=[Path(p) for p in glob.glob(str(root/"**"/"cow_pickup_reservation_probe_v0_*.json"),recursive=True)]
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if not rows:raise SystemExit("No pair files")
rows.sort(key=lambda r:int(r["seed"]))

bs=[float(r["baseline"]["terminal"]["self"]) for r in rows]
cs=[float(r["candidate"]["terminal"]["self"]) for r in rows]
bm=[float(r["baseline"]["terminal"]["margin"]) for r in rows]
cm=[float(r["candidate"]["terminal"]["margin"]) for r in rows]
ds=[c-b for b,c in zip(bs,cs)]

def avg(side,path):
    vals=[]
    for r in rows:
        x=r[side]
        for k in path:x=x[k]
        vals.append(float(x))
    return mean(vals)

out={
 "schema":"kaggriculture.strong-origin-v2.cow-pickup-reservation-probe.fresh5.v0",
 "battle_count":len(rows),
 "baseline_absolute_mean_self":mean(bs),
 "candidate_absolute_mean_self":mean(cs),
 "delta_mean_self":mean(ds),
 "baseline_mean_margin":mean(bm),
 "candidate_mean_margin":mean(cm),
 "delta_mean_margin":mean([c-b for b,c in zip(bm,cm)]),
 "baseline_wins":sum(x>0 for x in bm),
 "candidate_wins":sum(x>0 for x in cm),
 "self_improved":sum(x>0 for x in ds),
 "self_worsened":sum(x<0 for x in ds),
 "median_delta_self":median(ds),
 "min_delta_self":min(ds),
 "max_delta_self":max(ds),
 "commitment":{
   "baseline_rate":avg("baseline",["commitment","commitment_rate"]),
   "candidate_rate":avg("candidate",["commitment","commitment_rate"]),
   "baseline_idle_capital":avg("baseline",["commitment","day4_idle_capital"]),
   "candidate_idle_capital":avg("candidate",["commitment","day4_idle_capital"]),
 },
 "day4":{
   "baseline_assets":avg("baseline",["day4","productive_assets"]),
   "candidate_assets":avg("candidate",["day4","productive_assets"]),
   "baseline_potential":avg("baseline",["day4","production_potential_mark"]),
   "candidate_potential":avg("candidate",["day4","production_potential_mark"]),
 },
 "day8":{
   "baseline_assets":avg("baseline",["day8","productive_assets"]),
   "candidate_assets":avg("candidate",["day8","productive_assets"]),
   "baseline_potential":avg("baseline",["day8","production_potential_mark"]),
   "candidate_potential":avg("candidate",["day8","production_potential_mark"]),
 },
 "cases":rows,
 "boundary":[
   "Whole terminal effect remains primary.",
   "Commitment metrics test whether removing impossible duplicate COW pickup work improves allocation-to-commitment conversion.",
   "No post-hoc rescue condition is added."
 ]
}
Path("cow_pickup_reservation_probe_v0_fresh5.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("COW_PICKUP_RESERVATION_FRESH5 "+json.dumps({k:v for k,v in out.items() if k!="cases"},ensure_ascii=False,separators=(",",":")))
