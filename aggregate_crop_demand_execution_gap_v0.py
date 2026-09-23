#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/crop_demand_execution_gap_v0_*.json",recursive=True)]

def mean(xs): return statistics.mean(xs) if xs else None
keys=["base_crop_demand","actual_crop_execution","missed_crop_exec","overlay_changed_slots",
      "missed_due_to_changed_slot","base_water","actual_water","base_harvest","actual_harvest",
      "base_plant","actual_plant"]

tot={k:sum(r.get("summary",{}).get(k,0) for r in rows) for k in keys}
payload={
 "schema":"kaggriculture.crop-demand-execution-gap.aggregate.v0",
 "cases":len(rows),
 "cases_with_crop_loss":sum(bool(r.get("crop_loss_days")) for r in rows),
 "crop_loss_events":sum(len(r.get("crop_loss_days",[])) for r in rows),
 "unique_precursor_turns":sum(r.get("unique_precursor_turns",0) for r in rows),
 "totals":tot,
 "rates":{
   "execution_over_demand": (tot["actual_crop_execution"]/tot["base_crop_demand"] if tot["base_crop_demand"] else None),
   "missed_over_demand": (tot["missed_crop_exec"]/tot["base_crop_demand"] if tot["base_crop_demand"] else None),
   "missed_changed_share": (tot["missed_due_to_changed_slot"]/tot["missed_crop_exec"] if tot["missed_crop_exec"] else None)
 },
 "per_seed":[
   {"seed":r["seed"],"loss_days":r.get("crop_loss_days",[]),
    "unique_precursor_turns":r.get("unique_precursor_turns",0),
    **r.get("summary",{})}
   for r in sorted(rows,key=lambda x:x["seed"])
 ],
 "scale_check":{
   "baseline_absolute_mean_self":mean([r["terminal"]["self"] for r in rows]),
   "opponent_absolute_mean_self":mean([r["terminal"]["opponent"] for r in rows]),
   "mean_terminal_residual":mean([r["terminal"]["residual"] for r in rows]),
   "candidate_absolute_mean_self":None,
   "delta":None
 },
 "boundary":"Turn-deduplicated requested-vs-executed crop work only."
}
Path("crop_demand_execution_gap_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
