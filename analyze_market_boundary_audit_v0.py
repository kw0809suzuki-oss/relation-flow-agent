#!/usr/bin/env python3
"""Market Boundary Audit v0.

Compare the four fixed-five intervals where the product/date-agnostic +++ word
held 5/5 (Day14,15,17,19 anchors) against the Day18 boundary interval.

Observation basis only:
- Ready Output mark residual and product spread
- shared market inventory and displayed price at the anchor
- time-to-terminal
- next-24h realized SELL cash residual and Cash residual change

No action/policy diagnosis and no Candidate.
"""
import glob,json,statistics
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
ANCHORS=(14,15,17,18,19)
SUCCESS={14,15,17,19}
BOUNDARY=18

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
    lo=day*24;hi=(day+1)*24
    return [t for t in raw["surface_turns"] if lo<=int(t["turn_index"])<hi]

def ready_by_item(raw,day,label):
    t=anchor(raw,day); side=t["before"][pidx(raw,label)]
    out={}
    for item,(asset,field) in READY_MAP.items():
        units=float(side["asset_by_type"][asset][field])
        price=float(t["market_before"]["displayed_price_by_item"].get(item,0) or 0)
        out[item]={"units":units,"price":price,"mark":units*price}
    return out

def realized_sell_cash(raw,day,label):
    idx=pidx(raw,label)
    total=0.0
    by_item={i:0.0 for i in PRODUCTS}
    for t in interval_turns(raw,day):
        rp=t["realized_by_player"][idx]
        for item in PRODUCTS:
            c=float(rp["sell_cash_by_item"].get(item,0) or 0)
            total+=c;by_item[item]+=c
    return total,by_item

def cash_residual(raw,day):
    t=anchor(raw,day)
    return float(t["before"][pidx(raw,"opponent")]["cash"])-float(t["before"][pidx(raw,"self")]["cash"])

def feature_case(raw,day):
    t=anchor(raw,day)
    sr=ready_by_item(raw,day,"self");orr=ready_by_item(raw,day,"opponent")
    deltas={item:orr[item]["mark"]-sr[item]["mark"] for item in READY_MAP}
    positive=[i for i,v in deltas.items() if v>0]
    negative=[i for i,v in deltas.items() if v<0]
    positive_marks=[deltas[i] for i in positive]
    total_positive=sum(positive_marks)
    top_positive=max(positive_marks) if positive_marks else 0.0
    top_share=(top_positive/total_positive) if total_positive>0 else None

    market_inv={i:float(t["market_before"]["inventory_by_item"].get(i,0) or 0) for i in PRODUCTS}
    prices={i:float(t["market_before"]["displayed_price_by_item"].get(i,0) or 0) for i in PRODUCTS}

    pos_market_inv=[market_inv[i] for i in positive]
    pos_prices=[prices[i] for i in positive]
    # Mark-weighted market context over opponent-positive ready products.
    weighted_inv=None;weighted_price=None
    if total_positive>0:
        weighted_inv=sum(market_inv[i]*deltas[i] for i in positive)/total_positive
        weighted_price=sum(prices[i]*deltas[i] for i in positive)/total_positive

    s_sell,s_sell_by=realized_sell_cash(raw,day,"self")
    o_sell,o_sell_by=realized_sell_cash(raw,day,"opponent")
    c0=cash_residual(raw,day);c1=cash_residual(raw,day+1)

    return {
        "seed":raw["seed"],
        "anchor_day":day,
        "class":"success_5of5_word_anchor" if day in SUCCESS else "boundary_anchor",
        "ready_output":{
            "self_mark":sum(x["mark"] for x in sr.values()),
            "opponent_mark":sum(x["mark"] for x in orr.values()),
            "residual":sum(deltas.values()),
            "positive_product_count":len(positive),
            "negative_product_count":len(negative),
            "positive_products":positive,
            "negative_products":negative,
            "positive_mark_total":total_positive,
            "top_positive_mark_share":top_share,
            "by_item_residual_mark":deltas,
        },
        "market":{
            "shared_inventory_by_item":market_inv,
            "displayed_price_by_item":prices,
            "positive_ready_products_inventory_mean":mean(pos_market_inv),
            "positive_ready_products_inventory_min":min(pos_market_inv) if pos_market_inv else None,
            "positive_ready_products_inventory_max":max(pos_market_inv) if pos_market_inv else None,
            "positive_ready_products_price_mean":mean(pos_prices),
            "positive_ready_products_price_min":min(pos_prices) if pos_prices else None,
            "positive_ready_products_price_max":max(pos_prices) if pos_prices else None,
            "ready_mark_weighted_market_inventory":weighted_inv,
            "ready_mark_weighted_displayed_price":weighted_price,
        },
        "time":{
            "remaining_season_turns":int(t["before"][pidx(raw,"self")]["time"]["remaining_season_turns"]),
        },
        "response":{
            "sell_cash_residual":o_sell-s_sell,
            "cash_residual_change":c1-c0,
            "sell_cash_by_item_residual":{i:o_sell_by[i]-s_sell_by[i] for i in PRODUCTS},
        },
    }

def summarize(cases,field_path):
    vals=[]
    for c in cases:
        x=c
        for k in field_path:
            x=x[k]
        if x is not None:
            vals.append(float(x))
    return {
        "mean":mean(vals),
        "min":min(vals) if vals else None,
        "max":max(vals) if vals else None,
        "values":vals,
    }

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "market-boundary-artifacts/**/dynamic_economic_surface_v0_*.json",recursive=True
    ))
    if len(paths)!=5:
        raise SystemExit(f"Expected 5 raw dynamic-surface artifacts, found {len(paths)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

    by_day={}
    all_cases=[]
    for day in ANCHORS:
        cases=[feature_case(r,day) for r in raws]
        all_cases.extend(cases)
        by_day[str(day)]={
            "class":"success_5of5_word_anchor" if day in SUCCESS else "boundary_anchor",
            "ready_residual":summarize(cases,("ready_output","residual")),
            "positive_product_count":summarize(cases,("ready_output","positive_product_count")),
            "top_positive_mark_share":summarize(cases,("ready_output","top_positive_mark_share")),
            "positive_ready_market_inventory_mean":summarize(cases,("market","positive_ready_products_inventory_mean")),
            "ready_mark_weighted_market_inventory":summarize(cases,("market","ready_mark_weighted_market_inventory")),
            "positive_ready_price_mean":summarize(cases,("market","positive_ready_products_price_mean")),
            "ready_mark_weighted_displayed_price":summarize(cases,("market","ready_mark_weighted_displayed_price")),
            "remaining_season_turns":summarize(cases,("time","remaining_season_turns")),
            "sell_cash_residual":summarize(cases,("response","sell_cash_residual")),
            "cash_residual_change":summarize(cases,("response","cash_residual_change")),
            "cases":cases,
        }

    success_cases=[c for c in all_cases if c["anchor_day"] in SUCCESS]
    boundary_cases=[c for c in all_cases if c["anchor_day"]==BOUNDARY]
    feature_paths={
        "ready_residual":("ready_output","residual"),
        "positive_product_count":("ready_output","positive_product_count"),
        "top_positive_mark_share":("ready_output","top_positive_mark_share"),
        "positive_ready_market_inventory_mean":("market","positive_ready_products_inventory_mean"),
        "ready_mark_weighted_market_inventory":("market","ready_mark_weighted_market_inventory"),
        "positive_ready_price_mean":("market","positive_ready_products_price_mean"),
        "ready_mark_weighted_displayed_price":("market","ready_mark_weighted_displayed_price"),
        "remaining_season_turns":("time","remaining_season_turns"),
    }

    comparisons={}
    for name,path in feature_paths.items():
        s=summarize(success_cases,path); b=summarize(boundary_cases,path)
        # Mechanical non-overlap only; not a causal separator claim.
        nonoverlap=None
        if s["values"] and b["values"]:
            if s["min"]>b["max"]:
                nonoverlap="all_success_values_above_all_boundary_values"
            elif s["max"]<b["min"]:
                nonoverlap="all_success_values_below_all_boundary_values"
        comparisons[name]={"success":s,"boundary":b,"range_nonoverlap":nonoverlap}

    payload={
        "schema":"kaggriculture.strong-origin-v2.market-boundary-audit.result.v0",
        "battle_count":5,
        "success_anchor_days":[14,15,17,19],
        "boundary_anchor_day":18,
        "by_anchor_day":by_day,
        "feature_range_comparison":comparisons,
        "boundary":[
            "Success/boundary labels refer only to whether the +++ signature held 5/5 in Ready Output Surface v0.",
            "Market inventory and displayed price are shared public World State at the anchor.",
            "Cross-product Ready Output is a displayed-price valuation mark, not realized Cash.",
            "Range non-overlap is a mechanical sample property only; it is not a causal separator or a rule.",
            "Day/time identity is retained for audit but is not used as a candidate trigger.",
            "No Action reason, policy state, Candidate, or adoption conclusion is introduced."
        ]
    }
    Path("market_boundary_audit_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("MARKET_BOUNDARY_AUDIT_RESULT "+json.dumps({
        "by_anchor_day":{d:{k:v for k,v in x.items() if k!="cases"} for d,x in by_day.items()},
        "feature_range_comparison":comparisons,
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
