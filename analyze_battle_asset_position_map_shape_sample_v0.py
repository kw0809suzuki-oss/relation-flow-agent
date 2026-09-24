#!/usr/bin/env python3
import json,sys
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/battle_asset_position_map_v0_*_seat*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if len(rows)!=5:raise SystemExit(f"expected 5 inputs, got {len(rows)}")
types=["WHEAT","MELON","STRAWBERRY","COW","SHEEP"]

def cp(r,day):
    xs=[x for x in r["checkpoints"] if int(x["day"])==day and int(x["hour"])==0]
    if not xs:raise KeyError((r["seed"],day))
    return xs[0]

def get(c,side,typ,key):
    return c[side]["summary_by_type"].get(typ,{}).get(key,0)

cases=[]
for r in rows:
    x={"seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"],"checkpoints":{}}
    for day in (13,14,16,17):
        c=cp(r,day)
        x["checkpoints"][str(day)]={}
        for side in ("self","opponent"):
            x["checkpoints"][str(day)][side]={}
            for typ in types:
                x["checkpoints"][str(day)][side][typ]={
                  "count":int(get(c,side,typ,"count")),
                  "held_output_units":int(get(c,side,typ,"held_output_units")),
                  "harvest_ready_count":int(get(c,side,typ,"harvest_ready_count")),
                  "within_24_turns_count":int(get(c,side,typ,"within_24_turns_count")),
                  "within_72_turns_count":int(get(c,side,typ,"within_72_turns_count")),
                }
    cases.append(x)

# Keep all values visible; only mark whether simple directional relations repeat 5/5.
checks={}
for lead,after,label in ((13,14,"pulse_A"),(16,17,"pulse_B")):
    checks[label]={}
    for typ in types:
        near_pairs=[]
        held_pairs=[]
        for c in cases:
            a=c["checkpoints"][str(lead)]
            b=c["checkpoints"][str(after)]
            near_pairs.append({
              "seed":c["seed"],
              "self":a["self"][typ]["within_24_turns_count"],
              "opponent":a["opponent"][typ]["within_24_turns_count"]
            })
            held_pairs.append({
              "seed":c["seed"],
              "self":b["self"][typ]["held_output_units"],
              "opponent":b["opponent"][typ]["held_output_units"]
            })
        checks[label][typ]={
          "lead_within_24":near_pairs,
          "after_held_output":held_pairs,
          "opponent_more_near_5_of_5":all(z["opponent"]>z["self"] for z in near_pairs),
          "opponent_more_held_5_of_5":all(z["opponent"]>z["self"] for z in held_pairs),
        }

out={
 "schema":"kaggriculture.battle-asset-position-map.shape-sample.v0",
 "schedule_id":rows[0]["schedule_id"],
 "public_rule_commit":rows[0]["public_rule_commit"],
 "battle_count":5,
 "cases":cases,
 "checks":checks,
 "boundary":[
   "The fixed Asset State Schedule is unchanged across all five Battles.",
   "No asset values are summed across types; only same-type physical/time positions are compared.",
   "within_24_turns_count is distance to a public output/formation boundary, not a score.",
   "At h0, a zero-turn scheduled boundary is the day boundary just reached in the recorded post-refresh State.",
   "No cause, Action, Candidate, or internal policy conclusion."
 ]
}
Path("battle_asset_position_map_shape_sample_v0_result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("BATTLE_ASSET_POSITION_SHAPE_SAMPLE "+json.dumps({"checks":checks},ensure_ascii=False,separators=(",",":")))
