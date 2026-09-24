#!/usr/bin/env python3
"""Day4 Non-WHEAT Cohort Return Audit v0.

No Candidate, Direction, score, or policy mutation.

Cohorts are defined only by public origin time:
- existing cohort: asset_origin_day < 4
- new cohort:      4 <= asset_origin_day < 8

Current Return is observed Day4->8 production / harvest.
Future Return is Day8 remaining current-price production potential by cohort.

SELL remains item-level period realization only and is not assigned to cohorts
because inventory and Cash are fungible.
"""
import glob,json,sys
from collections import defaultdict
from pathlib import Path

import analyze_sb01_economic_layers_v0 as econ

START=4
END=8
NON_WHEAT_ITEMS=("MELON","STRAWBERRY","TOMATO","CARROT","MILK","WOOL","EGG","FERTILIZER")


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def cohort(origin):
    d=int(origin)
    if d<START: return "existing"
    if START<=d<END: return "new"
    return "other"


def day8_future(raw,p):
    obs=raw["state_export"][str(p)]["8"]["observation"]
    side=econ.derive_side(obs)
    out={
        "existing":{"mark":0.0,"potential_units":0.0,"asset_count":0.0,"by_item":defaultdict(lambda:{"mark":0.0,"potential_units":0.0,"asset_count":0.0})},
        "new":{"mark":0.0,"potential_units":0.0,"asset_count":0.0,"by_item":defaultdict(lambda:{"mark":0.0,"potential_units":0.0,"asset_count":0.0})},
    }
    cp=side["committed_production"]

    for x in cp["crop_detail"]:
        item=str(x["crop"])
        if item=="WHEAT": continue
        c=cohort(x["planted_day"])
        if c not in out: continue
        mark=float(x["current_price_potential_mark"])
        units=float(x["potential_units"])
        out[c]["mark"]+=mark; out[c]["potential_units"]+=units; out[c]["asset_count"]+=1
        b=out[c]["by_item"][item]
        b["mark"]+=mark; b["potential_units"]+=units; b["asset_count"]+=1

    for x in cp["animal_detail"]:
        product=str(x["product"])
        c=cohort(x["placed_day"])
        if c not in out: continue
        mark=float(x["current_price_potential_mark"])
        units=float(x["potential_product_units"])
        out[c]["mark"]+=mark; out[c]["potential_units"]+=units; out[c]["asset_count"]+=1
        b=out[c]["by_item"][product]
        b["mark"]+=mark; b["potential_units"]+=units; b["asset_count"]+=1

    for c in ("existing","new"):
        out[c]["by_item"]={k:dict(v) for k,v in sorted(out[c]["by_item"].items())}
    return out


def interval_returns(raw,p):
    production={
        "existing":{"units":0.0,"by_item":defaultdict(float)},
        "new":{"units":0.0,"by_item":defaultdict(float)},
    }
    harvest={
        "existing":{"units":0.0,"by_item":defaultdict(float)},
        "new":{"units":0.0,"by_item":defaultdict(float)},
    }

    for e in raw.get("production_events",[]) or []:
        if int(e.get("player",-1))!=p: continue
        d=int(e.get("result_state_day",e.get("transition_day",-1)))
        if not (START<d<=END): continue
        item=str(e.get("item"))
        if item=="WHEAT": continue
        c=cohort(e.get("asset_origin_day",999))
        if c not in production: continue
        u=float(e.get("units",0) or 0)
        production[c]["units"]+=u
        production[c]["by_item"][item]+=u

    for e in raw.get("harvest_events",[]) or []:
        if int(e.get("player",-1))!=p: continue
        d=int(e.get("day",-1))
        if not (START<=d<END): continue
        item=str(e.get("item"))
        if item=="WHEAT": continue
        c=cohort(e.get("asset_origin_day",999))
        if c not in harvest: continue
        u=float(e.get("units",0) or 0)
        harvest[c]["units"]+=u
        harvest[c]["by_item"][item]+=u

    sell=defaultdict(float)
    for e in raw.get("market_events",[]) or []:
        if int(e.get("player",-1))!=p or e.get("op")!="SELL": continue
        d=int(e.get("day",-1))
        if not (START<=d<END): continue
        item=str(e.get("item"))
        if item=="WHEAT": continue
        sell[item]+=max(0.0,float(e.get("cash_delta",0) or 0))

    for c in ("existing","new"):
        production[c]["by_item"]=dict(sorted(production[c]["by_item"].items()))
        harvest[c]["by_item"]=dict(sorted(harvest[c]["by_item"].items()))

    return {
        "production":production,
        "harvest":harvest,
        "non_wheat_sell_cash":dict(sorted(sell.items())),
        "non_wheat_sell_total":sum(sell.values()),
    }


def day4_nonwheat(raw,p):
    obs=raw["state_export"][str(p)]["4"]["observation"]
    side=econ.derive_side(obs)
    cp=side["committed_production"]
    return {
        "crop_count":{k:float(v) for k,v in cp["crop_count"].items() if k!="WHEAT" and v},
        "animal_count":{k:float(v) for k,v in cp["animal_count"].items() if v},
        "potential_mark_non_wheat":
            sum(float(v) for k,v in cp["crop_mark_by_type"].items() if k!="WHEAT")
            + sum(float(v) for v in cp["animal_mark_by_type"].values()),
    }


def side_case(raw,p):
    return {
        "day4_non_wheat":day4_nonwheat(raw,p),
        "current_return_day4_to_8":interval_returns(raw,p),
        "future_return_at_day8":day8_future(raw,p),
    }


def pair_scalar(cases,path):
    def get(c,side):
        x=c[side]
        for k in path: x=x[k]
        return float(x)
    s=[get(c,"self") for c in cases]
    o=[get(c,"opponent") for c in cases]
    g=[b-a for a,b in zip(s,o)]
    return {
        "self_absolute_mean":mean(s),
        "opponent_absolute_mean":mean(o),
        "mean_gap_opponent_minus_self":mean(g),
        "opponent_ahead_cases":sum(x>0 for x in g),
        "self_ahead_cases":sum(x<0 for x in g),
        "equal_cases":sum(x==0 for x in g),
    }


def union_map_keys(cases,path):
    keys=set()
    for c in cases:
        for side in ("self","opponent"):
            x=c[side]
            for k in path: x=x[k]
            keys.update(x.keys())
    return sorted(keys)


def pair_map(cases,path):
    out={}
    for key in union_map_keys(cases,path):
        s=[];o=[]
        for c in cases:
            xs=c["self"];xo=c["opponent"]
            for k in path: xs=xs[k];xo=xo[k]
            s.append(float(xs.get(key,0) or 0))
            o.append(float(xo.get(key,0) or 0))
        g=[b-a for a,b in zip(s,o)]
        out[key]={
            "self_absolute_mean":mean(s),
            "opponent_absolute_mean":mean(o),
            "mean_gap_opponent_minus_self":mean(g),
            "opponent_ahead_cases":sum(x>0 for x in g),
            "self_ahead_cases":sum(x<0 for x in g),
            "equal_cases":sum(x==0 for x in g),
        }
    return out


def composition_mean(cases,side):
    crop_keys=set();animal_keys=set()
    for c in cases:
        crop_keys.update(c[side]["day4_non_wheat"]["crop_count"].keys())
        animal_keys.update(c[side]["day4_non_wheat"]["animal_count"].keys())
    return {
        "crop_count":{k:mean([float(c[side]["day4_non_wheat"]["crop_count"].get(k,0) or 0) for c in cases]) for k in sorted(crop_keys)},
        "animal_count":{k:mean([float(c[side]["day4_non_wheat"]["animal_count"].get(k,0) or 0) for c in cases]) for k in sorted(animal_keys)},
        "potential_mark_non_wheat":mean([float(c[side]["day4_non_wheat"]["potential_mark_non_wheat"]) for c in cases]),
    }


def future_item_metric(cases,cohort_name,metric):
    keys=set()
    for c in cases:
        for side in ("self","opponent"):
            keys.update(c[side]["future_return_at_day8"][cohort_name]["by_item"].keys())
    out={}
    for item in sorted(keys):
        s=[];o=[]
        for c in cases:
            s.append(float(c["self"]["future_return_at_day8"][cohort_name]["by_item"].get(item,{}).get(metric,0) or 0))
            o.append(float(c["opponent"]["future_return_at_day8"][cohort_name]["by_item"].get(item,{}).get(metric,0) or 0))
        g=[b-a for a,b in zip(s,o)]
        out[item]={
            "self_absolute_mean":mean(s),"opponent_absolute_mean":mean(o),
            "mean_gap_opponent_minus_self":mean(g),
            "opponent_ahead_cases":sum(x>0 for x in g),
            "self_ahead_cases":sum(x<0 for x in g),
            "equal_cases":sum(x==0 for x in g),
        }
    return out


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/state_transition_growth_audit_v0_*.json"))
    if not files:
        files=[Path(p) for p in glob.glob(str(root/"**"/"state_transition_growth_audit_v0_*.json"),recursive=True)]
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    if not raws: raise SystemExit("No raw audit files")
    raws.sort(key=lambda r:int(r["seed"]))

    cases=[]
    for raw in raws:
        seat=int(raw["seat"])
        cases.append({
            "seed":int(raw["seed"]),"seat":seat,
            "self":side_case(raw,seat),
            "opponent":side_case(raw,1-seat),
        })

    current={}
    future={}
    for c in ("existing","new"):
        current[c]={
            "production_units":pair_scalar(cases,["current_return_day4_to_8","production",c,"units"]),
            "production_by_item":pair_map(cases,["current_return_day4_to_8","production",c,"by_item"]),
            "harvest_units":pair_scalar(cases,["current_return_day4_to_8","harvest",c,"units"]),
            "harvest_by_item":pair_map(cases,["current_return_day4_to_8","harvest",c,"by_item"]),
        }
        future[c]={
            "potential_mark":pair_scalar(cases,["future_return_at_day8",c,"mark"]),
            "potential_units":pair_scalar(cases,["future_return_at_day8",c,"potential_units"]),
            "asset_count":pair_scalar(cases,["future_return_at_day8",c,"asset_count"]),
            "potential_mark_by_item":future_item_metric(cases,c,"mark"),
            "potential_units_by_item":future_item_metric(cases,c,"potential_units"),
        }

    out={
        "schema":"kaggriculture.strong-origin-v2.day4-nonwheat-cohort-return-audit.v0",
        "battle_count":len(cases),
        "day4_non_wheat_composition":{
            "self":composition_mean(cases,"self"),
            "opponent":composition_mean(cases,"opponent"),
        },
        "current_return_day4_to_8":current,
        "period_non_wheat_sell_cash":{
            "total":pair_scalar(cases,["current_return_day4_to_8","non_wheat_sell_total"]),
            "by_item":pair_map(cases,["current_return_day4_to_8","non_wheat_sell_cash"]),
        },
        "future_return_at_day8":future,
        "cases":cases,
        "boundary":[
            "No Candidate, Direction, score, or policy mutation is introduced.",
            "Existing cohort means public asset_origin_day < 4; new cohort means 4 <= asset_origin_day < 8.",
            "Production and harvest can be attributed to cohort by public asset origin time.",
            "SELL is not attributed to cohort because inventory and Cash are fungible.",
            "Day8 future return is current-price remaining production potential, not guaranteed realized profit.",
            "No asset is ranked or declared independently causal."
        ]
    }
    Path("day4_nonwheat_cohort_return_audit_v0.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    compact={
        "battle_count":len(cases),
        "day4":out["day4_non_wheat_composition"],
        "current":current,
        "sell":out["period_non_wheat_sell_cash"],
        "future":future,
    }
    print("DAY4_NONWHEAT_COHORT_RETURN_AUDIT "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
