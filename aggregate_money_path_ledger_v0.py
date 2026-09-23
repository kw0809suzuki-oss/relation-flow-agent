#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
from collections import defaultdict

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/money_path_ledger_v0_*.json",recursive=True)]

def mean(xs): return statistics.mean(xs) if xs else None
byday=defaultdict(list)
for r in rows:
    for d in r.get("days",[]): byday[d["day"]].append(d)

day_summary=[]
for day in sorted(byday):
    xs=byday[day]
    day_summary.append({
      "day":day,"n":len(xs),
      "mean_money_start":mean([x["money_start"] for x in xs]),
      "mean_money_end":mean([x["money_end"] for x in xs]),
      "mean_money_delta":mean([x["money_delta"] for x in xs]),
      "mean_sell_face_value":mean([x["sell_face_value"] for x in xs]),
      "mean_priced_buy_face_value":mean([x["priced_buy_face_value"] for x in xs]),
      "mean_hire_count":mean([x["hire_count"] for x in xs]),
      "mean_buy_land_count":mean([x["buy_land_count"] for x in xs]),
      "mean_requested_sell_units":mean([x["requested_sell_units"] for x in xs]),
      "mean_observed_release_proxy_units":mean([x["observed_release_proxy_units"] for x in xs]),
      "mean_turn_money_residual_sum":mean([x["turn_money_residual_sum"] for x in xs])
    })

payload={
 "schema":"kaggriculture.money-path-ledger.aggregate.v0",
 "cases":len(rows),
 "scale_check":{
   "baseline_absolute_mean_self":mean([r["terminal"]["self"] for r in rows]),
   "opponent_absolute_mean_self":mean([r["terminal"]["opponent"] for r in rows]),
   "mean_terminal_residual":mean([r["terminal"]["residual"] for r in rows]),
   "candidate_absolute_mean_self":None,
   "delta":None
 },
 "day_summary":day_summary,
 "boundary":"Turn-level money reconciliation with stock-release proxy; no causal attribution."
}
Path("money_path_ledger_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
