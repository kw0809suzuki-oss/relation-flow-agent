#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
from collections import defaultdict,Counter

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/output_revenue_monetization_v0_*.json",recursive=True)]

def mean(xs): return statistics.mean(xs) if xs else None
byday=defaultdict(list)
for r in rows:
    for d in r.get("days",[]): byday[d["day"]].append(d)

day_summary=[]
for day in sorted(byday):
    xs=byday[day]
    day_summary.append({
      "day":day,"n":len(xs),
      "mean_self_money_start":mean([x["self_money_start"] for x in xs]),
      "mean_self_money_end":mean([x["self_money_end"] for x in xs]),
      "mean_self_money_delta":mean([x["self_money_delta"] for x in xs]),
      "mean_opp_money_start":mean([x["opp_money_start"] for x in xs]),
      "mean_opp_money_end":mean([x["opp_money_end"] for x in xs]),
      "mean_opp_money_delta":mean([x["opp_money_delta"] for x in xs]),
      "mean_harvest_actions":mean([x["harvest_actions"] for x in xs]),
      "mean_gross_sell_face_value":mean([x["gross_sell_face_value"] for x in xs]),
      "mean_sold_units_total":mean([x["sold_units_total"] for x in xs]),
      "mean_materialized_units_proxy_total":mean([x["materialized_units_proxy_total"] for x in xs])
    })

item_totals=Counter()
item_sales=Counter()
for r in rows:
    for d in r.get("days",[]):
        for item,v in d.get("items",{}).items():
            item_totals[item]+=v.get("materialized_units_proxy",0)
            item_sales[item]+=v.get("sold_units",0)

payload={
 "schema":"kaggriculture.output-revenue-monetization.aggregate.v0",
 "cases":len(rows),
 "scale_check":{
   "baseline_absolute_mean_self":mean([r["terminal"]["self"] for r in rows]),
   "opponent_absolute_mean_self":mean([r["terminal"]["opponent"] for r in rows]),
   "mean_terminal_residual":mean([r["terminal"]["residual"] for r in rows]),
   "candidate_absolute_mean_self":None,
   "delta":None
 },
 "day_summary":day_summary,
 "item_materialized_proxy_totals":dict(item_totals),
 "item_sold_unit_totals":dict(item_sales),
 "boundary":"Output/revenue observation only; no causal attribution and no opponent-private stock."
}
Path("output_revenue_monetization_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cases":len(rows),"scale_check":payload["scale_check"],"days":day_summary},ensure_ascii=False))
