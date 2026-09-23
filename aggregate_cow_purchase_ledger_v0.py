#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
rows=[json.loads(Path(p).read_text()) for p in glob.glob("artifacts/**/cow_purchase_ledger_v0_*.json",recursive=True)]
turns=[t for r in rows for t in r.get("cow_purchase_turns",[])]
mean=lambda xs: statistics.mean(xs) if xs else None
payload={
 "schema":"kaggriculture.cow-purchase-ledger.aggregate.v0","cases":len(rows),"cow_purchase_turns":len(turns),
 "cow_units":sum(t["cow_buy_units"] for t in turns),
 "mean_residual_excluding_cow":mean([t["residual_excluding_cow"] for t in turns]),
 "mean_residual_plus_400_per_cow":mean([t["residual_plus_400_per_cow"] for t in turns]),
 "mean_abs_residual_excluding_cow":mean([abs(t["residual_excluding_cow"]) for t in turns]),
 "mean_abs_residual_plus_400_per_cow":mean([abs(t["residual_plus_400_per_cow"]) for t in turns]),
 "scale_check":{"baseline_absolute_mean_self":mean([r["terminal"]["self"] for r in rows]),"opponent_absolute_mean_self":mean([r["terminal"]["opponent"] for r in rows]),"mean_terminal_residual":mean([r["terminal"]["residual"] for r in rows]),"candidate_absolute_mean_self":None,"delta":None},
 "per_turn":turns,
 "boundary":"400 comes from current g8_agent ANIMAL_COST; this tests ledger closure, not COW settlement causality."
}
Path("cow_purchase_ledger_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(payload,ensure_ascii=False))
