#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
from collections import defaultdict

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/wheat_market_overlap_v0_*.json",recursive=True)]

def mean(xs): return statistics.mean(xs) if xs else None
turns=[t for r in rows for t in r.get("turns",[])]
days=defaultdict(list)
for r in rows:
    for d in r.get("days",[]): days[d["day"]].append(d)

overlap=[t for t in turns if t.get("same_turn_overlap")]
opp=[t for t in turns if t.get("overlay_opposite_surface")]

payload={
 "schema":"kaggriculture.wheat-market-overlap.aggregate.v0",
 "cases":len(rows),
 "scale_check":{
   "baseline_absolute_mean_self":mean([r["terminal"]["self"] for r in rows]),
   "opponent_absolute_mean_self":mean([r["terminal"]["opponent"] for r in rows]),
   "mean_terminal_residual":mean([r["terminal"]["residual"] for r in rows]),
   "candidate_absolute_mean_self":None,
   "delta":None
 },
 "wheat_market_turns":len(turns),
 "same_turn_overlap_turns":len(overlap),
 "same_turn_overlap_share":len(overlap)/len(turns) if turns else None,
 "overlay_opposite_surface_turns":len(opp),
 "total_sell_units":sum(t["final_sell_units"] for t in turns),
 "total_buy_product_units":sum(t["final_buy_product_units"] for t in turns),
 "total_overlap_units":sum(t["overlap_units"] for t in turns),
 "overlap_units_share_of_sell":sum(t["overlap_units"] for t in turns)/sum(t["final_sell_units"] for t in turns) if sum(t["final_sell_units"] for t in turns) else None,
 "overlap_units_share_of_buy":sum(t["overlap_units"] for t in turns)/sum(t["final_buy_product_units"] for t in turns) if sum(t["final_buy_product_units"] for t in turns) else None,
 "mean_money_delta_overlap_turn":mean([t["money_delta"] for t in overlap]),
 "mean_money_delta_nonoverlap_wheat_turn":mean([t["money_delta"] for t in turns if not t.get("same_turn_overlap")]),
 "day_summary":[{
   "day":d,
   "mean_sell_units":mean([x["sell_units"] for x in xs]),
   "mean_buy_product_units":mean([x["buy_product_units"] for x in xs]),
   "mean_overlap_units":mean([x["overlap_units"] for x in xs]),
   "mean_same_turn_overlap_turns":mean([x["same_turn_overlap_turns"] for x in xs]),
   "mean_overlay_opposite_surface_turns":mean([x["overlay_opposite_surface_turns"] for x in xs]),
   "mean_money_delta_sum":mean([x["money_delta_sum"] for x in xs])
 } for d,xs in sorted(days.items())],
 "boundary":"Action-surface overlap only; no settlement-loss conclusion."
}
Path("wheat_market_overlap_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
