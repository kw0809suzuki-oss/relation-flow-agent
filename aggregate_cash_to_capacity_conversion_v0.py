#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
from collections import defaultdict

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/cash_to_capacity_conversion_v0_*.json",recursive=True)]

def mean(xs): return statistics.mean(xs) if xs else None

byday=defaultdict(list)
for r in rows:
    for d in r.get("days",[]): byday[d["day"]].append(d)

day_summary=[]
for day in sorted(byday):
    xs=byday[day]
    rec={"day":day,"n":len(xs)}
    for side in ["self","opponent"]:
        for k in ["money","hands","land","crop_tiles","animal_tiles","production_tiles"]:
            rec[f"mean_{side}_{k}"]=mean([x.get(f"{side}_state",{}).get(k) for x in xs if x.get(f"{side}_state",{}).get(k) is not None])
    for k in ["HIRE","BUY_LAND","BUY_ANIMAL","BUY_SEED","BUY_PRODUCT","SELL"]:
        rec[f"mean_self_action_{k}"]=mean([x.get("self_actions",{}).get(k,0) for x in xs])
    for side in ["self","opponent"]:
        for k in ["money","hands","land","crop_tiles","animal_tiles","production_tiles"]:
            field=f"{side}_change_from_prior_day"
            rec[f"mean_{side}_daily_delta_{k}"]=mean([x.get(field,{}).get(k) for x in xs if x.get(field,{}).get(k) is not None])
    day_summary.append(rec)

selfs=[r["terminal"]["self"] for r in rows]
opps=[r["terminal"]["opponent"] for r in rows]
resids=[r["terminal"]["residual"] for r in rows]

# Coarse growth summaries over day5->12 using day means.
dmap={x["day"]:x for x in day_summary}
growth={}
if 5 in dmap and 12 in dmap:
    for side in ["self","opponent"]:
        for k in ["money","hands","land","production_tiles"]:
            growth[f"{side}_{k}_day5_to_12"]=dmap[12][f"mean_{side}_{k}"]-dmap[5][f"mean_{side}_{k}"]

payload={
 "schema":"kaggriculture.cash-to-capacity-conversion.aggregate.v0",
 "cases":len(rows),
 "scale_check":{
   "baseline_absolute_mean_self":mean(selfs),
   "opponent_absolute_mean_self":mean(opps),
   "mean_terminal_residual":mean(resids),
   "candidate_absolute_mean_self":None,
   "delta":None
 },
 "growth_day5_to_12":growth,
 "day_summary":day_summary,
 "boundary":"Conversion/retention observation only; no causal attribution."
}
Path("cash_to_capacity_conversion_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cases":len(rows),"scale_check":payload["scale_check"],"growth":growth},ensure_ascii=False))
