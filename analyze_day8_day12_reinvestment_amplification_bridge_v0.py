#!/usr/bin/env python3
"""Day8->12 Reinvestment Amplification Bridge v0.

No Candidate, Direction, score, or policy mutation.

Question:
Starting from already-different Day8 States, at which observed connection does
self's second-cycle amplification become materially thinner?

Bridge:
Day8 State
-> Day8-12 Current Return
-> Operating Burden
-> Surplus
-> Productive Spend
-> G2 physical future capacity
-> Day12 State

Cash is fungible. No SELL is assigned as funding a specific investment.
"""
import glob,json,sys
from collections import defaultdict
from pathlib import Path

import analyze_sb01_economic_layers_v0 as econ

START=8
END=12
PRODUCTIVE_OPS=("BUY_SEED","BUY_ANIMAL","BUY_LAND","HIRE")


def mean(xs): return sum(xs)/len(xs) if xs else None


def derive_state(raw,p,day):
    obs=raw["state_export"][str(p)][str(day)]["observation"]
    side=econ.derive_side(obs)
    cp=side["committed_production"]

    g0_units=g1_units=g2_units=0.0
    g0_assets=g1_assets=g2_assets=0.0
    g0_mark=g1_mark=g2_mark=0.0

    def bucket(origin):
        d=int(origin)
        if 0<=d<4:return "G0"
        if 4<=d<8:return "G1"
        if 8<=d<12:return "G2"
        return None

    for x in cp["crop_detail"]:
        if x["crop"]=="WHEAT": continue
        b=bucket(x["planted_day"])
        if not b: continue
        units=float(x["potential_units"]); mark=float(x["current_price_potential_mark"])
        if b=="G0": g0_units+=units;g0_assets+=1;g0_mark+=mark
        elif b=="G1": g1_units+=units;g1_assets+=1;g1_mark+=mark
        else: g2_units+=units;g2_assets+=1;g2_mark+=mark

    for x in cp["animal_detail"]:
        b=bucket(x["placed_day"])
        if not b: continue
        units=float(x["potential_product_units"]); mark=float(x["current_price_potential_mark"])
        if b=="G0": g0_units+=units;g0_assets+=1;g0_mark+=mark
        elif b=="G1": g1_units+=units;g1_assets+=1;g1_mark+=mark
        else: g2_units+=units;g2_assets+=1;g2_mark+=mark

    farm=obs["farms"][p]
    return {
        "cash":float(side["cash"]),
        "land_quadrants":len(farm.get("unlocked_quadrants",[]) or []),
        "productive_assets":float(sum(cp["crop_count"].values())+sum(cp["animal_count"].values())),
        "production_potential_mark":float(cp["same_basis_subtotal"]),
        "non_wheat_future_units":{"G0":g0_units,"G1":g1_units,"G2":g2_units},
        "non_wheat_asset_count":{"G0":g0_assets,"G1":g1_assets,"G2":g2_assets},
        "non_wheat_future_mark":{"G0":g0_mark,"G1":g1_mark,"G2":g2_mark},
    }


def interval_flow(raw,p):
    sell=defaultdict(float)
    operating=defaultdict(float)
    productive_by_op=defaultdict(float)
    productive_by_item=defaultdict(float)

    for e in raw.get("market_events",[]) or []:
        if int(e.get("player",-1))!=p: continue
        d=int(e.get("day",-1))
        if not (START<=d<END): continue
        op=str(e.get("op"))
        item=str(e.get("item")) if e.get("item") is not None else None
        delta=float(e.get("cash_delta",0) or 0)
        if op=="SELL":
            sell[item]+=max(0.0,delta)
        elif op=="BUY_PRODUCT":
            operating[item]+=max(0.0,-delta)
        elif op in PRODUCTIVE_OPS:
            v=max(0.0,-delta)
            productive_by_op[op]+=v
            if item is not None: productive_by_item[item]+=v

    production_by_gen=defaultdict(float)
    production_by_gen_item=defaultdict(lambda:defaultdict(float))
    for e in raw.get("production_events",[]) or []:
        if int(e.get("player",-1))!=p: continue
        d=int(e.get("result_state_day",e.get("transition_day",-1)))
        if not (START<d<=END): continue
        origin=int(e.get("asset_origin_day",999))
        if 0<=origin<4:g="G0"
        elif 4<=origin<8:g="G1"
        elif 8<=origin<12:g="G2"
        else:continue
        item=str(e.get("item"))
        u=float(e.get("units",0) or 0)
        production_by_gen[g]+=u
        production_by_gen_item[g][item]+=u

    sell_total=sum(sell.values())
    operating_total=sum(operating.values())
    productive_total=sum(productive_by_op.values())
    return {
        "sell_cash_total":sell_total,
        "sell_cash_by_item":dict(sorted(sell.items())),
        "operating_spend_total":operating_total,
        "operating_spend_by_item":dict(sorted(operating.items())),
        "surplus_after_operating":sell_total-operating_total,
        "productive_spend_total":productive_total,
        "productive_spend_by_op":dict(sorted(productive_by_op.items())),
        "productive_spend_by_item":dict(sorted(productive_by_item.items())),
        "production_units_by_generation":dict(production_by_gen),
        "production_units_by_generation_item":{g:dict(sorted(v.items())) for g,v in sorted(production_by_gen_item.items())},
    }


def side_case(raw,p):
    d8=derive_state(raw,p,8)
    flow=interval_flow(raw,p)
    d12=derive_state(raw,p,12)
    return {
        "day8":d8,
        "flow":flow,
        "g2":{
            "asset_count":d12["non_wheat_asset_count"]["G2"],
            "future_units":d12["non_wheat_future_units"]["G2"],
            "future_mark":d12["non_wheat_future_mark"]["G2"],
        },
        "day12":d12,
        "growth":{
            "cash":d12["cash"]-d8["cash"],
            "productive_assets":d12["productive_assets"]-d8["productive_assets"],
            "production_potential_mark":d12["production_potential_mark"]-d8["production_potential_mark"],
            "non_wheat_future_units_total":
                sum(d12["non_wheat_future_units"].values())-sum(d8["non_wheat_future_units"].values()),
        }
    }


def pair_scalar(cases,path):
    def get(c,side):
        x=c[side]
        for k in path:
            if isinstance(x,dict) and k not in x:
                return 0.0
            x=x[k]
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


def pair_map(cases,path):
    keys=set()
    for c in cases:
        for side in ("self","opponent"):
            x=c[side]
            for k in path:x=x[k]
            keys.update(x.keys())
    out={}
    for key in sorted(keys):
        s=[];o=[]
        for c in cases:
            xs=c["self"];xo=c["opponent"]
            for k in path:xs=xs[k];xo=xo[k]
            s.append(float(xs.get(key,0) or 0));o.append(float(xo.get(key,0) or 0))
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


def side_means(cases,side,path_keys):
    vals={}
    for name,path in path_keys.items():
        xs=[]
        for c in cases:
            x=c[side]
            for k in path:x=x[k]
            xs.append(float(x))
        vals[name]=mean(xs)
    return vals


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
        cases.append({"seed":int(raw["seed"]),"seat":seat,
                      "self":side_case(raw,seat),"opponent":side_case(raw,1-seat)})

    bridge={
        "day8_cash":pair_scalar(cases,["day8","cash"]),
        "day8_g0_future_units":pair_scalar(cases,["day8","non_wheat_future_units","G0"]),
        "day8_g1_future_units":pair_scalar(cases,["day8","non_wheat_future_units","G1"]),
        "day8_total_non_wheat_future_units":{
            "self_absolute_mean":mean([sum(c["self"]["day8"]["non_wheat_future_units"].values()) for c in cases]),
            "opponent_absolute_mean":mean([sum(c["opponent"]["day8"]["non_wheat_future_units"].values()) for c in cases]),
        },
        "current_return_sell_cash":pair_scalar(cases,["flow","sell_cash_total"]),
        "current_return_production_g0":pair_scalar(cases,["flow","production_units_by_generation","G0"]),
        "current_return_production_g1":pair_scalar(cases,["flow","production_units_by_generation","G1"]),
        "operating_spend":pair_scalar(cases,["flow","operating_spend_total"]),
        "surplus_after_operating":pair_scalar(cases,["flow","surplus_after_operating"]),
        "productive_spend":pair_scalar(cases,["flow","productive_spend_total"]),
        "g2_asset_count":pair_scalar(cases,["g2","asset_count"]),
        "g2_future_units":pair_scalar(cases,["g2","future_units"]),
        "day12_total_non_wheat_future_units":{
            "self_absolute_mean":mean([sum(c["self"]["day12"]["non_wheat_future_units"].values()) for c in cases]),
            "opponent_absolute_mean":mean([sum(c["opponent"]["day12"]["non_wheat_future_units"].values()) for c in cases]),
        },
    }
    # add gaps/consistency for manually summed totals
    for key,path in (
        ("day8_total_non_wheat_future_units",["day8","non_wheat_future_units"]),
        ("day12_total_non_wheat_future_units",["day12","non_wheat_future_units"]),
    ):
        sv=[];ov=[]
        for c in cases:
            sv.append(sum(float(v) for v in c["self"][path[0]][path[1]].values()))
            ov.append(sum(float(v) for v in c["opponent"][path[0]][path[1]].values()))
        gaps=[o-s for s,o in zip(sv,ov)]
        bridge[key].update({
            "mean_gap_opponent_minus_self":mean(gaps),
            "opponent_ahead_cases":sum(x>0 for x in gaps),
            "self_ahead_cases":sum(x<0 for x in gaps),
            "equal_cases":sum(x==0 for x in gaps),
        })

    out={
        "schema":"kaggriculture.strong-origin-v2.day8-day12-reinvestment-amplification-bridge.v0",
        "battle_count":len(cases),
        "bridge":bridge,
        "flow_detail":{
            "sell_cash_by_item":pair_map(cases,["flow","sell_cash_by_item"]),
            "operating_spend_by_item":pair_map(cases,["flow","operating_spend_by_item"]),
            "productive_spend_by_op":pair_map(cases,["flow","productive_spend_by_op"]),
            "productive_spend_by_item":pair_map(cases,["flow","productive_spend_by_item"]),
            "production_g0_by_item":pair_map(cases,["flow","production_units_by_generation_item","G0"]),
            "production_g1_by_item":pair_map(cases,["flow","production_units_by_generation_item","G1"]),
        },
        "growth_day8_to_12":{
            "cash":pair_scalar(cases,["growth","cash"]),
            "productive_assets":pair_scalar(cases,["growth","productive_assets"]),
            "production_potential_mark":pair_scalar(cases,["growth","production_potential_mark"]),
            "non_wheat_future_units_total":pair_scalar(cases,["growth","non_wheat_future_units_total"]),
        },
        "cases":cases,
        "boundary":[
            "No Candidate, Direction, score, or policy mutation is introduced.",
            "Day8 States are already different; the bridge does not treat Day8-12 as an isolated failure interval.",
            "SELL is period-level Cash inflow and is not assigned to a cohort or specific reinvestment.",
            "Surplus is SELL minus observed BUY_PRODUCT operating spend only.",
            "G2 physical future capacity uses public origin-day assets [8,12) and remaining potential units at Day12.",
            "Potential units and asset count are preferred over price marks for physical amplification.",
            "Observed ratios, if later discussed, are descriptive comparisons and not adopted objectives."
        ]
    }
    Path("day8_day12_reinvestment_amplification_bridge_v0.json").write_text(
        json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    compact={
        "battle_count":len(cases),
        "bridge":bridge,
        "flow_detail":out["flow_detail"],
        "growth":out["growth_day8_to_12"],
    }
    print("DAY8_DAY12_REINVESTMENT_AMPLIFICATION_BRIDGE "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
