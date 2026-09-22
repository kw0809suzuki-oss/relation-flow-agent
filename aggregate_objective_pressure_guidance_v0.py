#!/usr/bin/env python3
import glob,json,statistics
from collections import Counter
from pathlib import Path
rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("artifacts/**/objective_pressure_guidance_v0_*.json",recursive=True)]
summary={}
for arm in ["fixed_match","previous_guided","objective_pressure"]:
    vals=[r[arm]["terminal_self_diff"] for r in rows]
    margins=[r[arm]["terminal_margin_diff"] for r in rows]
    choices=Counter(); reasons=Counter()
    for r in rows:
        choices.update(r[arm].get("choice_counts",{})); reasons.update(r[arm].get("reason_counts",{}))
    summary[arm]={
        "cases":len(vals),
        "improved":sum(v>0 for v in vals),
        "worsened":sum(v<0 for v in vals),
        "tied":sum(v==0 for v in vals),
        "mean_self_diff":statistics.mean(vals) if vals else None,
        "sum_self_diff":sum(vals),
        "mean_margin_diff":statistics.mean(margins) if margins else None,
        "sum_margin_diff":sum(margins),
        "action_changed_turns":sum(r[arm]["action_changed_turns"] for r in rows),
        "choice_counts":dict(choices),
        "reason_counts":dict(reasons),
        "per_seed":[{"seed":r["seed"],"self_diff":r[arm]["terminal_self_diff"],"margin_diff":r[arm]["terminal_margin_diff"]} for r in rows]
    }
payload={"schema":"kaggriculture.objective-pressure-guidance.aggregate.v0","cases":len(rows),"summary":summary,"abstraction_status":"hypothesis","boundary":"Flow-chan suggests a lens; Model-side proxy decides how to use it."}
Path("objective_pressure_guidance_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
