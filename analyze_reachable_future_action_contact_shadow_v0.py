#!/usr/bin/env python3
import json,sys
from collections import Counter,defaultdict
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/reachable_future_action_contact_shadow_v0_*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if not rows: raise SystemExit("no inputs")

classes=Counter(x["classification"] for x in rows)
contact_hours=Counter(
    x["first_contact"]["hour"] for x in rows if x.get("first_contact") is not None
)
hour_stats=defaultdict(lambda:{"cases":0,"reachable_pre":0,"reachable_post":0,"entry_realized":0})
actual_actions=defaultdict(Counter)
for x in rows:
    for r in x["records"]:
        h=int(r["turn"]["hour"]); s=hour_stats[h]; s["cases"]+=1
        s["reachable_pre"]+=int(bool(r["pre_state"]["reachable"]))
        s["reachable_post"]+=int(bool((r.get("post_state") or {}).get("reachable")))
        s["entry_realized"]+=int(bool(r.get("actual_entry_realized_after_action")))
        key=json.dumps(r["actual_action"],sort_keys=True,separators=(",",":"))
        actual_actions[h][key]+=1

out={
  "schema":"kaggriculture.strong-origin-v2.reachable-future-action-contact-shadow.aggregate.v0",
  "battle_count":len(rows),
  "classification_counts":dict(classes),
  "first_contact_hour_counts":dict(contact_hours),
  "actual_entry_realized_cases":sum(bool(x["actual_entry_realized"]) for x in rows),
  "reachable_all_pre_h10_h23_cases":sum(bool(x["reachable_at_every_pre_action_state_h10_h23"]) for x in rows),
  "hourly":{
    str(h):{
      **hour_stats[h],
      "actual_action_patterns":dict(actual_actions[h])
    } for h in sorted(hour_stats)
  },
  "cases":rows,
  "boundary":[
    "No policy/action mutation.",
    "CONTACT is intermediate Day4 reachability loss before h23.",
    "NO_CONTACT means reachability survived all pre-action States h10-h23 and no actual tracked entry occurred.",
    "This audit diagnoses contact only; it does not infer Evaluation or Direction."
  ]
}
Path("reachable_future_action_contact_shadow_v0_result.json").write_text(
    json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
)
print("REACHABLE_FUTURE_ACTION_CONTACT_SHADOW_AGG "+json.dumps({
    k:v for k,v in out.items() if k not in ("cases","hourly")
},ensure_ascii=False,separators=(",",":")))
print("HOURLY "+json.dumps(out["hourly"],ensure_ascii=False,separators=(",",":")))
