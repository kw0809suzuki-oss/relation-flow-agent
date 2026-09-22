#!/usr/bin/env python3
import glob,json,statistics
from collections import Counter
from pathlib import Path
rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("artifacts/**/flowchan_guidance_autonomy_v0_*.json",recursive=True)]
summary={}
for arm in ["fixed_match","guided_autonomy"]:
    vals=[r[arm]["terminal_self_diff"] for r in rows]
    margins=[r[arm]["terminal_margin_diff"] for r in rows]
    acts=[r[arm]["action_changed_turns"] for r in rows]
    choice_counts=Counter(); reason_counts=Counter()
    for r in rows:
        choice_counts.update(r[arm].get("model_choice_counts",{}))
        reason_counts.update(r[arm].get("model_reason_counts",{}))
    summary[arm]={
      "cases":len(vals),"improved":sum(v>0 for v in vals),"worsened":sum(v<0 for v in vals),"tied":sum(v==0 for v in vals),
      "mean_self_diff":statistics.mean(vals) if vals else None,"sum_self_diff":sum(vals),
      "mean_margin_diff":statistics.mean(margins) if margins else None,"sum_margin_diff":sum(margins),
      "action_changed_turns":sum(acts),
      "choice_counts":dict(choice_counts),
      "reason_counts":dict(reason_counts),
      "per_seed":[{"seed":r["seed"],"self_diff":r[arm]["terminal_self_diff"],"margin_diff":r[arm]["terminal_margin_diff"]} for r in rows]
    }
payload={"schema":"kaggriculture.flowchan-guidance-autonomy.aggregate.v0","cases":len(rows),"summary":summary,"abstraction_status":"hypothesis","boundary":"Guidance is a perspective, not a command."}
Path("flowchan_guidance_autonomy_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
