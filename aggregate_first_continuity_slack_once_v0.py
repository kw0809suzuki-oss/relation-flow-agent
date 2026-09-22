#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("artifacts/**/first_continuity_slack_once_v0_*.json",recursive=True)]
def summarize(key):
    s=[r[key]["self_diff"] for r in rows]; m=[r[key]["margin_diff"] for r in rows]
    return {
      "improved":sum(v>0 for v in s),"worsened":sum(v<0 for v in s),"tied":sum(v==0 for v in s),
      "mean_self_diff":statistics.mean(s) if s else None,"sum_self_diff":sum(s),
      "mean_margin_diff":statistics.mean(m) if m else None,"sum_margin_diff":sum(m),
      "per_seed":[{"seed":r["seed"],"self_diff":r[key]["self_diff"],"margin_diff":r[key]["margin_diff"],"trigger_count":r["trigger_count"],"trigger_turns":r["trigger_turns"]} for r in rows]
    }
payload={
 "schema":"kaggriculture.first-continuity-slack-once.aggregate.v0",
 "cases":len(rows),
 "one_shot_vs_current":summarize("one_shot_vs_current"),
 "one_shot_vs_coarse":summarize("one_shot_vs_coarse"),
 "trigger_total":sum(r["trigger_count"] for r in rows),
 "action_changed_turns_vs_current":sum(r["action_changed_turns_vs_current"] for r in rows),
 "hypothesis_status":"working_hypothesis"
}
Path("first_continuity_slack_once_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
