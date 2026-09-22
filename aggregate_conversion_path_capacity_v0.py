#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("artifacts/**/conversion_path_capacity_v0_*.json",recursive=True)]
modes=["throughput_match","throughput_with_slack","conversion_window_fit"]
summary={}
for m in modes:
    vals=[r["hypotheses"][m]["terminal_self_diff"] for r in rows]
    margins=[r["hypotheses"][m]["terminal_margin_diff"] for r in rows]
    acts=[r["hypotheses"][m]["action_changed_turns"] for r in rows]
    summary[m]={
      "cases":len(vals),"improved":sum(v>0 for v in vals),"worsened":sum(v<0 for v in vals),"tied":sum(v==0 for v in vals),
      "mean_self_diff":statistics.mean(vals) if vals else None,"sum_self_diff":sum(vals),
      "mean_margin_diff":statistics.mean(margins) if margins else None,"sum_margin_diff":sum(margins),
      "action_changed_turns":sum(acts),
      "per_seed":[{"seed":r["seed"],"self_diff":r["hypotheses"][m]["terminal_self_diff"]} for r in rows]
    }
payload={"schema":"kaggriculture.conversion-path-capacity.aggregate.v0","cases":len(rows),"summary":summary,"abstraction_status":"hypothesis","next":"Re-abstract from structural differences; do not auto-adopt."}
Path("conversion_path_capacity_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
