#!/usr/bin/env python3
import glob,json
from collections import Counter
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None

paths=sorted(Path(p) for p in glob.glob("return-melon-lineage-artifacts/**/return_melon_lineage_v0_*.json",recursive=True))
if len(paths)!=10: raise SystemExit(f"Expected 10 artifacts, found {len(paths)}")
raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
rows=[]
for r in raws:
    seat=int(r["seat"]);opp=1-seat
    rows.append({
      "seed":r["seed"],"seat":seat,
      "self_plant":r["first_return_seed_required_plant_by_player"][str(seat)],
      "opponent_plant":r["first_return_seed_required_plant_by_player"][str(opp)],
      "self_production":r["first_production_from_that_tile_by_player"][str(seat)],
      "opponent_production":r["first_production_from_that_tile_by_player"][str(opp)],
      "context":r["opponent_target_production_context_units_by_player"],
      "terminal":r["terminal"],
    })

def sig(z):
    if not z:return None
    return f'D{z["day"]}h{z["hour"]}@{z["position"]}'

opp_plants=[r["opponent_plant"] for r in rows if r["opponent_plant"]]
opp_prod=[r["opponent_production"] for r in rows if r["opponent_production"]]
self_plants=[r["self_plant"] for r in rows if r["self_plant"]]
self_prod=[r["self_production"] for r in rows if r["self_production"]]
payload={
 "schema":"kaggriculture.return-melon-lineage.result.v0",
 "battle_count":10,
 "opponent":{
   "return_seed_required_plant_cases":len(opp_plants),
   "first_plant_time_frequency":dict(Counter((z["day"],z["hour"]) for z in opp_plants)),
   "first_production_cases":len(opp_prod),
   "first_production_time_frequency":dict(Counter((z["day"],z["hour"]) for z in opp_prod)),
   "mean_first_production_units":mean([z["units"] for z in opp_prod]),
 },
 "self":{
   "return_seed_required_plant_cases":len(self_plants),
   "first_production_cases":len(self_prod),
 },
 "cases":rows,
 "boundary":[
   "A repeated opponent path closes only if Return-dependent seed necessity, successful PLANT, and later actual yield all appear on the same tracked tile.",
   "This is actual-path lineage, not a policy counterfactual or terminal-effect claim.",
   "WR-03 remains undefined until this observation is interpreted against the whole objective."
 ]
}
Path("return_melon_lineage_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("RETURN_MELON_LINEAGE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))
