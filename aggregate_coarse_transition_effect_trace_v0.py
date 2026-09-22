#!/usr/bin/env python3
import glob,json
from collections import Counter
from pathlib import Path
rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("artifacts/**/coarse_transition_effect_trace_v0_*.json",recursive=True)]
patterns=Counter()
items=[]
for r in rows:
    for x in r.get("transitions_with_nearby_action_divergence",[]):
        patterns[(str(x.get("regime")),str(x.get("choice")),str(x.get("reason")))] += 1
    items.append({
      "seed":r["seed"],
      "self_diff":r["terminal"]["self_diff"],
      "margin_diff":r["terminal"]["margin_diff"],
      "first_action_divergence":r["first_action_divergence"],
      "candidate_transition_count":r["candidate_transition_count"],
      "action_divergence_count":r["action_divergence_count"],
      "nearby_transition_count":len(r.get("transitions_with_nearby_action_divergence",[])),
      "transitions_with_nearby_action_divergence":r.get("transitions_with_nearby_action_divergence",[])
    })
payload={
 "schema":"kaggriculture.coarse-transition-effect-trace.aggregate.v0",
 "cases":len(rows),
 "transition_patterns_with_nearby_action_divergence":[
   {"regime":k[0],"choice":k[1],"reason":k[2],"count":v}
   for k,v in patterns.most_common()
 ],
 "seeds":sorted(items,key=lambda x:x["seed"]),
 "boundary":"Observer only. Pattern frequency is not causal evidence."
}
Path("coarse_transition_effect_trace_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cases":len(rows),"patterns":len(patterns)},ensure_ascii=False))
