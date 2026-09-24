#!/usr/bin/env python3
import glob,json,sys
from collections import Counter
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/internal_representation_audit_v0_*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if not rows: raise SystemExit("no inputs")

caps=[x["capture"] for x in rows]
strategies=Counter(c["internal"].get("strategy_name") for c in caps)
best=Counter(c["internal"].get("best_crop") for c in caps)

def score(c,k): return float((c["internal"].get("scores",{}) or {}).get(k,0) or 0)
def target(c,k): return float((c["internal"].get("targets",{}) or {}).get(k,0) or 0)

out={
  "schema":"kaggriculture.strong-origin-v2.internal-representation-audit.aggregate.v0",
  "battle_count":len(rows),
  "day4_h10":{
    "strategies":dict(strategies),
    "best_crop":dict(best),
    "mean_scores":{k:mean([score(c,k) for c in caps]) for k in ("WHEAT","MELON","STRAWBERRY")},
    "mean_targets":{k:mean([target(c,k) for c in caps]) for k in ("WHEAT","MELON","STRAWBERRY")},
    "existing_melon_seed_mean":mean([float(c["shadow_world_reachable"]["existing_seed_available"]) for c in caps]),
    "shadow_next_production_day_values":sorted(set(c["shadow_world_reachable"]["next_production_day"] for c in caps)),
    "base_actions":[c["base_action"] for c in caps],
    "final_actions":[c["final_action"] for c in caps],
    "overlay_changed_farmer_cases":sum(c["overlay_changed_farmer"] for c in caps),
    "overlay_changed_hands_cases":sum(c["overlay_changed_hands"] for c in caps),
    "overlay_changed_market_cases":sum(c["overlay_changed_market"] for c in caps)
  },
  "static_decision_path":{
    "explicit_reachable_future":"ABSENT",
    "implicit_reachable_future_at_day4_h10":"ABSENT",
    "evidence":[
      "strong_origin computes no candidate-entry production_day or harvest_day.",
      "FIRST_YIELD only affects candidate crop scores through remaining_days <= FIRST_YIELD[crop] + 1; at Day4 remaining_days=26, so this branch is false for WHEAT, STRAWBERRY, and MELON.",
      "MAX_YIELD_DAY is used for HARVEST of already-existing plants, not evaluation of a contemplated new entry.",
      "counter_crop_weights receives XField, prices, base prices, and town demand; it has no crop maturity schedule input. Its horizon factor is common across crops.",
      "origin_targets uses strategy/day/capacity and a hard-coded early mix; it does not compute whether a contemplated entry reaches the next-cycle production window.",
      "g8 livestock overlay does not read crop maturity schedule or compute crop future reachability."
    ]
  },
  "classification":"ABSENT",
  "classification_scope":"Specific to next-cycle reachability of the certified Day4 h10 G1 crop-entry opportunity.",
  "cases":rows,
  "boundary":[
    "ABSENT does not mean the Body has no time-awareness at all; it has end-horizon and existing-asset timing logic.",
    "The finding is narrower: candidate-entry next-cycle reachability does not feed the Day4 h10 action-generation path.",
    "The hard-coded early crop mix is not treated as evidence of implicit maturity representation without a dataflow connection to public maturity rules.",
    "Shadow reachability is logged only; Action is unchanged."
  ]
}
Path("internal_representation_audit_v0_result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("INTERNAL_REPRESENTATION_AUDIT_AGG "+json.dumps({k:v for k,v in out.items() if k!="cases"},ensure_ascii=False,separators=(",",":")))
