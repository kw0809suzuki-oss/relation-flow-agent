#!/usr/bin/env python3
"""Day4 Composition -> Operating Burden -> Return Bridge v0.

No Candidate, Direction, score, or policy mutation.

The bridge is period-level and composition-level:
Day4 State composition
-> Day4-8 observed operating requirements
-> Day4-8 observed production / realization
-> surplus after operating burden
-> Day8 productive/future-value State

Cash is fungible: no item-level spend is claimed to fund any particular return.
"""
import glob,json,sys
from collections import defaultdict
from pathlib import Path

import analyze_sb01_economic_layers_v0 as econ

START_DAY=4
END_DAY=8


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def obs_at(raw,p,day):
    return raw["state_export"][str(p)][str(day)]["observation"]


def composition(obs,p):
    side=econ.derive_side(obs)
    farm=obs["farms"][p]
    private=obs.get("private",{}) or {}
    crops=side["committed_production"]["crop_count"]
    animals=side["committed_production"]["animal_count"]
    seeds=private.get("seeds",{}) or {}
    return {
        "cash":float(side["cash"]),
        "land_quadrants":len(farm.get("unlocked_quadrants",[]) or []),
        "empty_unlocked_tiles":int(side["uncommitted_capacity"]["empty_unlocked_tiles"]),
        "crop_count":{k:int(v) for k,v in crops.items()},
        "animal_count":{k:int(v) for k,v in animals.items()},
        "seed_stock":{k:int(v or 0) for k,v in seeds.items()},
        "productive_assets":int(sum(crops.values())+sum(animals.values())),
        "production_potential_mark":float(side["committed_production"]["same_basis_subtotal"]),
    }


def interval_events(raw,p):
    operating_spend_by_item=defaultdict(float)
    operating_qty_by_item=defaultdict(float)
    productive_spend_by_op=defaultdict(float)
    productive_spend_by_item=defaultdict(float)
    sell_cash_by_item=defaultdict(float)
    sell_qty_by_item=defaultdict(float)

    for e in raw.get("market_events",[]) or []:
        if int(e.get("player",-1))!=p:
            continue
        d=int(e.get("day",-1))
        if not (START_DAY<=d<END_DAY):
            continue
        op=str(e.get("op"))
        item=str(e.get("item")) if e.get("item") is not None else None
        delta=float(e.get("cash_delta",0) or 0)
        qty=float(e.get("qty",e.get("units",0)) or 0)

        if op=="BUY_PRODUCT":
            operating_spend_by_item[item]+=max(0.0,-delta)
            operating_qty_by_item[item]+=qty
        elif op in ("BUY_SEED","BUY_ANIMAL","BUY_LAND","HIRE"):
            v=max(0.0,-delta)
            productive_spend_by_op[op]+=v
            if item is not None:
                productive_spend_by_item[item]+=v
        elif op=="SELL":
            sell_cash_by_item[item]+=max(0.0,delta)
            sell_qty_by_item[item]+=qty

    production_units_by_item=defaultdict(float)
    for e in raw.get("production_events",[]) or []:
        if int(e.get("player",-1))!=p:
            continue
        d=int(e.get("result_state_day",e.get("transition_day",-1)))
        if START_DAY<d<=END_DAY:
            production_units_by_item[str(e.get("item"))]+=float(e.get("units",0) or 0)

    harvest_units_by_item=defaultdict(float)
    for e in raw.get("harvest_events",[]) or []:
        if int(e.get("player",-1))!=p:
            continue
        d=int(e.get("day",-1))
        if START_DAY<=d<END_DAY:
            harvest_units_by_item[str(e.get("item"))]+=float(e.get("units",0) or 0)

    operating_total=sum(operating_spend_by_item.values())
    sell_total=sum(sell_cash_by_item.values())
    productive_total=sum(productive_spend_by_op.values())

    return {
        "operating_spend_by_item":dict(sorted(operating_spend_by_item.items())),
        "operating_qty_by_item":dict(sorted(operating_qty_by_item.items())),
        "operating_spend_total":operating_total,
        "sell_cash_by_item":dict(sorted(sell_cash_by_item.items())),
        "sell_qty_by_item":dict(sorted(sell_qty_by_item.items())),
        "sell_cash_total":sell_total,
        "surplus_after_operating":sell_total-operating_total,
        "productive_spend_by_op":dict(sorted(productive_spend_by_op.items())),
        "productive_spend_by_item":dict(sorted(productive_spend_by_item.items())),
        "productive_spend_total":productive_total,
        "production_units_by_item":dict(sorted(production_units_by_item.items())),
        "production_units_total":sum(production_units_by_item.values()),
        "harvest_units_by_item":dict(sorted(harvest_units_by_item.items())),
        "harvest_units_total":sum(harvest_units_by_item.values()),
    }


def side_case(raw,p):
    d4=composition(obs_at(raw,p,4),p)
    flow=interval_events(raw,p)
    d8=composition(obs_at(raw,p,8),p)

    return {
        "day4":d4,
        "flow_day4_to_8":flow,
        "day8":d8,
        "growth":{
            "productive_assets":d8["productive_assets"]-d4["productive_assets"],
            "production_potential_mark":d8["production_potential_mark"]-d4["production_potential_mark"],
            "cash":d8["cash"]-d4["cash"],
            "land_quadrants":d8["land_quadrants"]-d4["land_quadrants"],
        }
    }


def union_keys(cases,path):
    keys=set()
    for c in cases:
        for side in ("self","opponent"):
            x=c[side]
            for k in path:
                x=x[k]
            keys.update(x.keys())
    return sorted(keys)


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
        "opponent_ahead_cases":sum(g>0 for g in gaps),
        "self_ahead_cases":sum(g<0 for g in gaps),
        "equal_cases":sum(g==0 for g in gaps),
    }


def pair_map(cases,path):
    keys=union_keys(cases,path)
    out={}
    for key in keys:
        sv=[];ov=[]
        for c in cases:
            xs=c["self"]; xo=c["opponent"]
            for k in path:
                xs=xs[k]; xo=xo[k]
            sv.append(float(xs.get(key,0) or 0))
            ov.append(float(xo.get(key,0) or 0))
        gaps=[b-a for a,b in zip(sv,ov)]
        out[key]={
            "self_absolute_mean":mean(sv),
            "opponent_absolute_mean":mean(ov),
            "mean_gap_opponent_minus_self":mean(gaps),
            "opponent_ahead_cases":sum(g>0 for g in gaps),
            "self_ahead_cases":sum(g<0 for g in gaps),
            "equal_cases":sum(g==0 for g in gaps),
        }
    return out


def composition_mean(cases,side,daykey):
    out={}
    for k in ("cash","land_quadrants","empty_unlocked_tiles","productive_assets","production_potential_mark"):
        vals=[float(c[side][daykey][k]) for c in cases]
        out[k]=mean(vals)
    for mapkey in ("crop_count","animal_count","seed_stock"):
        keys=set()
        for c in cases: keys.update(c[side][daykey][mapkey].keys())
        out[mapkey]={k:mean([float(c[side][daykey][mapkey].get(k,0) or 0) for c in cases]) for k in sorted(keys)}
    return out


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

    out={
        "schema":"kaggriculture.strong-origin-v2.composition-operating-return-bridge.v0",
        "battle_count":len(cases),
        "day4_composition":{
            "self":composition_mean(cases,"self","day4"),
            "opponent":composition_mean(cases,"opponent","day4"),
        },
        "flow_day4_to_8":{
            "operating_spend_total":pair_scalar(cases,["flow_day4_to_8","operating_spend_total"]),
            "operating_spend_by_item":pair_map(cases,["flow_day4_to_8","operating_spend_by_item"]),
            "operating_qty_by_item":pair_map(cases,["flow_day4_to_8","operating_qty_by_item"]),
            "production_units_total":pair_scalar(cases,["flow_day4_to_8","production_units_total"]),
            "production_units_by_item":pair_map(cases,["flow_day4_to_8","production_units_by_item"]),
            "harvest_units_total":pair_scalar(cases,["flow_day4_to_8","harvest_units_total"]),
            "harvest_units_by_item":pair_map(cases,["flow_day4_to_8","harvest_units_by_item"]),
            "sell_cash_total":pair_scalar(cases,["flow_day4_to_8","sell_cash_total"]),
            "sell_cash_by_item":pair_map(cases,["flow_day4_to_8","sell_cash_by_item"]),
            "surplus_after_operating":pair_scalar(cases,["flow_day4_to_8","surplus_after_operating"]),
            "productive_spend_total":pair_scalar(cases,["flow_day4_to_8","productive_spend_total"]),
            "productive_spend_by_op":pair_map(cases,["flow_day4_to_8","productive_spend_by_op"]),
        },
        "day8_composition":{
            "self":composition_mean(cases,"self","day8"),
            "opponent":composition_mean(cases,"opponent","day8"),
        },
        "growth_day4_to_8":{
            "productive_assets":pair_scalar(cases,["growth","productive_assets"]),
            "production_potential_mark":pair_scalar(cases,["growth","production_potential_mark"]),
            "cash":pair_scalar(cases,["growth","cash"]),
            "land_quadrants":pair_scalar(cases,["growth","land_quadrants"]),
        },
        "cases":cases,
        "boundary":[
            "No Candidate, Direction, score, or policy mutation is introduced.",
            "Operating burden is observed BUY_PRODUCT spend only; it is not pre-labelled good or bad.",
            "Item-level spend and item-level return are shown side by side but are not causally paired.",
            "Cash is fungible; no claim is made that a specific SELL funded a specific productive spend.",
            "Day4 composition is treated as starting State context, not as a proven cause of all interval outcomes.",
            "No asset is ranked or assigned causal status."
        ]
    }

    Path("composition_operating_return_bridge_v0.json").write_text(
        json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={
        "battle_count":len(cases),
        "day4":out["day4_composition"],
        "operating":out["flow_day4_to_8"]["operating_spend_by_item"],
        "production":out["flow_day4_to_8"]["production_units_by_item"],
        "harvest":out["flow_day4_to_8"]["harvest_units_by_item"],
        "sell":out["flow_day4_to_8"]["sell_cash_by_item"],
        "surplus":out["flow_day4_to_8"]["surplus_after_operating"],
        "productive_spend":out["flow_day4_to_8"]["productive_spend_by_op"],
        "day8":out["day8_composition"],
        "growth":out["growth_day4_to_8"],
    }
    print("COMPOSITION_OPERATING_RETURN_BRIDGE "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
