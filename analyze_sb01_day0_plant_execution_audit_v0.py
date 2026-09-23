#!/usr/bin/env python3
"""SB-01 Day0 PLANT Execution Audit v0.

Deterministically evaluates Day0 PLANT requests using the public PLANT rules:
- atomic per-crop demand <= available seeds at turn start
- target tile must be owned and empty
- unit order is main farmer, then hands
- successful PLANT consumes one seed and occupies that tile

This audit does not infer strategy. It separates issued PLANT requests from
rule-valid executions.
"""
import copy, json, statistics, sys
from pathlib import Path
from collections import Counter

CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")


def get_player_state(obs, seat):
    player=int(obs.get("player",seat))
    return obs["farms"][player], obs.get("private",{}) or {}


def unit_positions(farm):
    return [tuple(farm.get("farmer",[0,0]))] + [tuple(p) for p in (farm.get("hands",[]) or [])]


def tile_at(tiles,pos):
    x,y=pos
    return tiles[y][x]


def audit_side(raw, seat):
    key=f"seat{seat}"
    totals={c:Counter() for c in CROPS}
    per_turn=[]

    for row in raw["day0_steps"]:
        obs=(row[key] or {}).get("observation") or {}
        act=(row[key] or {}).get("action") or {}
        if not isinstance(obs,dict) or not isinstance(act,dict):
            continue

        farm,private=get_player_state(obs,seat)
        positions=unit_positions(farm)
        actions=[act.get("farmer",["PASS"])]
        ha=act.get("hands",[])
        if isinstance(ha,list): actions.extend(ha)

        seeds=copy.deepcopy(private.get("seeds",{}) or {})
        tiles=copy.deepcopy(farm.get("tiles",[]) or [])

        demand=Counter()
        for a in actions:
            if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS:
                demand[a[1]]+=1

        blocked={c for c,n in demand.items() if n>int(seeds.get(c,0) or 0)}
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
                totals[crop]["missing_unit_position"]+=1
                turn[(crop,"missing_unit_position")]+=1
                continue
            pos=positions[idx]
            tile=tile_at(tiles,pos)
            if tile=="LOCKED":
                totals[crop]["locked_tile"]+=1
                turn[(crop,"locked_tile")]+=1
                continue
            if tile is not None:
                totals[crop]["occupied_tile"]+=1
                turn[(crop,"occupied_tile")]+=1
                continue
            if int(seeds.get(crop,0) or 0)<=0:
                totals[crop]["seed_depleted"]+=1
                turn[(crop,"seed_depleted")]+=1
                continue

            # Rule-valid PLANT execution.
            x,y=pos
            tiles[y][x]={"kind":"PLANT","crop":crop,"planted_day":0}
            seeds[crop]=int(seeds.get(crop,0) or 0)-1
            totals[crop]["rule_valid_execution"]+=1
            turn[(crop,"rule_valid_execution")]+=1

        if demand:
            per_turn.append({
                "hour":int(row["hour"]),
                "demand":dict(demand),
                "available_seed_at_turn_start":{c:int((private.get("seeds",{}) or {}).get(c,0) or 0) for c in demand},
                "blocked_crops":sorted(blocked),
                "results":{f"{c}:{k}":v for (c,k),v in turn.items()},
            })

    for c in CROPS:
        for k in ("issued","rule_valid_execution","atomic_seed_blocked","occupied_tile","locked_tile","seed_depleted","missing_unit_position"):
            totals[c][k]+=0
    return {c:dict(totals[c]) for c in CROPS}, per_turn


def day1_surviving(obs):
    player=int(obs.get("player",0))
    farm=obs["farms"][player]
    out={c:0 for c in CROPS}
    for row in farm.get("tiles",[]) or []:
        for tile in row or []:
            if isinstance(tile,dict):
                c=tile.get("crop")
                if c in out and int(tile.get("planted_day",-999))==0:
                    out[c]+=1
    return out


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
        sa,st=audit_side(raw,seat)
        oa,ot=audit_side(raw,opp)
        ss=day1_surviving(raw["day1_first"][str(seat)]["observation"])
        os=day1_surviving(raw["day1_first"][str(opp)]["observation"])
        cases.append({
            "seed":int(raw["seed"]),
            "self":{"audit":sa,"turns":st,"day1_surviving":ss},
            "opponent":{"audit":oa,"turns":ot,"day1_surviving":os},
        })

    agg={}
    metrics=("issued","rule_valid_execution","atomic_seed_blocked","occupied_tile","locked_tile","seed_depleted","missing_unit_position")
    for crop in CROPS:
        agg[crop]={}
        for m in metrics:
            agg[crop][m]=summarize(cases,lambda s,c=crop,k=m:s["audit"][c][k])
        agg[crop]["day1_surviving"]=summarize(cases,lambda s,c=crop:s["day1_surviving"][c])
        agg[crop]["valid_but_not_day1_surviving"]=summarize(
            cases,lambda s,c=crop:s["audit"][c]["rule_valid_execution"]-s["day1_surviving"][c]
        )

    payload={
        "schema":"kaggriculture.sb01.day0-plant-execution-audit.v0",
        "source_run_id":35831478953,
        "battle_count":len(cases),
        "aggregate":agg,
        "cases":cases,
        "rule_basis":[
            "Atomic PLANT validation blocks all same-crop PLANT requests in a turn when demand exceeds available seeds.",
            "PLANT requires an owned empty tile and consumes one seed.",
            "Unit action order is main farmer then hands."
        ],
        "boundary":[
            "rule_valid_execution is deterministic under the stated public PLANT rules and retained State.",
            "valid_but_not_day1_surviving means a rule-valid Day0 PLANT is absent at first Day1 State; this audit does not yet assign the disappearance mechanism.",
            "No strategic cause or policy recommendation is inferred."
        ]
    }
    Path("sb01_day0_plant_execution_audit_v0.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    compact={
        c:{
            "self_issued":agg[c]["issued"]["self_absolute_mean"],
            "opp_issued":agg[c]["issued"]["opponent_absolute_mean"],
            "self_valid":agg[c]["rule_valid_execution"]["self_absolute_mean"],
            "opp_valid":agg[c]["rule_valid_execution"]["opponent_absolute_mean"],
            "self_atomic_blocked":agg[c]["atomic_seed_blocked"]["self_absolute_mean"],
            "opp_atomic_blocked":agg[c]["atomic_seed_blocked"]["opponent_absolute_mean"],
            "self_occupied":agg[c]["occupied_tile"]["self_absolute_mean"],
            "opp_occupied":agg[c]["occupied_tile"]["opponent_absolute_mean"],
            "self_day1_surviving":agg[c]["day1_surviving"]["self_absolute_mean"],
            "opp_day1_surviving":agg[c]["day1_surviving"]["opponent_absolute_mean"],
            "self_valid_lost_before_day1":agg[c]["valid_but_not_day1_surviving"]["self_absolute_mean"],
            "opp_valid_lost_before_day1":agg[c]["valid_but_not_day1_surviving"]["opponent_absolute_mean"],
        } for c in CROPS
    }
    print("SB01_DAY0_PLANT_EXECUTION_AUDIT "+json.dumps({"battle_count":len(cases),"crops":compact},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
