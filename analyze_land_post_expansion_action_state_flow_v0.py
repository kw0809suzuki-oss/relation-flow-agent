#!/usr/bin/env python3
"""Aggregate LAND Post-Expansion Action-to-State Flow v0."""
import json, statistics, sys
from collections import Counter
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None
def summ(xs):
    xs=[float(x) for x in xs if x is not None]
    return {"n":len(xs),"mean":mean(xs),"median":median(xs),"min":min(xs) if xs else None,"max":max(xs) if xs else None}
def total(d): return sum(float(v) for v in (d or {}).values())

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/land_post_expansion_action_state_flow_v0_*.json"))
    if len(files)!=50: raise SystemExit(f"Expected 50 files, got {len(files)}")
    rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    rows.sort(key=lambda r:int(r["seed"]))

    terminal={
      "mean_self":mean([float(r["terminal"]["self"]) for r in rows]),
      "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in rows]),
      "mean_margin":mean([float(r["terminal"]["margin"]) for r in rows]),
      "wins":sum(float(r["terminal"]["margin"])>0 for r in rows),
    }

    sides={}
    for side in ("self","opponent"):
        xs=[r[side] for r in rows]
        unit_keys=set(); market_keys=set()
        for x in xs:
            unit_keys.update((x.get("issued_unit_actions") or {}).keys())
            market_keys.update((x.get("issued_market_orders") or {}).keys())
        sides[side]={
          "issued_unit_actions":{k:summ([(x.get("issued_unit_actions") or {}).get(k,0) for x in xs]) for k in sorted(unit_keys)},
          "issued_market_orders":{k:summ([(x.get("issued_market_orders") or {}).get(k,0) for x in xs]) for k in sorted(market_keys)},
          "observed_new_crops_total":summ([total(x.get("observed_new_crops")) for x in xs]),
          "observed_new_animals_total":summ([total(x.get("observed_new_animals")) for x in xs]),
          "observed_new_crops_by_type":{},
          "observed_new_animals_by_type":{},
          "state_delta":{},
        }
        crop_keys=set(); animal_keys=set()
        for x in xs:
            crop_keys.update((x.get("observed_new_crops") or {}).keys())
            animal_keys.update((x.get("observed_new_animals") or {}).keys())
        for k in sorted(crop_keys):
            sides[side]["observed_new_crops_by_type"][k]=summ([(x.get("observed_new_crops") or {}).get(k,0) for x in xs])
        for k in sorted(animal_keys):
            sides[side]["observed_new_animals_by_type"][k]=summ([(x.get("observed_new_animals") or {}).get(k,0) for x in xs])
        for k in ("cash","empty_tiles","occupied_tiles","crop_count","animal_count","hands","seed_inventory_total","sellable_stock_total","committed_mark"):
            sides[side]["state_delta"][k]=summ([x.get("state_delta",{}).get(k) for x in xs])

    payload={
      "schema":"kaggriculture.land-post-expansion-action-state-flow.aggregate.v0",
      "battle_count":len(rows),
      "terminal_absolute":terminal,
      "self":sides["self"],"opponent":sides["opponent"],
      "cases":[{
        "seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"],
        "self":r["self"],"opponent":r["opponent"]
      } for r in rows],
      "boundary":[
        "Issued Action volume and directly observed productive placements are separate axes.",
        "Gross observed new placements are not equated to net productive value.",
        "This aggregate does not infer a bottleneck, cause, or strategy rule."
      ]
    }
    Path("land_post_expansion_action_state_flow_v0_aggregate.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    compact={
      "battle_count":len(rows),"terminal":terminal,
      "self":{
        "plant_issued":sides["self"]["issued_unit_actions"].get("PLANT",{}).get("mean"),
        "place_issued":sides["self"]["issued_unit_actions"].get("PLACE",{}).get("mean"),
        "movement_issued":sum(sides["self"]["issued_unit_actions"].get(k,{}).get("mean",0) or 0 for k in ("NORTH","SOUTH","EAST","WEST")),
        "new_crops":sides["self"]["observed_new_crops_total"]["mean"],
        "new_animals":sides["self"]["observed_new_animals_total"]["mean"],
        "occupied_delta":sides["self"]["state_delta"]["occupied_tiles"]["mean"],
        "committed_delta":sides["self"]["state_delta"]["committed_mark"]["mean"],
      },
      "opponent":{
        "plant_issued":sides["opponent"]["issued_unit_actions"].get("PLANT",{}).get("mean"),
        "place_issued":sides["opponent"]["issued_unit_actions"].get("PLACE",{}).get("mean"),
        "movement_issued":sum(sides["opponent"]["issued_unit_actions"].get(k,{}).get("mean",0) or 0 for k in ("NORTH","SOUTH","EAST","WEST")),
        "new_crops":sides["opponent"]["observed_new_crops_total"]["mean"],
        "new_animals":sides["opponent"]["observed_new_animals_total"]["mean"],
        "occupied_delta":sides["opponent"]["state_delta"]["occupied_tiles"]["mean"],
        "committed_delta":sides["opponent"]["state_delta"]["committed_mark"]["mean"],
      },
      "crop_by_type":{
        side:{k:v["mean"] for k,v in sides[side]["observed_new_crops_by_type"].items()}
        for side in ("self","opponent")
      },
      "animal_by_type":{
        side:{k:v["mean"] for k,v in sides[side]["observed_new_animals_by_type"].items()}
        for side in ("self","opponent")
      }
    }
    print("LAND_POST_EXPANSION_ACTION_STATE_FLOW_AGG "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
