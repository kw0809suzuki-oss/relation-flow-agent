#!/usr/bin/env python3
"""SB-01 Day0 aligned Action Allocation v1.

Consumes correctly aligned pre-State -> Action -> post-State transitions.
Reports:
- total unit-action allocation
- PLANT requests by crop
- directly observed new-plant transitions by crop

The observed-new-plant count is conservative at the Day0->Day1 closing
transition because end-of-day refresh may remove a newly planted crop before
the stored post-State. That boundary is therefore reported separately.
"""
import json, statistics, sys
from pathlib import Path
from collections import Counter,defaultdict

CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")
CATEGORIES=("PLANT","WATER","ANIMAL_SETUP","ANIMAL_CARE","SHED_HANDLING","MOVEMENT","HARVEST","OTHER_ECONOMIC","PASS")
MOVE={"NORTH","SOUTH","EAST","WEST"}
ANIMAL_SETUP={"BUILD_COOP","BUILD_PASTURE","PLACE"}
ANIMAL_CARE={"FEED","CARE","COLLECT_FERTILIZER"}
SHED={"PICKUP","DROP"}
OTHER={"FERTILIZE","DIG"}


def classify(a):
    if not isinstance(a,list) or not a: return "PASS"
    op=a[0]
    if op=="PLANT": return "PLANT"
    if op=="WATER": return "WATER"
    if op in ANIMAL_SETUP:return "ANIMAL_SETUP"
    if op in ANIMAL_CARE:return "ANIMAL_CARE"
    if op in SHED:return "SHED_HANDLING"
    if op in MOVE:return "MOVEMENT"
    if op=="HARVEST":return "HARVEST"
    if op in OTHER:return "OTHER_ECONOMIC"
    if op=="PASS":return "PASS"
    return "OTHER_ECONOMIC"


def tile(farm,pos):
    x,y=pos
    return farm["tiles"][y][x]


def side_case(raw,seat):
    key=f"seat{seat}"
    cats=Counter()
    plant_req=Counter()
    new_plant=Counter()
    closing_plant_req=Counter()
    closing_new_plant=Counter()

    for tr in raw["transitions"]:
        pre=tr[key]["pre_observation"]
        post=tr[key]["post_observation"]
        act=tr[key]["action"] or {}
        player=int(pre.get("player",seat))
        pre_farm=pre["farms"][player]
        post_farm=post["farms"][player]

        positions=[tuple(pre_farm.get("farmer",[0,0]))]+[tuple(p) for p in (pre_farm.get("hands",[]) or [])]
        actions=[act.get("farmer",["PASS"])]
        ha=act.get("hands",[])
        if isinstance(ha,list): actions.extend(ha)

        closing=(int(tr["to"]["day"])==1)
        targets=defaultdict(list)
        for idx,a in enumerate(actions):
            cat=classify(a); cats[cat]+=1
            if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS and idx<len(positions):
                crop=a[1]
                plant_req[crop]+=1
                if closing: closing_plant_req[crop]+=1
                targets[positions[idx]].append(crop)

        # Count at most one newly observed plant per target tile.
        for pos,crops in targets.items():
            pre_t=tile(pre_farm,pos)
            post_t=tile(post_farm,pos)
            if not isinstance(post_t,dict) or post_t.get("crop") not in CROPS:
                continue
            crop=post_t.get("crop")
            was_same=(isinstance(pre_t,dict) and pre_t.get("crop")==crop and int(pre_t.get("planted_day",-999))==0)
            if crop in crops and not was_same and int(post_t.get("planted_day",-999))==0:
                new_plant[crop]+=1
                if closing: closing_new_plant[crop]+=1

    for c in CATEGORIES: cats[c]+=0
    for c in CROPS:
        plant_req[c]+=0; new_plant[c]+=0; closing_plant_req[c]+=0; closing_new_plant[c]+=0

    return {
        "categories":dict(cats),
        "plant_requests":dict(plant_req),
        "observed_new_plants":dict(new_plant),
        "closing_transition_plant_requests":dict(closing_plant_req),
        "closing_transition_observed_new_plants":dict(closing_new_plant),
        "nonpass":sum(cats[c] for c in CATEGORIES if c!="PASS"),
    }


def mean(xs):return sum(xs)/len(xs) if xs else None
def median(xs):return statistics.median(xs) if xs else None


def summ(cases,getter):
    sv=[getter(c["self"]) for c in cases]; ov=[getter(c["opponent"]) for c in cases]
    gaps=[o-s for s,o in zip(sv,ov)]
    return {
        "self_absolute_mean":mean(sv),"opponent_absolute_mean":mean(ov),
        "mean_gap_opponent_minus_self":mean(gaps),"median_gap_opponent_minus_self":median(gaps),
        "opponent_ahead_cases":sum(g>0 for g in gaps),"self_ahead_cases":sum(g<0 for g in gaps),"equal_cases":sum(g==0 for g in gaps)
    }


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("sb01_day0_aligned_transitions_v1_*.json"))
    if not files: files=sorted(root.glob("**/sb01_day0_aligned_transitions_v1_*.json"))
    if not files: raise SystemExit("No aligned inputs")

    cases=[]
    bad=[]
    for p in files:
        raw=json.loads(p.read_text(encoding="utf-8"))
        if len(raw.get("transitions",[]))!=24:
            bad.append(raw.get("seed")); continue
        seat=int(raw["seat"])
        cases.append({"seed":int(raw["seed"]),"self":side_case(raw,seat),"opponent":side_case(raw,1-seat)})
    if bad: raise SystemExit(f"Bad transition count: {bad}")

    agg={"categories":{},"plant":{}}
    for c in CATEGORIES:
        agg["categories"][c]=summ(cases,lambda s,k=c:s["categories"][k])
    agg["nonpass"]=summ(cases,lambda s:s["nonpass"])
    for crop in CROPS:
        agg["plant"][crop]={
            "requests":summ(cases,lambda s,k=crop:s["plant_requests"][k]),
            "observed_new_plants":summ(cases,lambda s,k=crop:s["observed_new_plants"][k]),
            "closing_requests":summ(cases,lambda s,k=crop:s["closing_transition_plant_requests"][k]),
            "closing_observed_new_plants":summ(cases,lambda s,k=crop:s["closing_transition_observed_new_plants"][k]),
        }

    payload={
        "schema":"kaggriculture.sb01.day0-aligned-action-allocation.v1",
        "battle_count":len(cases),"aggregate":agg,"cases":cases,
        "boundary":[
            "All counts use 24 explicitly aligned Day0 pre-State -> Action -> post-State transitions.",
            "Action categories count issued unit actions.",
            "observed_new_plants counts directly visible tile transitions into a Day0-planted crop.",
            "Closing Day0->Day1 transition may hide a newly planted crop that dies during end-of-day refresh; closing counts are shown separately.",
            "No causal conclusion is generated."
        ]
    }
    Path("sb01_day0_aligned_action_allocation_v1.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    compact={
        "battle_count":len(cases),
        "nonpass":{"self":agg["nonpass"]["self_absolute_mean"],"opponent":agg["nonpass"]["opponent_absolute_mean"],"gap":agg["nonpass"]["mean_gap_opponent_minus_self"]},
        "categories":{c:{"self":agg["categories"][c]["self_absolute_mean"],"opponent":agg["categories"][c]["opponent_absolute_mean"],"gap":agg["categories"][c]["mean_gap_opponent_minus_self"]} for c in CATEGORIES},
        "plant":{c:{
            "self_requests":agg["plant"][c]["requests"]["self_absolute_mean"],
            "opp_requests":agg["plant"][c]["requests"]["opponent_absolute_mean"],
            "self_new_visible":agg["plant"][c]["observed_new_plants"]["self_absolute_mean"],
            "opp_new_visible":agg["plant"][c]["observed_new_plants"]["opponent_absolute_mean"],
            "self_closing_requests":agg["plant"][c]["closing_requests"]["self_absolute_mean"],
            "opp_closing_requests":agg["plant"][c]["closing_requests"]["opponent_absolute_mean"],
        } for c in CROPS}
    }
    print("SB01_DAY0_ALIGNED_ACTION_ALLOCATION "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
