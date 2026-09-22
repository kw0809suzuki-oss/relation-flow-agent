#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path

rows=[]
for path in sorted(glob.glob("artifacts/**/abstraction_interpretation_bundle_v0_*.json",recursive=True)):
    rows.append(json.loads(Path(path).read_text(encoding="utf-8")))

modes=["capacity_aligned","alternative_affordability","staged_commitment"]
summary={}
for mode in modes:
    vals=[r["interpretations"][mode]["terminal_self_diff_vs_control"] for r in rows]
    margins=[r["interpretations"][mode]["terminal_margin_diff_vs_control"] for r in rows]
    acts=[r["interpretations"][mode]["action_changed_turns"] for r in rows]
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
        "per_seed_self_diff":[{"seed":r["seed"],"diff":r["interpretations"][mode]["terminal_self_diff_vs_control"]} for r in rows],
    }

payload={
    "schema":"kaggriculture.abstraction-interpretation-bundle.aggregate.v0",
    "cases":len(rows),
    "summary":summary,
    "interpretation_policy":"No automatic winner. Battle evidence is returned for re-entry."
}
Path("abstraction_interpretation_bundle_v0_aggregate.json").write_text(
    json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
)
print(json.dumps(payload,ensure_ascii=False))
