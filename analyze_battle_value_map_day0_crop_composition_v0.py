#!/usr/bin/env python3
import json,sys
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/battle_value_map_day0_crop_composition_v0_*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if len(rows)!=5: raise SystemExit(f"expected 5 inputs, got {len(rows)}")

crops=["WHEAT","CARROT","TOMATO","STRAWBERRY","MELON"]
keys=["day0_h10","day0_h14","day0_h17"]

def same(vals):
    return all(v==vals[0] for v in vals[1:])

common={}
for ck in keys:
    block={}
    for metric in ("crop_count_by_type","crop_potential_units_by_type","crop_mark_by_type"):
        block[metric]={}
        for crop in crops:
            vals=[r["checkpoints"][ck]["residual"][metric][crop] for r in rows]
            block[metric][crop]={"values":vals,"all_equal":same(vals),"common_value":vals[0] if same(vals) else None}
    vals=[r["checkpoints"][ck]["residual"]["crop_total_mark"] for r in rows]
    block["crop_total_mark"]={"values":vals,"all_equal":same(vals),"common_value":vals[0] if same(vals) else None}
    common[ck]=block

# Growth in common mark residual, only if all five share each checkpoint.
growth={}
for crop in crops:
    h10=common["day0_h10"]["crop_mark_by_type"][crop]["common_value"]
    h14=common["day0_h14"]["crop_mark_by_type"][crop]["common_value"]
    h17=common["day0_h17"]["crop_mark_by_type"][crop]["common_value"]
    growth[crop]={
      "h10_to_h14":None if None in (h10,h14) else h14-h10,
      "h14_to_h17":None if None in (h14,h17) else h17-h14,
      "h10_to_h17":None if None in (h10,h17) else h17-h10,
    }

out={
  "schema":"kaggriculture.strong-origin-v2.battle-value-map.day0-crop-composition.aggregate.v0",
  "battle_count":5,
  "cases":[{"seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"]} for r in rows],
  "common":common,
  "mark_residual_growth_by_crop":growth,
  "all_three_checkpoints_identical_across_5":all(
      common[ck]["crop_total_mark"]["all_equal"]
      and all(common[ck]["crop_mark_by_type"][c]["all_equal"] for c in crops)
      and all(common[ck]["crop_count_by_type"][c]["all_equal"] for c in crops)
      and all(common[ck]["crop_potential_units_by_type"][c]["all_equal"] for c in crops)
      for ck in keys
  ),
  "boundary":[
    "This aggregate compares five individual fixed Battles; it does not average their trajectories.",
    "Only public crop productive-State composition is opened.",
    "No cause or policy conclusion."
  ]
}
Path("battle_value_map_day0_crop_composition_v0_result.json").write_text(
    json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
)
print("DAY0_CROP_COMPOSITION_AGG "+json.dumps({
  "all_equal":out["all_three_checkpoints_identical_across_5"],
  "common":out["common"],
  "growth":out["mark_residual_growth_by_crop"]
},ensure_ascii=False,separators=(",",":")))
