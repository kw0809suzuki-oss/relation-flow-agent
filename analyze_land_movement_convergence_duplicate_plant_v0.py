#!/usr/bin/env python3
"""Aggregate LAND Movement Convergence -> Duplicate PLANT Observer v0."""
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
    moved_members=already_members=other_members=0
    all_moved=mixed=all_already=empty_before=0
    prev_action_ops=Counter()
    for g in gs:
        p=g.get("previous_transition") or {}
        moved_members += int(p.get("moved_into_target_count",0) or 0)
        already_members += int(p.get("already_on_target_count",0) or 0)
        other_members += int(p.get("other_count",0) or 0)
        if p:
            if p.get("moved_into_target_count",0)==g["group_size"]: all_moved+=1
            if 0<p.get("moved_into_target_count",0)<g["group_size"]: mixed+=1
            if p.get("already_on_target_count",0)==g["group_size"]: all_already+=1
            if p.get("target_tile_before_t_minus_1")=="EMPTY": empty_before+=1
            for m in p.get("members",[]):
                a=m.get("t_minus_1_action")
                op=a[0] if isinstance(a,list) and a else "NONE"
                prev_action_ops[str(op)]+=1
    return {
      "groups":len(gs),
      "failed_plants":sum(g["failed_count"] for g in gs),
      "group_size":dict(Counter(str(g["group_size"]) for g in gs)),
      "moved_members":moved_members,
      "already_members":already_members,
      "other_members":other_members,
      "all_members_moved_into_groups":all_moved,
      "mixed_arrival_groups":mixed,
      "all_already_groups":all_already,
      "target_empty_before_t_minus_1_groups":empty_before,
      "previous_action_ops":dict(prev_action_ops),
      "events":gs,
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/land_movement_convergence_duplicate_plant_v0_*.json"))
    if len(files)!=50: raise SystemExit(f"Expected 50 files, got {len(files)}")
    rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    rows.sort(key=lambda r:int(r["seed"]))
    cases=[]
    all_group_sizes=set(); all_ops=set()
    for r in rows:
        c={"seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"],
           "self":side_case(r["self"]),"opponent":side_case(r["opponent"])}
        cases.append(c)
        for side in ("self","opponent"):
            all_group_sizes.update(c[side]["group_size"])
            all_ops.update(c[side]["previous_action_ops"])
    agg={}
    for side in ("self","opponent"):
        agg[side]={
          "duplicate_groups":summ([c[side]["groups"] for c in cases]),
          "failed_plants":summ([c[side]["failed_plants"] for c in cases]),
          "cases_with_any":sum(c[side]["groups"]>0 for c in cases),
          "group_size":{k:sum(c[side]["group_size"].get(k,0) for c in cases) for k in sorted(all_group_sizes,key=int)},
          "moved_members_total":sum(c[side]["moved_members"] for c in cases),
          "already_members_total":sum(c[side]["already_members"] for c in cases),
          "other_members_total":sum(c[side]["other_members"] for c in cases),
          "all_members_moved_into_groups":sum(c[side]["all_members_moved_into_groups"] for c in cases),
          "mixed_arrival_groups":sum(c[side]["mixed_arrival_groups"] for c in cases),
          "all_already_groups":sum(c[side]["all_already_groups"] for c in cases),
          "target_empty_before_t_minus_1_groups":sum(c[side]["target_empty_before_t_minus_1_groups"] for c in cases),
          "previous_action_ops":{k:sum(c[side]["previous_action_ops"].get(k,0) for c in cases) for k in sorted(all_ops)},
        }

    terminal={
      "mean_self":mean([float(r["terminal"]["self"]) for r in rows]),
      "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in rows]),
      "mean_margin":mean([float(r["terminal"]["margin"]) for r in rows]),
      "wins":sum(float(r["terminal"]["margin"])>0 for r in rows),
    }

    payload={
      "schema":"kaggriculture.land-movement-convergence-duplicate-plant.aggregate.v0",
      "battle_count":len(rows),
      "terminal_absolute":terminal,
      "self":agg["self"],"opponent":agg["opponent"],
      "cases":cases,
      "boundary":[
        "This aggregate observes one transition before duplicate PLANT only.",
        "Movement convergence is position/action evidence, not a claim about target-selection intent.",
        "No coordination Candidate or terminal-effect claim is generated."
      ]
    }
    Path("land_movement_convergence_duplicate_plant_v0_aggregate.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    compact={"battle_count":len(rows),"terminal":terminal,"self":agg["self"],"opponent":agg["opponent"]}
    print("LAND_MOVEMENT_CONVERGENCE_DUPLICATE_PLANT_AGG "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
