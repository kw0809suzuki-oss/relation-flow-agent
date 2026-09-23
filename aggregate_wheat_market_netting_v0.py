#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/wheat_market_netting_v0_*.json",recursive=True)]
mean=lambda xs: statistics.mean(xs) if xs else None

payload={
 "schema":"kaggriculture.wheat-market-netting.aggregate.v0",
 "cases":len(rows),
 "baseline_absolute_mean_self":mean([r["baseline"]["self"] for r in rows]),
 "candidate_absolute_mean_self":mean([r["candidate"]["self"] for r in rows]),
 "delta":mean([r["delta_self"] for r in rows]),
 "baseline_absolute_mean_opponent":mean([r["baseline"]["opponent"] for r in rows]),
 "candidate_absolute_mean_opponent":mean([r["candidate"]["opponent"] for r in rows]),
 "mean_delta_margin":mean([r["delta_margin"] for r in rows]),
 "improve":sum(r["result"]=="improve" for r in rows),
 "worse":sum(r["result"]=="worse" for r in rows),
 "tie":sum(r["result"]=="tie" for r in rows),
 "modified_turns_total":sum(r["candidate"].get("telemetry",{}).get("modified_turns",0) for r in rows),
 "overlap_units_removed_total":sum(r["candidate"].get("telemetry",{}).get("overlap_units_removed",0) for r in rows),
 "per_seed":[{"seed":r["seed"],"seat":r["seat"],"baseline_self":r["baseline"]["self"],"candidate_self":r["candidate"]["self"],"delta_self":r["delta_self"],"result":r["result"],"modified_turns":r["candidate"].get("telemetry",{}).get("modified_turns",0),"overlap_units_removed":r["candidate"].get("telemetry",{}).get("overlap_units_removed",0)} for r in sorted(rows,key=lambda x:x["seed"])]
}
Path("wheat_market_netting_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
