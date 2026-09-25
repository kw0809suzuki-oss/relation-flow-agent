#!/usr/bin/env python3
import glob,json
from collections import Counter
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None

paths=sorted(Path(p) for p in glob.glob("generated-return-land-lineage-artifacts/**/generated_return_land_production_lineage_v0_*.json",recursive=True))
if len(paths)!=10: raise SystemExit(f"Expected 10 artifacts, found {len(paths)}")
raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
rows=[]
for r in raws:
    seat=int(r["seat"]);opp=1-seat
    rows.append({
      "seed":r["seed"],"seat":seat,
      "self_land":r["first_generated_return_land_by_player"][str(seat)],
      "opponent_land":r["first_generated_return_land_by_player"][str(opp)],
      "self_plants":r["successful_plants_on_that_new_land_by_player"][str(seat)],
      "opponent_plants":r["successful_plants_on_that_new_land_by_player"][str(opp)],
      "self_first_production":r["first_production_from_that_new_land_by_player"][str(seat)],
      "opponent_first_production":r["first_production_from_that_new_land_by_player"][str(opp)],
      "context":r["opponent_first_production_context"],
      "terminal":r["terminal"],
    })

opp_land=[r["opponent_land"] for r in rows if r["opponent_land"]]
opp_plants=[z for r in rows for z in r["opponent_plants"]]
opp_prod=[r["opponent_first_production"] for r in rows if r["opponent_first_production"]]
self_prod=[r["self_first_production"] for r in rows if r["self_first_production"]]
payload={
 "schema":"kaggriculture.generated-return-land-production-lineage.result.v0",
 "battle_count":10,
 "opponent":{
   "generated_return_land_cases":len(opp_land),
   "land_time_frequency":dict(Counter((z["day"],z["hour"]) for z in opp_land)),
   "new_land_successful_plant_cases":sum(bool(r["opponent_plants"]) for r in rows),
   "new_land_plant_crop_frequency":dict(Counter(z["crop"] for z in opp_plants)),
   "first_production_cases":len(opp_prod),
   "first_production_time_frequency":dict(Counter((z["day"],z["hour"]) for z in opp_prod)),
   "first_production_crop_frequency":dict(Counter(z["crop"] for z in opp_prod)),
   "mean_first_production_units":mean([z["units"] for z in opp_prod]),
 },
 "self":{
   "first_production_cases":len(self_prod),
   "first_production_time_frequency":dict(Counter((z["day"],z["hour"]) for z in self_prod)),
 },
 "cases":rows,
 "boundary":[
   "The bridge is closed only when generated Return necessity, exact newly unlocked coordinates, successful PLANT on those coordinates, and actual yield increase all appear on the same Battle path.",
   "No terminal causal attribution or WR-03 is introduced by this observer."
 ]
}
Path("generated_return_land_production_lineage_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("GENERATED_RETURN_LAND_PRODUCTION_LINEAGE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))
