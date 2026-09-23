#!/usr/bin/env python3
"""Aggregate LAND PLANT Realization Audit v0."""
import json, statistics, sys
from collections import Counter
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None
def summ(xs):
    xs=[float(x) for x in xs if x is not None]
    return {"n":len(xs),"mean":mean(xs),"median":median(xs),"min":min(xs) if xs else None,"max":max(xs) if xs else None}

def side_case(side):
    ev=side.get("events",[])
    cls=Counter(x["classification"] for x in ev)
    crop=Counter(x["crop"] for x in ev)
    succ=sum(x["classification"]=="success_unit_phase" for x in ev)
    vis=sum(bool(x.get("visible_post_as_requested_crop")) for x in ev)
    blocks=[x for x in ev if x["classification"]=="atomic_seed_blocked"]
    return {
      "issued":len(ev),
      "success_unit_phase":succ,
      "visible_post":vis,
      "classification":dict(cls),
      "crop":dict(crop),
      "atomic_block_events":len(blocks),
      "atomic_block_events_with_same_turn_buy":sum(int(x.get("same_turn_buy_seed_issued",0) or 0)>0 for x in blocks),
      "atomic_block_same_turn_buy_qty_sum":sum(int(x.get("same_turn_buy_seed_issued",0) or 0) for x in blocks),
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/land_plant_realization_audit_v0_*.json"))
    if len(files)!=50: raise SystemExit(f"Expected 50 files, got {len(files)}")
    rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    rows.sort(key=lambda r:int(r["seed"]))

    cases=[]
    for r in rows:
        cases.append({
          "seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"],
          "self":side_case(r["self"]),"opponent":side_case(r["opponent"]),
        })

    all_classes=set()
    all_crops=set()
    for c in cases:
        for side in ("self","opponent"):
            all_classes.update(c[side]["classification"].keys())
            all_crops.update(c[side]["crop"].keys())

    agg={}
    for side in ("self","opponent"):
        agg[side]={
          "issued":summ([c[side]["issued"] for c in cases]),
          "success_unit_phase":summ([c[side]["success_unit_phase"] for c in cases]),
          "visible_post":summ([c[side]["visible_post"] for c in cases]),
          "classification":{
            k:summ([c[side]["classification"].get(k,0) for c in cases])
            for k in sorted(all_classes)
          },
          "crop":{
            k:summ([c[side]["crop"].get(k,0) for c in cases])
            for k in sorted(all_crops)
          },
          "atomic_block_events_with_same_turn_buy":summ([
            c[side]["atomic_block_events_with_same_turn_buy"] for c in cases
          ]),
          "atomic_block_same_turn_buy_qty_sum":summ([
            c[side]["atomic_block_same_turn_buy_qty_sum"] for c in cases
          ]),
        }

    terminal={
      "mean_self":mean([float(r["terminal"]["self"]) for r in rows]),
      "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in rows]),
      "mean_margin":mean([float(r["terminal"]["margin"]) for r in rows]),
      "wins":sum(float(r["terminal"]["margin"])>0 for r in rows),
    }

    payload={
      "schema":"kaggriculture.land-plant-realization-audit.aggregate.v0",
      "battle_count":len(rows),
      "terminal_absolute":terminal,
      "self":agg["self"],"opponent":agg["opponent"],
      "cases":cases,
      "boundary":[
        "Failure classes are mechanical execution-rule classes, not causal explanations.",
        "success_unit_phase and visible_post are separated.",
        "same-turn BUY_SEED is context only because public execution order places market after unit actions."
      ]
    }
    Path("land_plant_realization_audit_v0_aggregate.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={
      "battle_count":len(rows),"terminal":terminal,
      "self":{
        "issued_mean":agg["self"]["issued"]["mean"],
        "success_mean":agg["self"]["success_unit_phase"]["mean"],
        "visible_mean":agg["self"]["visible_post"]["mean"],
        "classification_mean":{k:v["mean"] for k,v in agg["self"]["classification"].items()},
        "same_turn_buy_blocked_events_mean":agg["self"]["atomic_block_events_with_same_turn_buy"]["mean"],
      },
      "opponent":{
        "issued_mean":agg["opponent"]["issued"]["mean"],
        "success_mean":agg["opponent"]["success_unit_phase"]["mean"],
        "visible_mean":agg["opponent"]["visible_post"]["mean"],
        "classification_mean":{k:v["mean"] for k,v in agg["opponent"]["classification"].items()},
        "same_turn_buy_blocked_events_mean":agg["opponent"]["atomic_block_events_with_same_turn_buy"]["mean"],
      }
    }
    print("LAND_PLANT_REALIZATION_AUDIT_AGG "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
