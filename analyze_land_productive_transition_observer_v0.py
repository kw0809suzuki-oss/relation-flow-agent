#!/usr/bin/env python3
"""Aggregate LAND Productive Transition Observer v0 outputs.

Observation only. No causal conclusion and no Action attribution.
"""
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

OFFSETS=(-1,0,24,48,72)
FIELDS=(
    "cash","unlocked_tiles","empty_tiles","occupied_tiles","occupancy_ratio",
    "crop_count","animal_count","hands","seed_inventory_total",
    "sellable_stock_total","committed_mark","remaining_turns",
)
CHANGE_FIELDS=(
    "empty_tiles","occupied_tiles","crop_count","animal_count",
    "seed_inventory_total","sellable_stock_total","committed_mark",
)

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None
def q(xs,p):
    if not xs:return None
    ys=sorted(xs); pos=(len(ys)-1)*p
    lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:return ys[lo]
    return ys[lo]*(hi-pos)+ys[hi]*(pos-lo)
def summ(xs):
    xs=[float(x) for x in xs if x is not None]
    return {
        "n":len(xs),"mean":mean(xs),"median":median(xs),
        "q25":q(xs,.25),"q75":q(xs,.75),
        "min":min(xs) if xs else None,"max":max(xs) if xs else None,
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/land_productive_transition_observer_v0_*.json"))
    if len(files)!=50:
        raise SystemExit(f"Expected 50 observer files, got {len(files)}")
    rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    rows.sort(key=lambda r:int(r["seed"]))

    terminal={
        "mean_self":mean([float(r["terminal"]["self"]) for r in rows]),
        "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in rows]),
        "mean_margin":mean([float(r["terminal"]["margin"]) for r in rows]),
        "wins":sum(float(r["terminal"]["margin"])>0 for r in rows),
    }

    summary={}
    for side in ("self","opponent"):
        srows=[r[side] for r in rows]
        summary[side]={
            "land_event_found":sum(bool(x["land_event_found"]) for x in srows),
            "land_event_day":summ([x["land_event"]["day"] if x["land_event"] else None for x in srows]),
            "land_event_hour":summ([x["land_event"]["hour"] if x["land_event"] else None for x in srows]),
            "event_delta":{},
            "snapshots":{},
            "first_state_change_by_field":{},
        }
        for f in FIELDS:
            summary[side]["event_delta"][f]=summ([
                x["event_delta"].get(f) if x.get("event_delta") else None for x in srows
            ])
        for rel in OFFSETS:
            snap={}
            for f in FIELDS:
                vals=[]
                for x in srows:
                    z=x["snapshots"].get(str(rel))
                    vals.append((z["state"].get(f) if z else None))
                snap[f]=summ(vals)
            summary[side]["snapshots"][str(rel)]=snap
        for f in CHANGE_FIELDS:
            vals=[]
            directions=Counter()
            for x in srows:
                ev=x["first_state_change_by_field"].get(f)
                if ev:
                    vals.append(ev["relative_turn"])
                    directions[ev["direction"]]+=1
            summary[side]["first_state_change_by_field"][f]={
                "relative_turn":summ(vals),
                "direction_counts":dict(directions),
                "observed_within_72":len(vals),
            }

    paired={}
    for rel in OFFSETS:
        paired[str(rel)]={}
        for f in FIELDS:
            gaps=[]
            for r in rows:
                ss=r["self"]["snapshots"].get(str(rel))
                oo=r["opponent"]["snapshots"].get(str(rel))
                if not ss or not oo: continue
                gaps.append(float(oo["state"][f])-float(ss["state"][f]))
            paired[str(rel)][f]=summ(gaps)

    div_turns=[]
    div_fields=Counter()
    combo=Counter()
    for r in rows:
        d=r.get("first_self_vs_opponent_transition_divergence")
        if not d: continue
        div_turns.append(d["relative_turn"])
        fields=tuple(sorted(d["fields"]))
        combo[fields]+=1
        for f in fields: div_fields[f]+=1

    payload={
        "schema":"kaggriculture.land-productive-transition-observer.aggregate.v0",
        "battle_count":len(rows),
        "terminal_absolute":terminal,
        "self":summary["self"],
        "opponent":summary["opponent"],
        "paired_opponent_minus_self_by_offset":paired,
        "first_self_vs_opponent_transition_divergence":{
            "observed_cases":len(div_turns),
            "relative_turn":summ(div_turns),
            "field_counts":dict(div_fields),
            "field_combinations":{
                "+".join(k):v for k,v in combo.most_common()
            },
        },
        "cases":[{
            "seed":r["seed"],
            "seat":r["seat"],
            "terminal":r["terminal"],
            "self_land_event":r["self"]["land_event"],
            "opponent_land_event":r["opponent"]["land_event"],
            "self_first_state_change_by_field":r["self"]["first_state_change_by_field"],
            "opponent_first_state_change_by_field":r["opponent"]["first_state_change_by_field"],
            "first_divergence":r.get("first_self_vs_opponent_transition_divergence"),
        } for r in rows],
        "boundary":[
            "State-transition observation only.",
            "t=0 is each side's own first realized LAND expansion.",
            "Snapshot gaps compare event-aligned relative time, not same calendar turn.",
            "first divergence is a physical-State delta divergence, not cause.",
            "Cash and hands are context axes and do not trigger first divergence.",
            "No Action attribution or Candidate is generated.",
        ],
    }
    Path("land_productive_transition_observer_v0_aggregate.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={
        "battle_count":len(rows),
        "terminal":terminal,
        "land_event":{
            "self_day_mean":summary["self"]["land_event_day"]["mean"],
            "opponent_day_mean":summary["opponent"]["land_event_day"]["mean"],
            "self_found":summary["self"]["land_event_found"],
            "opponent_found":summary["opponent"]["land_event_found"],
        },
        "snapshot_gaps":{
            str(rel):{
                f:paired[str(rel)][f]["mean"]
                for f in ("empty_tiles","occupied_tiles","crop_count","animal_count",
                          "seed_inventory_total","sellable_stock_total","committed_mark")
            } for rel in OFFSETS
        },
        "first_changes":{
            side:{
                f:{
                    "mean_turn":summary[side]["first_state_change_by_field"][f]["relative_turn"]["mean"],
                    "median_turn":summary[side]["first_state_change_by_field"][f]["relative_turn"]["median"],
                    "n":summary[side]["first_state_change_by_field"][f]["observed_within_72"],
                    "dir":summary[side]["first_state_change_by_field"][f]["direction_counts"],
                } for f in CHANGE_FIELDS
            } for side in ("self","opponent")
        },
        "first_divergence":payload["first_self_vs_opponent_transition_divergence"],
    }
    print("LAND_PRODUCTIVE_TRANSITION_AGG "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
