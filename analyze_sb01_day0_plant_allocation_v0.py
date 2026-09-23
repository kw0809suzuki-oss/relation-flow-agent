#!/usr/bin/env python3
"""SB-01 Day0 PLANT Allocation v0.

Reuses raw Day0 actions from Run 35831478953.
Counts issued PLANT actions by crop for main farmer + hands and compares them
with Day1 surviving Day0-planted crop counts and remaining seeds.

No claim is made that every issued PLANT executed successfully.
"""
import json, statistics, sys
from pathlib import Path
from collections import Counter

CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")


def issued_plant_counts(raw, seat):
    key=f"seat{seat}"
    out=Counter()
    for row in raw["day0_steps"]:
        act=(row[key] or {}).get("action") or {}
        if not isinstance(act,dict): continue
        actions=[act.get("farmer",["PASS"])]
        ha=act.get("hands",[])
        if isinstance(ha,list): actions.extend(ha)
        for a in actions:
            if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS:
                out[a[1]]+=1
    return {c:out[c] for c in CROPS}


def day1_crop_state(obs):
    player=int(obs.get("player",0))
    farm=obs["farms"][player]
    private=obs.get("private",{}) or {}
    planted={c:0 for c in CROPS}
    for row in farm.get("tiles",[]) or []:
        for tile in row or []:
            if not isinstance(tile,dict): continue
            c=tile.get("crop")
            if c in planted and int(tile.get("planted_day",-999))==0:
                planted[c]+=1
    remaining={c:int((private.get("seeds",{}) or {}).get(c,0) or 0) for c in CROPS}
    return planted,remaining


def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None


def summarize(cases,getter):
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
    }


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("sb01_day0_resource_flow_input_*.json"))
    if not files: files=sorted(root.glob("**/sb01_day0_resource_flow_input_*.json"))
    if not files: raise SystemExit("No inputs")

    cases=[]
    for p in files:
        raw=json.loads(p.read_text(encoding="utf-8"))
        seat=int(raw["seat"]); opp=1-seat
        si=issued_plant_counts(raw,seat)
        oi=issued_plant_counts(raw,opp)
        sp,sr=day1_crop_state(raw["day1_first"][str(seat)]["observation"])
        op,orr=day1_crop_state(raw["day1_first"][str(opp)]["observation"])
        cases.append({
            "seed":int(raw["seed"]),
            "self":{"issued":si,"day1_planted":sp,"day1_remaining_seed":sr},
            "opponent":{"issued":oi,"day1_planted":op,"day1_remaining_seed":orr},
        })

    agg={}
    for crop in CROPS:
        agg[crop]={
            "issued_plant_actions":summarize(cases,lambda s,c=crop:s["issued"][c]),
            "day1_surviving_day0_plants":summarize(cases,lambda s,c=crop:s["day1_planted"][c]),
            "day1_remaining_seed":summarize(cases,lambda s,c=crop:s["day1_remaining_seed"][c]),
        }

    payload={
        "schema":"kaggriculture.sb01.day0-plant-allocation.v0",
        "source_run_id":35831478953,
        "battle_count":len(cases),
        "aggregate":agg,
        "cases":cases,
        "boundary":[
            "Issued PLANT actions are action-allocation facts.",
            "Day1 surviving plants are state facts.",
            "Difference between issued PLANT count and Day1 surviving plants is not automatically labeled failed execution; later loss/removal can also contribute.",
            "No causal or policy conclusion is generated."
        ]
    }
    Path("sb01_day0_plant_allocation_v0.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    compact={
        c:{
            "self_issued":agg[c]["issued_plant_actions"]["self_absolute_mean"],
            "opp_issued":agg[c]["issued_plant_actions"]["opponent_absolute_mean"],
            "self_day1_planted":agg[c]["day1_surviving_day0_plants"]["self_absolute_mean"],
            "opp_day1_planted":agg[c]["day1_surviving_day0_plants"]["opponent_absolute_mean"],
            "self_remaining_seed":agg[c]["day1_remaining_seed"]["self_absolute_mean"],
            "opp_remaining_seed":agg[c]["day1_remaining_seed"]["opponent_absolute_mean"],
        } for c in CROPS
    }
    print("SB01_DAY0_PLANT_ALLOCATION "+json.dumps({"battle_count":len(cases),"crops":compact},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
