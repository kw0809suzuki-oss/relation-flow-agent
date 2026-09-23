#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/mode_to_action_reachability_path_v0_*.json",recursive=True)]

items=[]
for r in rows:
    path=r.get("path",[])
    items.append({
      "seed":r["seed"],
      "self_diff":r["terminal"]["self_diff"],
      "margin_diff":r["terminal"]["margin_diff"],
      "mode_turn":r.get("first_mode_divergence_turn"),
      "action_turn":r.get("first_action_divergence_turn"),
      "distance":r.get("mode_to_action_distance"),
      "same_action_turns":r.get("same_action_turns_before_first_action_divergence"),
      "mode_choice_current":path[0]["current"].get("choice") if path else None,
      "mode_choice_coarse":path[0]["coarse"].get("choice") if path else None,
      "action_current":path[-1]["current"].get("action") if path and r.get("first_action_divergence_turn") is not None else None,
      "action_coarse":path[-1]["coarse"].get("action") if path and r.get("first_action_divergence_turn") is not None else None,
      "post_first_action_state":r.get("post_first_action_state")
    })

dist=[x["distance"] for x in items if x["distance"] is not None]
payload={
 "schema":"kaggriculture.mode-to-action-reachability-path.aggregate.v0",
 "cases":len(items),
 "with_mode_divergence":sum(x["mode_turn"] is not None for x in items),
 "with_action_divergence":sum(x["action_turn"] is not None for x in items),
 "distance":{
   "values":dist,
   "min":min(dist) if dist else None,
   "max":max(dist) if dist else None,
   "mean":statistics.mean(dist) if dist else None
 },
 "seeds":sorted(items,key=lambda x:x["seed"]),
 "boundary":"Observed shortest temporal paths only; no causal attribution."
}
Path("mode_to_action_reachability_path_v0_aggregate.json").write_text(
 json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cases":len(items),"distances":dist},ensure_ascii=False))
