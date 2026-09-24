#!/usr/bin/env python3
"""Cohort Generation Amplification Audit v0.

No Candidate, Direction, score, or policy mutation.

Purpose:
Check whether economic thickness grows across 4-day cohort generations.

Generation windows:
- G0: asset_origin_day in [0,4)
- G1: asset_origin_day in [4,8)
- G2: asset_origin_day in [8,12)

For each boundary (Day4, Day8, Day12), report remaining future value by
generation. For each cycle, report production/harvest by generation and whether
the cohort created in the previous cycle becomes a larger returning cohort in
the next cycle.

SELL stays period-level only and is never attributed to a cohort.
"""
import glob,json,sys
from collections import defaultdict
from pathlib import Path

import analyze_sb01_economic_layers_v0 as econ

GENERATIONS={
    "G0":(0,4),
    "G1":(4,8),
    "G2":(8,12),
}
BOUNDARIES=(4,8,12)
CYCLES=((0,4),(4,8),(8,12))


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def generation(origin_day):
    d=int(origin_day)
    for g,(a,b) in GENERATIONS.items():
        if a<=d<b:
            return g
    if d<0:
        return "PRE"
    return "OTHER"


def future_by_generation(raw,p,day):
    obs=raw["state_export"][str(p)][str(day)]["observation"]
    side=econ.derive_side(obs)
    cp=side["committed_production"]
    out={g:{
        "asset_count":0.0,
        "potential_units":0.0,
        "potential_mark":0.0,
        "by_item":defaultdict(lambda:{"asset_count":0.0,"potential_units":0.0,"potential_mark":0.0}),
    } for g in GENERATIONS}

    for x in cp["crop_detail"]:
        item=str(x["crop"])
        if item=="WHEAT":
            continue
        g=generation(x["planted_day"])
        if g not in out:
            continue
        vals={
            "asset_count":1.0,
            "potential_units":float(x["potential_units"]),
            "potential_mark":float(x["current_price_potential_mark"]),
        }
        for k,v in vals.items():
            out[g][k]+=v
            out[g]["by_item"][item][k]+=v

    for x in cp["animal_detail"]:
        item=str(x["product"])
        g=generation(x["placed_day"])
        if g not in out:
            continue
        vals={
            "asset_count":1.0,
            "potential_units":float(x["potential_product_units"]),
            "potential_mark":float(x["current_price_potential_mark"]),
        }
        for k,v in vals.items():
            out[g][k]+=v
            out[g]["by_item"][item][k]+=v

    for g in out:
        out[g]["by_item"]={k:dict(v) for k,v in sorted(out[g]["by_item"].items())}
    return out


def cycle_returns(raw,p,start,end):
    prod={g:{"units":0.0,"by_item":defaultdict(float)} for g in GENERATIONS}
    harvest={g:{"units":0.0,"by_item":defaultdict(float)} for g in GENERATIONS}

    for e in raw.get("production_events",[]) or []:
        if int(e.get("player",-1))!=p:
            continue
        d=int(e.get("result_state_day",e.get("transition_day",-1)))
        if not (start<d<=end):
            continue
        item=str(e.get("item"))
        if item=="WHEAT":
            continue
        g=generation(e.get("asset_origin_day",999))
        if g not in prod:
            continue
        u=float(e.get("units",0) or 0)
        prod[g]["units"]+=u
        prod[g]["by_item"][item]+=u

    for e in raw.get("harvest_events",[]) or []:
        if int(e.get("player",-1))!=p:
            continue
        d=int(e.get("day",-1))
        if not (start<=d<end):
            continue
        item=str(e.get("item"))
        if item=="WHEAT":
            continue
        g=generation(e.get("asset_origin_day",999))
        if g not in harvest:
            continue
        u=float(e.get("units",0) or 0)
        harvest[g]["units"]+=u
        harvest[g]["by_item"][item]+=u

    sell=defaultdict(float)
    for e in raw.get("market_events",[]) or []:
        if int(e.get("player",-1))!=p or e.get("op")!="SELL":
            continue
        d=int(e.get("day",-1))
        if not (start<=d<end):
            continue
        item=str(e.get("item"))
        if item=="WHEAT":
            continue
        sell[item]+=max(0.0,float(e.get("cash_delta",0) or 0))

    for bucket in (prod,harvest):
        for g in bucket:
            bucket[g]["by_item"]=dict(sorted(bucket[g]["by_item"].items()))

    return {
        "production":prod,
        "harvest":harvest,
        "non_wheat_sell_cash":dict(sorted(sell.items())),
        "non_wheat_sell_total":sum(sell.values()),
    }


def side_case(raw,p):
    future={str(day):future_by_generation(raw,p,day) for day in BOUNDARIES}
    cycles={}
    for start,end in CYCLES:
        cycles[f"{start}_{end}"]=cycle_returns(raw,p,start,end)
    return {"future":future,"cycles":cycles}


def pair_scalar(cases,path):
    def get(c,side):
        x=c[side]
        for k in path:
            x=x[k]
        return float(x)
    s=[get(c,"self") for c in cases]
    o=[get(c,"opponent") for c in cases]
    gaps=[b-a for a,b in zip(s,o)]
    return {
        "self_absolute_mean":mean(s),
        "opponent_absolute_mean":mean(o),
        "mean_gap_opponent_minus_self":mean(gaps),
        "opponent_ahead_cases":sum(x>0 for x in gaps),
        "self_ahead_cases":sum(x<0 for x in gaps),
        "equal_cases":sum(x==0 for x in gaps),
    }


def pair_map(cases,path):
    keys=set()
    for c in cases:
        for side in ("self","opponent"):
            x=c[side]
            for k in path:
                x=x[k]
            keys.update(x.keys())
    out={}
    for item in sorted(keys):
        s=[];o=[]
        for c in cases:
            xs=c["self"];xo=c["opponent"]
            for k in path:
                xs=xs[k];xo=xo[k]
            s.append(float(xs.get(item,0) or 0))
            o.append(float(xo.get(item,0) or 0))
        gaps=[b-a for a,b in zip(s,o)]
        out[item]={
            "self_absolute_mean":mean(s),
            "opponent_absolute_mean":mean(o),
            "mean_gap_opponent_minus_self":mean(gaps),
            "opponent_ahead_cases":sum(x>0 for x in gaps),
            "self_ahead_cases":sum(x<0 for x in gaps),
            "equal_cases":sum(x==0 for x in gaps),
        }
    return out


def future_summary(cases,day,g):
    base=["future",str(day),g]
    return {
        "asset_count":pair_scalar(cases,base+["asset_count"]),
        "potential_units":pair_scalar(cases,base+["potential_units"]),
        "potential_mark":pair_scalar(cases,base+["potential_mark"]),
    }


def cycle_summary(cases,start,end,g):
    key=f"{start}_{end}"
    base=["cycles",key]
    return {
        "production_units":pair_scalar(cases,base+["production",g,"units"]),
        "production_by_item":pair_map(cases,base+["production",g,"by_item"]),
        "harvest_units":pair_scalar(cases,base+["harvest",g,"units"]),
        "harvest_by_item":pair_map(cases,base+["harvest",g,"by_item"]),
    }


def generation_chain(cases,side,g,birth_boundary,next_cycle,next_boundary):
    # absolute means only; no ratio score is adopted.
    f_birth=[]
    next_prod=[]
    f_next=[]
    for c in cases:
        f_birth.append(float(c[side]["future"][str(birth_boundary)][g]["potential_mark"]))
        key=f"{next_cycle[0]}_{next_cycle[1]}"
        next_prod.append(float(c[side]["cycles"][key]["production"][g]["units"]))
        f_next.append(float(c[side]["future"][str(next_boundary)][g]["potential_mark"]))
    return {
        "future_mark_at_birth_boundary_mean":mean(f_birth),
        "next_cycle_production_units_mean":mean(next_prod),
        "future_mark_after_next_cycle_mean":mean(f_next),
    }


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/state_transition_growth_audit_v0_*.json"))
    if not files:
        files=[Path(p) for p in glob.glob(str(root/"**"/"state_transition_growth_audit_v0_*.json"),recursive=True)]
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    if not raws:
        raise SystemExit("No raw audit files")
    raws.sort(key=lambda r:int(r["seed"]))

    cases=[]
    for raw in raws:
        seat=int(raw["seat"])
        cases.append({
            "seed":int(raw["seed"]),
            "seat":seat,
            "self":side_case(raw,seat),
            "opponent":side_case(raw,1-seat),
        })

    future={}
    for day in BOUNDARIES:
        future[str(day)]={g:future_summary(cases,day,g) for g in GENERATIONS}

    cycles={}
    for start,end in CYCLES:
        cycles[f"{start}_{end}"]={g:cycle_summary(cases,start,end,g) for g in GENERATIONS}
        cycles[f"{start}_{end}"]["period_non_wheat_sell_cash"]={
            "total":pair_scalar(cases,["cycles",f"{start}_{end}","non_wheat_sell_total"]),
            "by_item":pair_map(cases,["cycles",f"{start}_{end}","non_wheat_sell_cash"]),
        }

    chains={
        "G0":{
            "self":generation_chain(cases,"self","G0",4,(4,8),8),
            "opponent":generation_chain(cases,"opponent","G0",4,(4,8),8),
        },
        "G1":{
            "self":generation_chain(cases,"self","G1",8,(8,12),12),
            "opponent":generation_chain(cases,"opponent","G1",8,(8,12),12),
        },
    }

    out={
        "schema":"kaggriculture.strong-origin-v2.cohort-generation-amplification-audit.v0",
        "battle_count":len(cases),
        "future_by_boundary":future,
        "cycle_returns":cycles,
        "generation_chains":chains,
        "cases":cases,
        "boundary":[
            "No Candidate, Direction, score, or policy mutation is introduced.",
            "G0/G1/G2 are public origin-day windows [0,4), [4,8), [8,12).",
            "Production and harvest are cohort-attributed by public asset origin day.",
            "SELL remains period-level and is never cohort-attributed.",
            "Future potential uses Day-boundary current-price remaining production potential; price changes can affect marks.",
            "Potential units and asset counts are retained alongside marks to avoid treating valuation movement as physical growth.",
            "No amplification ratio or ranking score is adopted."
        ]
    }
    Path("cohort_generation_amplification_audit_v0.json").write_text(
        json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={
        "battle_count":len(cases),
        "future":future,
        "cycles":cycles,
        "chains":chains,
    }
    print("COHORT_GENERATION_AMPLIFICATION_AUDIT "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
