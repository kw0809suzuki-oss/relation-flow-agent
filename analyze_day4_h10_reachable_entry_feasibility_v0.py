#!/usr/bin/env python3
import glob,json,sys
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/day4_h10_reachable_entry_feasibility_v0_*.json"))
raw=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if not raw: raise SystemExit("no inputs")
out={
  "schema":"kaggriculture.strong-origin-v2.day4-h10-next-cycle-entry-feasibility.aggregate.v0",
  "battle_count":len(raw),
  "cash_mean":mean([x["cash"] for x in raw]),
  "melon_seed_mean":mean([x["certified_existing_seed_entry"]["seed_available"] for x in raw]),
  "empty_unlocked_mean":mean([x["empty_unlocked_count"] for x in raw]),
  "workers_mean":mean([len(x["unit_positions"]) for x in raw]),
  "min_path_moves_mean":mean([x["closest_empty_path"]["manhattan_moves"] for x in raw]),
  "min_path_moves_max":max(x["closest_empty_path"]["manhattan_moves"] for x in raw),
  "movement_plus_plant_max":max(x["certified_existing_seed_entry"]["movement_plus_plant_actions"] for x in raw),
  "reachable_cases":sum(bool(x["certified_existing_seed_entry"]["can_enter_productive_state_before_day5"]) for x in raw),
  "cases":raw,
  "boundary":[
    "Existence only: no Candidate, Direction, or policy mutation.",
    "Existing MELON seed path requires no market purchase.",
    "Feasible entry is not equivalent to selected entry or terminal improvement."
  ]
}
Path("day4_h10_reachable_entry_feasibility_v0_result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("DAY4_H10_REACHABLE_ENTRY_FEASIBILITY_AGG "+json.dumps({k:v for k,v in out.items() if k!="cases"},ensure_ascii=False,separators=(",",":")))
