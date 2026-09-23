#!/usr/bin/env python3
"""Aggregate LAND Failed-PLANT Target Filler Audit v0."""
import json, statistics, sys
from collections import Counter
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None
def summ(xs):
    xs=[float(x) for x in xs if x is not None]
    return {"n":len(xs),"mean":mean(xs),"median":median(xs),"min":min(xs) if xs else None,"max":max(xs) if xs else None}

def side_case(side):
    fs=side.get("failed_plant_fillers",[])
    return {
      "count":len(fs),
      "filler_op":dict(Counter(x["filler_op"] for x in fs)),
      "pairs":dict(Counter(f'{x["filler_op"]}:{x.get("filler_item")}->{x["failed_crop"]}' for x in fs)),
      "unit_order_gap":dict(Counter(str(x["unit_order_gap"]) for x in fs)),
      "events":fs,
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/land_failed_plant_target_filler_v0_*.json"))
    if len(files)!=50: raise SystemExit(f"Expected 50 files, got {len(files)}")
    rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    rows.sort(key=lambda r:int(r["seed"]))
    cases=[]
    all_ops=set(); all_pairs=set(); all_gaps=set()
    for r in rows:
        c={"seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"],
           "self":side_case(r["self"]),"opponent":side_case(r["opponent"])}
        cases.append(c)
        for side in ("self","opponent"):
            all_ops.update(c[side]["filler_op"])
            all_pairs.update(c[side]["pairs"])
            all_gaps.update(c[side]["unit_order_gap"])
    agg={}
    for side in ("self","opponent"):
        agg[side]={
          "failed_count":summ([c[side]["count"] for c in cases]),
          "cases_with_any":sum(c[side]["count"]>0 for c in cases),
          "filler_op":{k:sum(c[side]["filler_op"].get(k,0) for c in cases) for k in sorted(all_ops)},
          "pairs":{k:sum(c[side]["pairs"].get(k,0) for c in cases) for k in sorted(all_pairs)},
          "unit_order_gap":{k:sum(c[side]["unit_order_gap"].get(k,0) for c in cases) for k in sorted(all_gaps,key=lambda x:int(x))},
        }
    terminal={
      "mean_self":mean([float(r["terminal"]["self"]) for r in rows]),
      "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in rows]),
      "mean_margin":mean([float(r["terminal"]["margin"]) for r in rows]),
      "wins":sum(float(r["terminal"]["margin"])>0 for r in rows),
    }
    payload={
      "schema":"kaggriculture.land-failed-plant-target-filler.aggregate.v0",
      "battle_count":len(rows),"terminal_absolute":terminal,
      "self":agg["self"],"opponent":agg["opponent"],"cases":cases,
      "boundary":[
        "Counts identify the first earlier same-turn unit Action that filled an initially-empty target.",
        "These are execution-order facts, not causal or intervention claims."
      ]
    }
    Path("land_failed_plant_target_filler_v0_aggregate.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    compact={
      "battle_count":len(rows),"terminal":terminal,
      "self":agg["self"],"opponent":agg["opponent"],
    }
    print("LAND_FAILED_PLANT_TARGET_FILLER_AGG "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
