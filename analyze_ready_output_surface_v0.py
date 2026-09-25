#!/usr/bin/env python3
"""Ready Output Surface v0.

Replays the same fixed-five Dynamic Economic Surface raw observations and tests
whether a product/date-independent transition pattern survives:

ready-output mark residual at Day d h0
 -> realized SELL cash residual over [d,d+1)
 -> Cash residual change Day d -> d+1

Ready output is public per-asset held/harvestable product already present in the
World. Cross-product aggregation uses the same displayed market price at the
anchor only as a valuation basis, never as realized Cash.
"""
import glob,json
from pathlib import Path

PRODUCTS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER")
READY_MAP={
    "WHEAT":("WHEAT","current_harvestable_units"),
    "CARROT":("CARROT","current_harvestable_units"),
    "TOMATO":("TOMATO","current_harvestable_units"),
    "STRAWBERRY":("STRAWBERRY","current_harvestable_units"),
    "MELON":("MELON","current_harvestable_units"),
    "EGG":("GOOSE","held_output_units"),
    "MILK":("COW","held_output_units"),
    "WOOL":("SHEEP","held_output_units"),
}
DAYS=tuple(range(12,20))

def mean(xs): return sum(xs)/len(xs) if xs else None

def anchor(raw,day):
    for t in raw["surface_turns"]:
        if int(t["day"])==day and int(t["hour"])==0:
            return t
    raise KeyError((raw["seed"],day))

def pidx(raw,label):
    seat=int(raw["seat"])
    return str(seat if label=="self" else 1-seat)

def interval_turns(raw,day):
    lo=day*24; hi=(day+1)*24
    return [t for t in raw["surface_turns"] if lo<=int(t["turn_index"])<hi]

def ready_units_at(raw,day,label,item):
    t=anchor(raw,day)
    side=t["before"][pidx(raw,label)]
    asset,field=READY_MAP[item]
    return float(side["asset_by_type"][asset][field])

def price_at(raw,day,item):
    return float(anchor(raw,day)["market_before"]["displayed_price_by_item"].get(item,0) or 0)

def ready_mark_at(raw,day,label):
    by_item={}
    total=0.0
    for item in READY_MAP:
        units=ready_units_at(raw,day,label,item)
        price=price_at(raw,day,item)
        mark=units*price
        by_item[item]={"units":units,"price":price,"mark":mark}
        total+=mark
    return total,by_item

def realized_sell(raw,day,label):
    idx=pidx(raw,label)
    by_item={item:{"units":0.0,"cash":0.0} for item in PRODUCTS}
    total_cash=0.0
    for t in interval_turns(raw,day):
        rp=t["realized_by_player"][idx]
        for item in PRODUCTS:
            by_item[item]["units"]+=float(rp["sell_units_by_item"].get(item,0) or 0)
            c=float(rp["sell_cash_by_item"].get(item,0) or 0)
            by_item[item]["cash"]+=c
            total_cash+=c
    return total_cash,by_item

def cash_residual(raw,day):
    t=anchor(raw,day)
    s=float(t["before"][pidx(raw,"self")]["cash"])
    o=float(t["before"][pidx(raw,"opponent")]["cash"])
    return o-s

def sign_class(x,eps=1e-9):
    if x>eps: return "+"
    if x<-eps: return "-"
    return "0"

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "ready-output-artifacts/**/dynamic_economic_surface_v0_*.json",
        recursive=True
    ))
    if len(paths)!=5:
        raise SystemExit(f"Expected 5 raw dynamic-surface artifacts, found {len(paths)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

    intervals={}
    signatures=[]
    for day in DAYS:
        cases=[]
        for r in raws:
            s_ready,s_items=ready_mark_at(r,day,"self")
            o_ready,o_items=ready_mark_at(r,day,"opponent")
            ready_res=o_ready-s_ready

            s_sell,s_sell_items=realized_sell(r,day,"self")
            o_sell,o_sell_items=realized_sell(r,day,"opponent")
            sell_res=o_sell-s_sell

            cash_before=cash_residual(r,day)
            cash_after=cash_residual(r,day+1)
            cash_change=cash_after-cash_before

            ready_positive_items=[
                item for item in READY_MAP
                if o_items[item]["mark"]-s_items[item]["mark"]>0
            ]
            sell_positive_items=[
                item for item in PRODUCTS
                if o_sell_items[item]["cash"]-s_sell_items[item]["cash"]>0
            ]

            cases.append({
                "seed":r["seed"],
                "ready_output":{
                    "self_mark":s_ready,
                    "opponent_mark":o_ready,
                    "residual_opponent_minus_self":ready_res,
                    "opponent_positive_item_count":len(ready_positive_items),
                    "by_item_self":s_items,
                    "by_item_opponent":o_items,
                },
                "next_interval_realized_sell":{
                    "self_cash":s_sell,
                    "opponent_cash":o_sell,
                    "residual_opponent_minus_self":sell_res,
                    "opponent_positive_item_count":len(sell_positive_items),
                    "by_item_self":s_sell_items,
                    "by_item_opponent":o_sell_items,
                },
                "cash":{
                    "residual_before":cash_before,
                    "residual_after":cash_after,
                    "residual_change":cash_change,
                },
                "product_agnostic_signature":{
                    "ready_residual_sign":sign_class(ready_res),
                    "sell_residual_sign":sign_class(sell_res),
                    "cash_change_sign":sign_class(cash_change),
                },
            })

        ready_vals=[c["ready_output"]["residual_opponent_minus_self"] for c in cases]
        sell_vals=[c["next_interval_realized_sell"]["residual_opponent_minus_self"] for c in cases]
        cash_vals=[c["cash"]["residual_change"] for c in cases]
        sigs=[tuple(c["product_agnostic_signature"].values()) for c in cases]
        common_sig=sigs[0] if all(x==sigs[0] for x in sigs) else None

        row={
            "ready_output_mark_residual":{
                "mean":mean(ready_vals),
                "positive_cases":sum(x>0 for x in ready_vals),
                "negative_cases":sum(x<0 for x in ready_vals),
                "zero_cases":sum(x==0 for x in ready_vals),
            },
            "realized_sell_cash_residual":{
                "mean":mean(sell_vals),
                "positive_cases":sum(x>0 for x in sell_vals),
                "negative_cases":sum(x<0 for x in sell_vals),
                "zero_cases":sum(x==0 for x in sell_vals),
            },
            "cash_residual_change":{
                "mean":mean(cash_vals),
                "positive_cases":sum(x>0 for x in cash_vals),
                "negative_cases":sum(x<0 for x in cash_vals),
                "zero_cases":sum(x==0 for x in cash_vals),
            },
            "common_product_agnostic_signature_5of5":list(common_sig) if common_sig else None,
            "mean_opponent_positive_ready_item_count":mean([
                c["ready_output"]["opponent_positive_item_count"] for c in cases
            ]),
            "mean_opponent_positive_sell_item_count":mean([
                c["next_interval_realized_sell"]["opponent_positive_item_count"] for c in cases
            ]),
            "cases":cases,
        }
        intervals[f"{day}->{day+1}"]=row
        if common_sig:
            signatures.append({
                "interval":f"{day}->{day+1}",
                "signature":list(common_sig),
                "ready_mean":row["ready_output_mark_residual"]["mean"],
                "sell_mean":row["realized_sell_cash_residual"]["mean"],
                "cash_change_mean":row["cash_residual_change"]["mean"],
            })

    # Detect repeated date-independent signatures. No semantic labels are assigned.
    groups={}
    for x in signatures:
        k="|".join(x["signature"])
        groups.setdefault(k,[]).append(x)

    repeated={k:v for k,v in groups.items() if len(v)>=2}

    payload={
        "schema":"kaggriculture.strong-origin-v2.ready-output-surface.result.v0",
        "battle_count":5,
        "intervals":intervals,
        "repeated_product_agnostic_signatures":repeated,
        "boundary":[
            "Ready-output cross-product aggregation is a displayed-price valuation mark, not realized Cash.",
            "Ready output includes only product units already held/harvestable on productive assets at the day-h0 anchor.",
            "Realized SELL is exact public market cash over the following 24h interval.",
            "Signatures discard date and product identity and retain only the sign of ready-output residual, SELL residual, and Cash residual change.",
            "A repeated signature is an observed finite transition shape, not a causal law or strategy rule.",
            "No same-unit continuity from ready output to later SELL is asserted.",
            "No Candidate, mode label, or action recommendation is generated."
        ]
    }
    Path("ready_output_surface_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("READY_OUTPUT_SURFACE_RESULT "+json.dumps({
        "repeated_product_agnostic_signatures":repeated,
        "interval_summary":{
            k:{
                "ready":v["ready_output_mark_residual"],
                "sell":v["realized_sell_cash_residual"],
                "cash_change":v["cash_residual_change"],
                "signature_5of5":v["common_product_agnostic_signature_5of5"],
            } for k,v in intervals.items()
        }
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
