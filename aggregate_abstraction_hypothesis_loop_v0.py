#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in sorted(glob.glob("artifacts/**/abstraction_hypothesis_loop_v0_*.json",recursive=True))]
modes=["seed_surface","hire_workload","land_activation"]
summary={}
for mode in modes:
    vals=[r["hypotheses"][mode]["terminal_self_diff"] for r in rows]
    margins=[r["hypotheses"][mode]["terminal_margin_diff"] for r in rows]
    acts=[r["hypotheses"][mode]["action_changed_turns"] for r in rows]
    summary[mode]={
        "cases":len(vals),
        "improved":sum(v>0 for v in vals),
        "worsened":sum(v<0 for v in vals),
        "tied":sum(v==0 for v in vals),
        "mean_self_diff":statistics.mean(vals) if vals else None,
        "sum_self_diff":sum(vals),
        "mean_margin_diff":statistics.mean(margins) if margins else None,
        "sum_margin_diff":sum(margins),
        "action_changed_turns":sum(acts),
        "per_seed":[{"seed":r["seed"],"self_diff":r["hypotheses"][mode]["terminal_self_diff"]} for r in rows]
    }
payload={
    "schema":"kaggriculture.abstraction-hypothesis-loop.aggregate.v0",
    "cases":len(rows),
    "summary":summary,
    "next_step":"Return observed structural differences to Flow-chan for re-abstraction. Do not auto-adopt.",
    "abstraction_status":"hypothesis"
}
Path("abstraction_hypothesis_loop_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
