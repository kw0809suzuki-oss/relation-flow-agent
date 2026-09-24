#!/usr/bin/env python3
import json,sys
from pathlib import Path

p=Path(sys.argv[1] if len(sys.argv)>1 else "battle_asset_position_map_v0_7351_seat0.json")
d=json.loads(p.read_text(encoding="utf-8"))
types=["WHEAT","MELON","STRAWBERRY","COW","SHEEP"]
rows=[]
for c in d["checkpoints"]:
    row={"day":c["day"]}
    for side in ("self","opponent"):
        s=c[side]["summary_by_type"]
        row[side]={}
        for typ in types:
            x=s.get(typ,{})
            row[side][typ]={
              "count":int(x.get("count",0)),
              "held_output_units":int(x.get("held_output_units",0)),
              "harvest_ready_count":int(x.get("harvest_ready_count",0)),
              "within_24_turns_count":int(x.get("within_24_turns_count",0)),
              "within_72_turns_count":int(x.get("within_72_turns_count",0)),
              "turns_to_boundaries":x.get("turns_to_boundaries",[])
            }
    rows.append(row)
out={
 "schema":"kaggriculture.battle-asset-position-map.summary.v0",
 "schedule_id":d["schedule_id"],
 "seed":d["seed"],"seat":d["seat"],"terminal":d["terminal"],
 "days":rows,
 "boundary":[
   "This summary is physical/time position only.",
   "Counts within 24/72 turns are descriptive proximity to public boundaries, not value scores.",
   "No ranking or policy conclusion."
 ]
}
Path("battle_asset_position_map_v0_summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("BATTLE_ASSET_POSITION_SUMMARY "+json.dumps(out,ensure_ascii=False,separators=(",",":")))
