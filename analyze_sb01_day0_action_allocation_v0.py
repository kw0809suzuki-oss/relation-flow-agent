#!/usr/bin/env python3
"""SB-01 Day0 Action Allocation v0.

Reuses raw Day0 actions from Run 35831478953.
Counts issued unit actions (main farmer + hands) into coarse categories.
No causal claim and no success/effectiveness claim is made here.
"""
import json, statistics, sys
from pathlib import Path
from collections import Counter

CATEGORIES = (
    "PLANT",
    "WATER",
    "ANIMAL_SETUP",
    "ANIMAL_CARE",
    "SHED_HANDLING",
    "MOVEMENT",
    "HARVEST",
    "OTHER_ECONOMIC",
    "PASS",
)

MOVE={"NORTH","SOUTH","EAST","WEST"}
ANIMAL_SETUP={"BUILD_COOP","BUILD_PASTURE","PLACE"}
ANIMAL_CARE={"FEED","CARE","COLLECT_FERTILIZER"}
SHED={"PICKUP","DROP"}
OTHER_ECON={"FERTILIZE","DIG"}


def classify(action):
    if not isinstance(action,list) or not action:
        return "PASS"
    op=action[0]
    if op=="PLANT": return "PLANT"
    if op=="WATER": return "WATER"
    if op in ANIMAL_SETUP: return "ANIMAL_SETUP"
    if op in ANIMAL_CARE: return "ANIMAL_CARE"
    if op in SHED: return "SHED_HANDLING"
    if op in MOVE: return "MOVEMENT"
    if op=="HARVEST": return "HARVEST"
    if op in OTHER_ECON: return "OTHER_ECONOMIC"
    if op=="PASS": return "PASS"
    return "OTHER_ECONOMIC"


def side_counts(raw, seat):
    key=f"seat{seat}"
    total=Counter()
    main=Counter()
    hands=Counter()

    for row in raw["day0_steps"]:
        act=(row[key] or {}).get("action") or {}
        if not isinstance(act,dict):
            continue

        fa=act.get("farmer",["PASS"])
        cat=classify(fa)
        total[cat]+=1
        main[cat]+=1

        ha=act.get("hands",[])
        if isinstance(ha,list):
            for a in ha:
                cat=classify(a)
                total[cat]+=1
                hands[cat]+=1

    for c in CATEGORIES:
        total[c]+=0; main[c]+=0; hands[c]+=0

    nonpass=sum(total[c] for c in CATEGORIES if c!="PASS")
    production_direct=total["PLANT"]+total["HARVEST"]
    maintenance=total["WATER"]+total["ANIMAL_CARE"]
    setup=total["ANIMAL_SETUP"]
    movement=total["MOVEMENT"]
    handling=total["SHED_HANDLING"]
    return {
        "total":dict(total),
        "main":dict(main),
        "hands":dict(hands),
        "nonpass_unit_actions":nonpass,
        "direct_production_actions":production_direct,
        "maintenance_actions":maintenance,
        "animal_setup_actions":setup,
        "movement_actions":movement,
        "shed_handling_actions":handling,
    }


def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None


def summarize(cases, getter):
    sv=[getter(c["self"]) for c in cases]
    ov=[getter(c["opponent"]) for c in cases]
    gaps=[o-s for s,o in zip(sv,ov)]
    return {
        "self_absolute_mean":mean(sv),
        "opponent_absolute_mean":mean(ov),
        "mean_gap_opponent_minus_self":mean(gaps),
        "median_gap_opponent_minus_self":median(gaps),
        "opponent_ahead_cases":sum(g>0 for g in gaps),
        "self_ahead_cases":sum(g<0 for g in gaps),
        "equal_cases":sum(g==0 for g in gaps),
        "self_min":min(sv) if sv else None,
        "self_max":max(sv) if sv else None,
        "opponent_min":min(ov) if ov else None,
        "opponent_max":max(ov) if ov else None,
    }


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("sb01_day0_resource_flow_input_*.json"))
    if not files:
        files=sorted(root.glob("**/sb01_day0_resource_flow_input_*.json"))
    if not files:
        raise SystemExit("No Day0 resource-flow input files found")

    cases=[]
    for p in files:
        raw=json.loads(p.read_text(encoding="utf-8"))
        seat=int(raw["seat"])
        cases.append({
            "seed":int(raw["seed"]),
            "seat":seat,
            "self":side_counts(raw,seat),
            "opponent":side_counts(raw,1-seat),
        })

    aggregate={"total":{},"main":{},"hands":{}}
    for scope in ("total","main","hands"):
        for cat in CATEGORIES:
            aggregate[scope][cat]=summarize(
                cases, lambda s,sc=scope,c=cat:s[sc][c]
            )

    aggregate["summary"]={
        "nonpass_unit_actions":summarize(cases,lambda s:s["nonpass_unit_actions"]),
        "direct_production_actions":summarize(cases,lambda s:s["direct_production_actions"]),
        "maintenance_actions":summarize(cases,lambda s:s["maintenance_actions"]),
        "animal_setup_actions":summarize(cases,lambda s:s["animal_setup_actions"]),
        "movement_actions":summarize(cases,lambda s:s["movement_actions"]),
        "shed_handling_actions":summarize(cases,lambda s:s["shed_handling_actions"]),
    }

    payload={
        "schema":"kaggriculture.sb01.day0-action-allocation.v0",
        "source_run_id":35831478953,
        "battle_count":len(cases),
        "aggregate":aggregate,
        "cases":cases,
        "boundary":[
            "Counts issued unit actions from retained Day0 action bundles.",
            "Main farmer and hired-hand actions are both included in total.",
            "These are allocation counts, not successful-execution counts.",
            "PLANT/HARVEST are grouped as direct production actions only for descriptive comparison.",
            "No causal or adoption conclusion is generated."
        ]
    }
    Path("sb01_day0_action_allocation_v0.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={
        "battle_count":len(cases),
        "summary":{
            k:{
                "self":v["self_absolute_mean"],
                "opponent":v["opponent_absolute_mean"],
                "gap":v["mean_gap_opponent_minus_self"],
            } for k,v in aggregate["summary"].items()
        },
        "categories":{
            c:{
                "self":aggregate["total"][c]["self_absolute_mean"],
                "opponent":aggregate["total"][c]["opponent_absolute_mean"],
                "gap":aggregate["total"][c]["mean_gap_opponent_minus_self"],
                "opp_ahead_cases":aggregate["total"][c]["opponent_ahead_cases"],
                "self_ahead_cases":aggregate["total"][c]["self_ahead_cases"],
            } for c in CATEGORIES
        }
    }
    print("SB01_DAY0_ACTION_ALLOCATION "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
