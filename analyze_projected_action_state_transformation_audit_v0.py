#!/usr/bin/env python3
import json,sys
from collections import Counter,defaultdict
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/projected_action_state_transformation_audit_v0_*.json"))
cases=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if not cases: raise SystemExit("no inputs")

hours=(11,15,19,23)
summary={}
for h in hours:
    rows=[next(r for r in c["rows"] if r["hour"]==h) for c in cases]
    reasons=Counter()
    for r in rows:
        reasons.update(r["plant_summary"].get("noop_reasons",{}))
    summary[str(h)]={
        "cases":len(rows),
        "plant_requests":sum(r["plant_summary"]["plant_requests"] for r in rows),
        "plant_successes":sum(r["plant_summary"]["plant_successes"] for r in rows),
        "melon_requests":sum(r["plant_summary"]["melon_requests"] for r in rows),
        "melon_successes":sum(r["plant_summary"]["melon_successes"] for r in rows),
        "melon_noops":sum(r["plant_summary"]["melon_noops"] for r in rows),
        "wheat_requests":sum(r["plant_summary"]["wheat_requests"] for r in rows),
        "wheat_successes":sum(r["plant_summary"]["wheat_successes"] for r in rows),
        "noop_reasons":dict(reasons),
        "cases_with_melon_request":sum(r["plant_summary"]["melon_requests"]>0 for r in rows),
        "cases_with_melon_success":sum(r["plant_summary"]["melon_successes"]>0 for r in rows),
    }

terminal_self=sum(c["terminal"]["self"] for c in cases)/len(cases)
terminal_opp=sum(c["terminal"]["opponent"] for c in cases)/len(cases)

out={
  "schema":"kaggriculture.strong-origin-v2.projected-action-state-transformation-audit.aggregate.v0",
  "battle_count":len(cases),
  "terminal_context":{
    "self_absolute_mean":terminal_self,
    "opponent_absolute_mean":terminal_opp,
    "mean_margin":terminal_self-terminal_opp,
  },
  "hourly":summary,
  "totals":{
    "melon_requests":sum(v["melon_requests"] for v in summary.values()),
    "melon_successes":sum(v["melon_successes"] for v in summary.values()),
    "melon_noops":sum(v["melon_noops"] for v in summary.values()),
    "plant_requests":sum(v["plant_requests"] for v in summary.values()),
    "plant_successes":sum(v["plant_successes"] for v in summary.values()),
  },
  "cases":cases,
  "boundary":[
    "This audit measures Action -> World Transformation only.",
    "It does not infer whether MELON or any crop should be preferred.",
    "It does not infer terminal causality from local no-ops.",
    "No Candidate, Direction, or policy mutation."
  ]
}
Path("projected_action_state_transformation_audit_v0_result.json").write_text(
    json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
)
print("PROJECTED_ACTION_STATE_TRANSFORMATION_AGG "+json.dumps({
    "battle_count":out["battle_count"],
    "terminal_context":out["terminal_context"],
    "hourly":out["hourly"],
    "totals":out["totals"],
},ensure_ascii=False,separators=(",",":")))
