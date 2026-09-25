#!/usr/bin/env python3
"""Post-LAND first-12-turn productive conversion audit from existing 50 raw artifacts."""
import glob,json,statistics
from collections import Counter
from pathlib import Path

def mean(xs):return sum(xs)/len(xs) if xs else None
def med(xs):return statistics.median(xs) if xs else None

files=sorted(Path(p) for p in glob.glob("inputs/**/land_plant_realization_audit_v0_*.json",recursive=True))
if len(files)!=50: raise SystemExit(f"Expected 50 raw files, got {len(files)}")
raws=[json.loads(p.read_text(encoding="utf-8")) for p in files]
rows=[]
for r in raws:
    row={"seed":r["seed"],"seat":r["seat"]}
    for side in ("self","opponent"):
        ev=[e for e in r[side].get("events",[]) if int(e["relative_turn"])<=12]
        cls=Counter(e["classification"] for e in ev)
        crop=Counter(e["crop"] for e in ev)
        succ=[e for e in ev if e["classification"]=="success_unit_phase"]
        coll=[e for e in ev if e["classification"]=="same_turn_target_became_nonempty"]
        row[side]={
          "issued":len(ev),"success":len(succ),"collision":len(coll),
          "success_rate":len(succ)/len(ev) if ev else None,
          "crop":dict(crop),
          "first_success_turn":min([int(e["relative_turn"]) for e in succ],default=None),
          "first_collision_turn":min([int(e["relative_turn"]) for e in coll],default=None),
        }
    rows.append(row)

def agg(side):
    xs=[r[side] for r in rows]
    crops=sorted(set(k for x in xs for k in x["crop"]))
    return {
      "issued_mean":mean([x["issued"] for x in xs]),
      "success_mean":mean([x["success"] for x in xs]),
      "collision_mean":mean([x["collision"] for x in xs]),
      "success_rate_mean":mean([x["success_rate"] for x in xs if x["success_rate"] is not None]),
      "success_positive_cases":sum(x["success"]>0 for x in xs),
      "collision_positive_cases":sum(x["collision"]>0 for x in xs),
      "first_success_turn_mean":mean([x["first_success_turn"] for x in xs if x["first_success_turn"] is not None]),
      "first_success_turn_median":med([x["first_success_turn"] for x in xs if x["first_success_turn"] is not None]),
      "first_collision_turn_mean":mean([x["first_collision_turn"] for x in xs if x["first_collision_turn"] is not None]),
      "crop_issued_mean":{c:mean([x["crop"].get(c,0) for x in xs]) for c in crops},
    }

payload={
 "schema":"kaggriculture.post-land-first12-productive-conversion-audit.v0",
 "source_run_id":35913668518,
 "battle_count":50,
 "window":"first 12 retained turns after each side's first realized LAND expansion",
 "self":agg("self"),"opponent":agg("opponent"),"cases":rows,
 "boundary":[
   "Reanalysis of existing observation-only LAND PLANT raw artifacts; no new Battle and no policy mutation.",
   "Window is relative to each side's own first realized LAND expansion.",
   "success_unit_phase and same_turn_target_became_nonempty are mechanical public-rule execution classes.",
   "This localizes Input->Productive-State conversion behavior; it does not yet adopt a rule."
 ]}
Path("post_land_first12_productive_conversion_audit_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("POST_LAND_FIRST12_PRODUCTIVE_CONVERSION "+json.dumps({"self":payload["self"],"opponent":payload["opponent"]},ensure_ascii=False,separators=(",",":")))
