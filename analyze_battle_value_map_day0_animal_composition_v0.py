#!/usr/bin/env python3
import json,sys
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/battle_value_map_day0_animal_composition_v0_*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if len(rows)!=5: raise SystemExit(f"expected 5 inputs, got {len(rows)}")

animals=["GOOSE","COW","SHEEP"]
keys=["day0_h10","day0_h14","day0_h17"]

def same(vals): return all(v==vals[0] for v in vals[1:])

common={}
for ck in keys:
    block={}
    for metric in ("animal_count_by_type","animal_potential_units_by_type","animal_mark_by_type"):
        block[metric]={}
        for animal in animals:
            vals=[r["checkpoints"][ck]["residual"][metric][animal] for r in rows]
            block[metric][animal]={"values":vals,"all_equal":same(vals),"common_value":vals[0] if same(vals) else None}
    vals=[r["checkpoints"][ck]["residual"]["animal_total_mark"] for r in rows]
    block["animal_total_mark"]={"values":vals,"all_equal":same(vals),"common_value":vals[0] if same(vals) else None}
    common[ck]=block

growth={}
for animal in animals:
    h10=common["day0_h10"]["animal_mark_by_type"][animal]["common_value"]
    h14=common["day0_h14"]["animal_mark_by_type"][animal]["common_value"]
    h17=common["day0_h17"]["animal_mark_by_type"][animal]["common_value"]
    growth[animal]={
      "h10_to_h14":None if None in (h10,h14) else h14-h10,
      "h14_to_h17":None if None in (h14,h17) else h17-h14,
      "h10_to_h17":None if None in (h10,h17) else h17-h10,
    }

out={
  "schema":"kaggriculture.strong-origin-v2.battle-value-map.day0-animal-composition.aggregate.v0",
  "battle_count":5,
  "cases":[{"seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"]} for r in rows],
  "common":common,
  "mark_residual_growth_by_animal":growth,
  "all_three_checkpoints_identical_across_5":all(
      common[ck]["animal_total_mark"]["all_equal"]
      and all(common[ck]["animal_mark_by_type"][a]["all_equal"] for a in animals)
      and all(common[ck]["animal_count_by_type"][a]["all_equal"] for a in animals)
      and all(common[ck]["animal_potential_units_by_type"][a]["all_equal"] for a in animals)
      for ck in keys
  ),
  "boundary":[
    "This aggregate compares five individual fixed Battles; it does not average their trajectories.",
    "Only public animal productive-State composition is opened.",
    "No cause or policy conclusion."
  ]
}
Path("battle_value_map_day0_animal_composition_v0_result.json").write_text(
    json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
)
print("DAY0_ANIMAL_COMPOSITION_AGG "+json.dumps({
  "all_equal":out["all_three_checkpoints_identical_across_5"],
  "common":out["common"],
  "growth":out["mark_residual_growth_by_animal"]
},ensure_ascii=False,separators=(",",":")))
