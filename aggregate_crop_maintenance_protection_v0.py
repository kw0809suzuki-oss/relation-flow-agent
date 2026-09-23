#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/crop_maintenance_protection_v0_*.json",recursive=True)]

def mean(xs): return statistics.mean(xs) if xs else None
curr=[r["current"]["terminal"]["self"] for r in rows]
cand=[r["candidate"]["terminal"]["self"] for r in rows]
opp=[r["current"]["terminal"]["opponent"] for r in rows]
deltas=[r["delta_self"] for r in rows]

def daymean(arm,day,key):
    vals=[]
    for r in rows:
        x=r[arm].get("day_end",{}).get(str(day))
        if x is None: x=r[arm].get("day_end",{}).get(day)
        if x is not None and key in x: vals.append(x[key])
    return mean(vals)

days={}
for d in [5,7,10,12,15,20,26]:
    days[str(d)]={
      "current_crop_tiles":daymean("current",d,"crop_tiles"),
      "candidate_crop_tiles":daymean("candidate",d,"crop_tiles"),
      "current_production_tiles":daymean("current",d,"production_tiles"),
      "candidate_production_tiles":daymean("candidate",d,"production_tiles"),
      "current_money":daymean("current",d,"money"),
      "candidate_money":daymean("candidate",d,"money")
    }

prot=[]
for r in rows:
    cp=(r["candidate"].get("telemetry",{}) or {}).get("crop_protection",{}) or {}
    prot.append(cp)

payload={
 "schema":"kaggriculture.crop-maintenance-protection.aggregate.v0",
 "cases":len(rows),
 "scale_check":{
   "baseline_absolute_mean_self":mean(curr),
   "candidate_absolute_mean_self":mean(cand),
   "delta":mean(cand)-mean(curr) if curr and cand else None,
   "opponent_absolute_mean_self":mean(opp),
   "baseline_mean_terminal_residual":mean([r["current"]["terminal"]["residual"] for r in rows])
 },
 "outcomes":{
   "improved":sum(x>0 for x in deltas),
   "worse":sum(x<0 for x in deltas),
   "tied":sum(x==0 for x in deltas),
   "mean_delta_self":mean(deltas),
   "mean_delta_margin":mean([r["delta_margin"] for r in rows])
 },
 "protection":{
   "eligible_slots":sum(x.get("eligible_slots",0) for x in prot),
   "protected_slots":sum(x.get("protected_slots",0) for x in prot),
   "protected_water":sum(x.get("protected_water",0) for x in prot),
   "protected_plant":sum(x.get("protected_plant",0) for x in prot),
   "protected_harvest":sum(x.get("protected_harvest",0) for x in prot)
 },
 "day_means":days,
 "per_seed":[
   {"seed":r["seed"],"current":r["current"]["terminal"]["self"],"candidate":r["candidate"]["terminal"]["self"],"delta":r["delta_self"]}
   for r in sorted(rows,key=lambda x:x["seed"])
 ]
}
Path("crop_maintenance_protection_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
