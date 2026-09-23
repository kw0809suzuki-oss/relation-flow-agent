#!/usr/bin/env python3
"""Aggregate external economic quantities for Strong Origin v2 Body-only v0."""
import glob,json,statistics,sys
from pathlib import Path

import analyze_sb01_economic_layers_v0 as econ

DAYS=(0,4,8,12,16,20,24,28)
OUTPUT_PRODUCTS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL")


def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None


def summary(self_vals,opp_vals):
    gaps=[o-s for s,o in zip(self_vals,opp_vals)]
    return {
        "self_absolute_mean":mean(self_vals),
        "opponent_absolute_mean":mean(opp_vals),
        "mean_gap_opponent_minus_self":mean(gaps),
        "median_gap_opponent_minus_self":median(gaps),
        "opponent_ahead_cases":sum(g>0 for g in gaps),
        "self_ahead_cases":sum(g<0 for g in gaps),
    }


def flow_for(raw,p):
    ev=[e for e in raw["events"] if int(e.get("player",-1))==p]
    sales=sum(float(e.get("cash_delta",0) or 0) for e in ev if e.get("op")=="SELL")
    productive=-sum(float(e.get("cash_delta",0) or 0) for e in ev if e.get("op") in ("HIRE","BUY_LAND","BUY_SEED","BUY_ANIMAL"))
    operating=-sum(float(e.get("cash_delta",0) or 0) for e in ev if e.get("op")=="BUY_PRODUCT")
    late_productive=-sum(float(e.get("cash_delta",0) or 0) for e in ev if int(e.get("day",0) or 0)>=14 and e.get("op") in ("HIRE","BUY_LAND","BUY_SEED","BUY_ANIMAL"))
    late_total=-sum(float(e.get("cash_delta",0) or 0) for e in ev if int(e.get("day",0) or 0)>=14 and float(e.get("cash_delta",0) or 0)<0)

    day0=raw["state_export"][str(p)]["0"]["observation"]
    final=raw["final_observation"][str(p)]
    q0=econ._inventory_quantities(day0.get("private",{}) or {})
    qf=econ._inventory_quantities(final.get("private",{}) or {})
    bought={k:0 for k in econ.PRODUCTS}
    sold={k:0 for k in econ.PRODUCTS}
    for e in ev:
        item=e.get("item")
        if item not in econ.PRODUCTS: continue
        if e.get("op")=="BUY_PRODUCT": bought[item]+=1
        if e.get("op")=="SELL": sold[item]+=1

    net_generated={}
    final_prices=(final.get("market",{}) or {}).get("prices",{}) or {}
    mark=0.0
    for item in OUTPUT_PRODUCTS:
        units=float(qf.get(item,0)-q0.get(item,0)-bought.get(item,0)+sold.get(item,0))
        net_generated[item]=units
        mark += units*float(final_prices.get(item,0) or 0)

    return {
        "realized_sell_cash":sales,
        "productive_reinvestment_spend":productive,
        "operating_input_spend":operating,
        "total_market_spend":productive+operating,
        "late_productive_reinvestment_spend_day14_plus":late_productive,
        "late_total_spend_day14_plus":late_total,
        "net_generated_sellable_units_after_internal_use":net_generated,
        "net_generated_output_terminal_price_mark":mark,
    }


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/strong_origin_v2_external_economy_v0_*.json"))
    if not files:
        files=[Path(p) for p in glob.glob(str(root/"**"/"strong_origin_v2_external_economy_v0_*.json"),recursive=True)]
    if not files: raise SystemExit("No external economy files")

    cases=[]
    for f in files:
        raw=json.loads(f.read_text(encoding="utf-8"))
        seat=int(raw["seat"]); opp=1-seat
        if any(str(d) not in raw["state_export"][str(seat)] or str(d) not in raw["state_export"][str(opp)] for d in DAYS):
            raise SystemExit(f"Missing target day in seed {raw['seed']}")
        if any(abs(float(x["error"]))>1e-9 for x in raw["players"]):
            raise SystemExit(f"Cash reconstruction failed seed {raw['seed']}")
        days={}
        for d in DAYS:
            so=raw["state_export"][str(seat)][str(d)]["observation"]
            oo=raw["state_export"][str(opp)][str(d)]["observation"]
            days[str(d)]={"self":econ.derive_side(so),"opponent":econ.derive_side(oo)}
        cases.append({
            "seed":raw["seed"],"seat":seat,"terminal":raw["terminal"],"days":days,
            "flow":{"self":flow_for(raw,seat),"opponent":flow_for(raw,opp)}
        })

    day_out={}
    for d in DAYS:
        rows=[c["days"][str(d)] for c in cases]
        day_out[str(d)]={
            "cash":summary([r["self"]["cash"] for r in rows],[r["opponent"]["cash"] for r in rows]),
            "liquidatable_inventory_mark":summary(
                [r["self"]["liquidatable_inventory"]["display_price_mark"] for r in rows],
                [r["opponent"]["liquidatable_inventory"]["display_price_mark"] for r in rows]),
            "committed_production_potential_mark":summary(
                [r["self"]["committed_production"]["same_basis_subtotal"] for r in rows],
                [r["opponent"]["committed_production"]["same_basis_subtotal"] for r in rows]),
            "unlocked_tiles":summary(
                [r["self"]["uncommitted_capacity"]["unlocked_tiles"] for r in rows],
                [r["opponent"]["uncommitted_capacity"]["unlocked_tiles"] for r in rows]),
            "empty_unlocked_tiles":summary(
                [r["self"]["uncommitted_capacity"]["empty_unlocked_tiles"] for r in rows],
                [r["opponent"]["uncommitted_capacity"]["empty_unlocked_tiles"] for r in rows]),
        }

    flows={}
    for key in (
        "realized_sell_cash","productive_reinvestment_spend","operating_input_spend",
        "total_market_spend","late_productive_reinvestment_spend_day14_plus",
        "late_total_spend_day14_plus","net_generated_output_terminal_price_mark"
    ):
        flows[key]=summary(
            [c["flow"]["self"][key] for c in cases],
            [c["flow"]["opponent"][key] for c in cases]
        )

    tself=[float(c["terminal"]["self"]) for c in cases]
    topp=[float(c["terminal"]["opponent"]) for c in cases]
    tmargin=[float(c["terminal"]["margin"]) for c in cases]
    payload={
        "schema":"kaggriculture.strong-origin-v2.external-economy.aggregate.v0",
        "battle_count":len(cases),
        "terminal":{
            "self_absolute_mean":mean(tself),"opponent_absolute_mean":mean(topp),
            "mean_margin":mean(tmargin),"wins":sum(x>0 for x in tmargin)
        },
        "days":day_out,
        "whole_season_flow":flows,
        "cases":cases,
        "boundary":[
            "Cash and executed market Cash flow are Facts.",
            "Committed production potential and inventory marks are Valuations on the existing WB-0001 basis.",
            "Net-generated output is final inventory - initial inventory - executed BUY_PRODUCT + executed SELL; internal consumption makes it a net-output measure, not gross harvest.",
            "Late-spend fields measure executed Cash outflow at day >= 14 and are the closure coordinate.",
            "No total economic score is formed and no Flow/Catalog operation is selected here."
        ]
    }
    Path("strong_origin_v2_external_economy_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("STRONG_ORIGIN_V2_EXTERNAL_ECONOMY_AGG "+json.dumps({
        "battle_count":len(cases),"terminal":payload["terminal"],"flows":flows,
        "days":{d:{
            "cash_gap":day_out[d]["cash"]["mean_gap_opponent_minus_self"],
            "production_potential_gap":day_out[d]["committed_production_potential_mark"]["mean_gap_opponent_minus_self"],
            "inventory_gap":day_out[d]["liquidatable_inventory_mark"]["mean_gap_opponent_minus_self"]
        } for d in map(str,DAYS)}
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
