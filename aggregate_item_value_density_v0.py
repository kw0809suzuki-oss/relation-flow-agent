#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
from collections import defaultdict

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/item_value_density_v0_*.json",recursive=True)]

def mean(xs): return statistics.mean(xs) if xs else None

items=defaultdict(lambda:{"sell_units":[],"sell_face":[],"stock_start":[],"stock_end":[],"materialized":[]})
days=defaultdict(list)
for r in rows:
    for d in r.get("days",[]):
        days[d["day"]].append(d)
        for item,v in d["items"].items():
            items[item]["sell_units"].append(v["sell_units"])
            items[item]["sell_face"].append(v["sell_face_value"])
            items[item]["stock_start"].append(v["stock_start"])
            items[item]["stock_end"].append(v["stock_end"])
            items[item]["materialized"].append(v["materialized_units_proxy"])

item_summary={}
total_units=sum(sum(v["sell_units"]) for v in items.values())
total_face=sum(sum(v["sell_face"]) for v in items.values())
for item,v in sorted(items.items()):
    su=sum(v["sell_units"]); sf=sum(v["sell_face"])
    item_summary[item]={
      "total_sell_units":su,
      "total_sell_face_value":sf,
      "overall_sell_value_per_unit":(sf/su if su else None),
      "overall_sell_units_share":(su/total_units if total_units else 0.0),
      "overall_sell_value_share":(sf/total_face if total_face else 0.0),
      "mean_daily_stock_start":mean(v["stock_start"]),
      "mean_daily_stock_end":mean(v["stock_end"]),
      "mean_daily_materialized_units_proxy":mean(v["materialized"])
    }

day_summary=[]
for day in sorted(days):
    xs=days[day]
    day_summary.append({
      "day":day,
      "mean_total_sell_units":mean([x["total_sell_units"] for x in xs]),
      "mean_total_sell_face_value":mean([x["total_sell_face_value"] for x in xs])
    })

payload={
 "schema":"kaggriculture.item-value-density.aggregate.v0",
 "cases":len(rows),
 "scale_check":{
   "baseline_absolute_mean_self":mean([r["terminal"]["self"] for r in rows]),
   "opponent_absolute_mean_self":mean([r["terminal"]["opponent"] for r in rows]),
   "mean_terminal_residual":mean([r["terminal"]["residual"] for r in rows]),
   "candidate_absolute_mean_self":None,
   "delta":None
 },
 "item_summary":item_summary,
 "day_summary":day_summary,
 "boundary":"Separates sell mix from stock/materialization availability; no policy conclusion."
}
Path("item_value_density_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cases":len(rows),"scale_check":payload["scale_check"],"item_summary":item_summary},ensure_ascii=False))
