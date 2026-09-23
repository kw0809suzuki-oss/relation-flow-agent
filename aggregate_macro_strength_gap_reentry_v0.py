#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
from collections import defaultdict

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/macro_strength_gap_reentry_v0_*.json",recursive=True)]

def mean(xs): return statistics.mean(xs) if xs else None

term_self=[r["terminal"]["self"] for r in rows]
term_opp=[r["terminal"]["opponent"] for r in rows]
term_res=[r["terminal"]["residual"] for r in rows]

by_day=defaultdict(list)
for r in rows:
    for x in r.get("day_end",[]):
        by_day[x["day"]].append(x)

day_summary=[]
for d in sorted(by_day):
    xs=by_day[d]
    rec={"day":d,"n":len(xs)}
    for k in ["money","hands","land","crop_tiles","animal_tiles","production_tiles"]:
        rec[f"mean_self_{k}"]=mean([x["self"][k] for x in xs])
        rec[f"mean_opponent_{k}"]=mean([x["opponent"][k] for x in xs])
        rec[f"mean_gap_{k}"]=mean([x["gap"][k] for x in xs])
    day_summary.append(rec)

threshold=10000
first_large=None
for rec in day_summary:
    if rec["mean_gap_money"]>=threshold:
        later=[x for x in day_summary if x["day"]>=rec["day"]]
        if later and sum(x["mean_gap_money"]>=threshold for x in later)/len(later)>=0.75:
            first_large=rec["day"]; break

payload={
 "schema":"kaggriculture.macro-strength-gap-reentry.aggregate.v0",
 "cases":len(rows),
 "scale_check":{
   "baseline_absolute_mean_self":mean(term_self),
   "opponent_absolute_mean_self":mean(term_opp),
   "mean_terminal_residual":mean(term_res),
   "recent_local_effect_reference":-19.7,
   "recent_local_effect_over_residual_pct":(
      abs(-19.7)/mean(term_res)*100 if term_res and mean(term_res)!=0 else None
   )
 },
 "first_persistent_mean_money_gap_ge_10000_day":first_large,
 "day_summary":day_summary,
 "terminal_per_seed":[
   {"seed":r["seed"],"self":r["terminal"]["self"],"opponent":r["terminal"]["opponent"],"residual":r["terminal"]["residual"]}
   for r in sorted(rows,key=lambda x:x["seed"])
 ],
 "boundary":"Macro observation only. Large gaps identify where to look, not why they exist."
}
Path("macro_strength_gap_reentry_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cases":len(rows),"scale_check":payload["scale_check"],"first_large_day":first_large},ensure_ascii=False))
