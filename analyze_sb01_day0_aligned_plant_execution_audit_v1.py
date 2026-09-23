#!/usr/bin/env python3
"""SB-01 Day0 aligned PLANT execution audit v1.

Consumes aligned pre-State -> Action -> post-State data from Run 35836285226.
Applies public PLANT rules to every Day0 transition, including the closing
Day0 hour23 -> Day1 hour0 transition.

This is deterministic execution accounting, not strategy interpretation.
"""
import copy, json, statistics, sys
from pathlib import Path
from collections import Counter

CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")


def side_audit(raw,seat):
    key=f"seat{seat}"
    totals={c:Counter() for c in CROPS}
    details=[]

    for tr in raw["transitions"]:
        pre=tr[key]["pre_observation"]
        act=tr[key]["action"] or {}
        player=int(pre.get("player",seat))
        farm=pre["farms"][player]
        private=pre.get("private",{}) or {}

        positions=[tuple(farm.get("farmer",[0,0]))]+[tuple(p) for p in (farm.get("hands",[]) or [])]
        actions=[act.get("farmer",["PASS"])]
        ha=act.get("hands",[])
        if isinstance(ha,list): actions.extend(ha)

        demand=Counter()
        for a in actions:
            if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS:
                demand[a[1]]+=1

        seeds={c:int((private.get("seeds",{}) or {}).get(c,0) or 0) for c in CROPS}
        blocked={c for c,n in demand.items() if n>seeds[c]}
        tiles=copy.deepcopy(farm.get("tiles",[]) or [])
        turn=Counter()

        for idx,a in enumerate(actions):
            if not (isinstance(a,list) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS):
                continue
            crop=a[1]
            totals[crop]["issued"]+=1
            turn[(crop,"issued")]+=1

            if crop in blocked:
                totals[crop]["atomic_seed_blocked"]+=1
                turn[(crop,"atomic_seed_blocked")]+=1
                continue
            if idx>=len(positions):
                totals[crop]["missing_unit"]+=1
                turn[(crop,"missing_unit")]+=1
                continue

            x,y=positions[idx]
            tile=tiles[y][x]
            if tile=="LOCKED":
                totals[crop]["locked_tile"]+=1
                turn[(crop,"locked_tile")]+=1
                continue
            if tile is not None:
                totals[crop]["occupied_tile"]+=1
                turn[(crop,"occupied_tile")]+=1
                continue
            if seeds[crop]<=0:
                totals[crop]["seed_depleted"]+=1
                turn[(crop,"seed_depleted")]+=1
                continue

            tiles[y][x]={"kind":"PLANT","crop":crop,"planted_day":0}
            seeds[crop]-=1
            totals[crop]["rule_valid_execution"]+=1
            turn[(crop,"rule_valid_execution")]+=1

        if demand:
            details.append({
                "from":tr["from"],"to":tr["to"],
                "demand":dict(demand),
                "seed_at_pre":{c:int((private.get("seeds",{}) or {}).get(c,0) or 0) for c in demand},
                "blocked_crops":sorted(blocked),
                "results":{f"{c}:{k}":v for (c,k),v in turn.items()},
            })

    for c in CROPS:
        for k in ("issued","rule_valid_execution","atomic_seed_blocked","occupied_tile","locked_tile","seed_depleted","missing_unit"):
            totals[c][k]+=0
    return {c:dict(totals[c]) for c in CROPS},details


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
    for p in files:
        raw=json.loads(p.read_text(encoding="utf-8"))
        seat=int(raw["seat"])
        sa,sd=side_audit(raw,seat)
        oa,od=side_audit(raw,1-seat)
        cases.append({"seed":int(raw["seed"]),"self":sa,"opponent":oa,"self_details":sd,"opponent_details":od})

    metrics=("issued","rule_valid_execution","atomic_seed_blocked","occupied_tile","locked_tile","seed_depleted","missing_unit")
    agg={}
    for crop in CROPS:
        agg[crop]={m:summ(cases,lambda s,c=crop,k=m:s[c][k]) for m in metrics}

    payload={
        "schema":"kaggriculture.sb01.day0-aligned-plant-execution-audit.v1",
        "source_run_id":35836285226,
        "battle_count":len(cases),
        "aggregate":agg,
        "cases":cases,
        "rule_basis":[
            "Per-turn atomic PLANT validation: if same-crop PLANT demand exceeds pre-State seed count, all requests for that crop are blocked.",
            "PLANT requires an owned empty tile.",
            "Successful PLANT consumes one seed and occupies the unit's current tile.",
            "Unit order is main farmer then hands."
        ],
        "boundary":[
            "All transitions are explicitly aligned pre-State -> Action -> post-State.",
            "rule_valid_execution is a deterministic rule calculation before end-of-day refresh.",
            "No strategic value or causal explanation is inferred."
        ]
    }
    Path("sb01_day0_aligned_plant_execution_audit_v1.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    compact={c:{
        "self_issued":agg[c]["issued"]["self_absolute_mean"],
        "opp_issued":agg[c]["issued"]["opponent_absolute_mean"],
        "self_valid":agg[c]["rule_valid_execution"]["self_absolute_mean"],
        "opp_valid":agg[c]["rule_valid_execution"]["opponent_absolute_mean"],
        "self_seed_blocked":agg[c]["atomic_seed_blocked"]["self_absolute_mean"],
        "opp_seed_blocked":agg[c]["atomic_seed_blocked"]["opponent_absolute_mean"],
        "self_occupied":agg[c]["occupied_tile"]["self_absolute_mean"],
        "opp_occupied":agg[c]["occupied_tile"]["opponent_absolute_mean"],
        "self_locked":agg[c]["locked_tile"]["self_absolute_mean"],
        "opp_locked":agg[c]["locked_tile"]["opponent_absolute_mean"],
    } for c in CROPS}
    print("SB01_DAY0_ALIGNED_PLANT_EXECUTION "+json.dumps({"battle_count":len(cases),"crops":compact},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
