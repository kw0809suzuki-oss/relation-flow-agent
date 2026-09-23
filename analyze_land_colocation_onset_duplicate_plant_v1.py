#!/usr/bin/env python3
"""Aggregate LAND Co-location Onset -> Duplicate PLANT Observer v1."""
import json, statistics, sys
from collections import Counter
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None
def summ(xs):
    xs=[float(x) for x in xs if x is not None]
    return {"n":len(xs),"mean":mean(xs),"median":median(xs),"min":min(xs) if xs else None,"max":max(xs) if xs else None}

def side_case(side):
    gs=side.get("groups",[])
    persistence=Counter()
    onset_actions=Counter()
    moved=already=new_unit=other=0
    onset_empty=0
    for g in gs:
        o=g["colocation_onset"]
        persistence[str(o["full_colocation_persistence_turns_before_plant"])]+=1
        moved+=o["moved_into_target_count"]
        already+=o["already_on_target_count"]
        new_unit+=o["new_unit_at_target_count"]
        other+=o["other_count"]
        onset_empty+=int(o.get("target_tile_before_onset")=="EMPTY")
        for m in o.get("members",[]):
            a=m.get("onset_action")
            op=a[0] if isinstance(a,list) and a else "NONE"
            onset_actions[str(op)]+=1
    return {
      "groups":len(gs),
      "failed_plants":sum(g["failed_count"] for g in gs),
      "persistence":dict(persistence),
      "moved_members":moved,
      "already_members":already,
      "new_unit_members":new_unit,
      "other_members":other,
      "onset_target_empty_groups":onset_empty,
      "onset_actions":dict(onset_actions),
      "events":gs,
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/land_colocation_onset_duplicate_plant_v1_*.json"))
    if len(files)!=50: raise SystemExit(f"Expected 50 files, got {len(files)}")
    rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    rows.sort(key=lambda r:int(r["seed"]))
    cases=[]
    pkeys=set(); akeys=set()
    for r in rows:
        c={"seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"],
           "self":side_case(r["self"]),"opponent":side_case(r["opponent"])}
        cases.append(c)
        for side in ("self","opponent"):
            pkeys.update(c[side]["persistence"])
            akeys.update(c[side]["onset_actions"])
    agg={}
    for side in ("self","opponent"):
        agg[side]={
          "duplicate_groups":summ([c[side]["groups"] for c in cases]),
          "failed_plants":summ([c[side]["failed_plants"] for c in cases]),
          "cases_with_any":sum(c[side]["groups"]>0 for c in cases),
          "persistence_turns":{k:sum(c[side]["persistence"].get(k,0) for c in cases) for k in sorted(pkeys,key=int)},
          "moved_members_total":sum(c[side]["moved_members"] for c in cases),
          "already_members_total":sum(c[side]["already_members"] for c in cases),
          "new_unit_members_total":sum(c[side]["new_unit_members"] for c in cases),
          "other_members_total":sum(c[side]["other_members"] for c in cases),
          "onset_target_empty_groups":sum(c[side]["onset_target_empty_groups"] for c in cases),
          "onset_actions":{k:sum(c[side]["onset_actions"].get(k,0) for c in cases) for k in sorted(akeys)},
        }
    terminal={
      "mean_self":mean([float(r["terminal"]["self"]) for r in rows]),
      "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in rows]),
      "mean_margin":mean([float(r["terminal"]["margin"]) for r in rows]),
      "wins":sum(float(r["terminal"]["margin"])>0 for r in rows),
    }
    payload={
      "schema":"kaggriculture.land-colocation-onset-duplicate-plant.aggregate.v1",
      "battle_count":len(rows),"terminal_absolute":terminal,
      "self":agg["self"],"opponent":agg["opponent"],"cases":cases,
      "boundary":[
        "Co-location onset is backtracked only within the same game day.",
        "Observed onset actions and positions do not establish target-selection intent.",
        "No intervention or terminal-effect conclusion is generated."
      ]
    }
    Path("land_colocation_onset_duplicate_plant_v1_aggregate.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("LAND_COLOCATION_ONSET_DUPLICATE_PLANT_AGG "+json.dumps({
      "battle_count":len(rows),"terminal":terminal,"self":agg["self"],"opponent":agg["opponent"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
