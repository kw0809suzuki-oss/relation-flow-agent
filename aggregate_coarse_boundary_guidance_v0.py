#!/usr/bin/env python3
import glob,json,statistics
from collections import Counter
from pathlib import Path
rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("artifacts/**/coarse_boundary_guidance_v0_*.json",recursive=True)]
summary={}
for arm in ["current_objective_pressure","coarse_boundary_candidate"]:
    vals=[r[arm]["terminal_self_diff"] for r in rows]
    margins=[r[arm]["terminal_margin_diff"] for r in rows]
    choices=Counter(); regimes=Counter(); reasons=Counter()
    for r in rows:
        choices.update(r[arm].get("choice_counts",{}))
        regimes.update(r[arm].get("regime_counts",{}))
        reasons.update(r[arm].get("reason_counts",{}))
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
      "boundary_change_count":sum(r[arm]["boundary_change_count"] for r in rows),
      "choice_counts":dict(choices),
      "regime_counts":dict(regimes),
      "reason_counts":dict(reasons),
      "per_seed":[{"seed":r["seed"],"self_diff":r[arm]["terminal_self_diff"],"margin_diff":r[arm]["terminal_margin_diff"]} for r in rows]
    }
cv=[r["candidate_vs_current"]["self_diff"] for r in rows]
cm=[r["candidate_vs_current"]["margin_diff"] for r in rows]
payload={
 "schema":"kaggriculture.coarse-boundary-guidance.aggregate.v0",
 "cases":len(rows),
 "summary":summary,
 "candidate_vs_current":{
   "improved":sum(v>0 for v in cv),
   "worsened":sum(v<0 for v in cv),
   "tied":sum(v==0 for v in cv),
   "mean_self_diff":statistics.mean(cv) if cv else None,
   "sum_self_diff":sum(cv),
   "mean_margin_diff":statistics.mean(cm) if cm else None,
   "sum_margin_diff":sum(cm),
   "per_seed":[{"seed":r["seed"],"self_diff":r["candidate_vs_current"]["self_diff"],"margin_diff":r["candidate_vs_current"]["margin_diff"]} for r in rows]
 },
 "hypothesis_status":"working_hypothesis"
}
Path("coarse_boundary_guidance_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
