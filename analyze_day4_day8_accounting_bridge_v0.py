#!/usr/bin/env python3
"""Day4 -> Day8 Accounting Bridge v0.

Input:
  state_transition_growth_audit_v0_aggregate.json

Purpose:
  Close the external accounting bridge from Day4 composition to Day8 State
  without creating a Candidate or attributing a particular SELL dollar to a
  particular investment.

Identity per side/case:
  realized SELL
  - operating spend
  = productive spend
  + Cash growth

The bridge also separates WHEAT realization from non-WHEAT realization because
WHEAT is simultaneously sold and repurchased as an operating input.
"""
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

INTERVAL="4_8"
START="4"
END="8"


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def median(xs):
    return statistics.median(xs) if xs else None


def sumdict(d):
    return sum(float(v or 0) for v in (d or {}).values())


def item_mean(cases,side,path):
    keys=set()
    for c in cases:
        x=c[side]
        for k in path:
            x=x[k]
        keys.update(x.keys())
    out={}
    for key in sorted(keys):
        vals=[]
        for c in cases:
            x=c[side]
            for k in path:
                x=x[k]
            vals.append(float(x.get(key,0) or 0))
        out[key]=mean(vals)
    return out


def composition_mean(cases,side,day):
    crop=item_mean(cases,side,["states",day,"crop_count"])
    animal=item_mean(cases,side,["states",day,"animal_count"])
    return {"crop":crop,"animal":animal}


def due_mean(cases,side):
    return item_mean(cases,side,["intervals",INTERVAL,"timing_quality","start_state_due_by_item"])


def lane_row(case,side):
    x=case[side]["intervals"][INTERVAL]
    sell=x["timing_quality"]["sell_cash_by_item"]
    operating=x["reinvestment_capacity"]["operating_spend_by_item"]
    productive=x["reinvestment_capacity"]["productive_spend_by_op"]

    wheat_sell=float(sell.get("WHEAT",0) or 0)
    non_wheat_sell=sum(float(v or 0) for k,v in sell.items() if k!="WHEAT")
    operating_spend=sumdict(operating)
    realized_sell=sumdict(sell)
    surplus=realized_sell-operating_spend
    productive_spend=sumdict(productive)
    cash_growth=float(x["state_growth"]["cash_delta"])
    net_wheat=wheat_sell-operating_spend

    return {
        "realized_sell":realized_sell,
        "wheat_sell":wheat_sell,
        "non_wheat_sell":non_wheat_sell,
        "operating_spend":operating_spend,
        "net_wheat_after_operating":net_wheat,
        "surplus_after_operating":surplus,
        "productive_spend":productive_spend,
        "cash_growth":cash_growth,
        "bridge_error":surplus-productive_spend-cash_growth,
        "sell_by_item":sell,
        "operating_by_item":operating,
        "productive_spend_by_op":productive,
        "actual_production_units":float(x["timing_quality"]["actual_production_units"]),
        "actual_harvest_units":float(x["timing_quality"]["actual_harvest_units"]),
        "productive_assets_growth":float(x["state_growth"]["productive_assets_delta"]),
        "production_potential_growth":float(x["state_growth"]["production_potential_mark_delta"]),
        "land_growth":float(x["state_growth"]["land_quadrants_delta"]),
    }


def aggregate_rows(rows):
    scalar_keys=(
        "realized_sell","wheat_sell","non_wheat_sell","operating_spend",
        "net_wheat_after_operating","surplus_after_operating",
        "productive_spend","cash_growth","bridge_error",
        "actual_production_units","actual_harvest_units",
        "productive_assets_growth","production_potential_growth","land_growth",
    )
    out={k:mean([float(r[k]) for r in rows]) for k in scalar_keys}
    out["max_abs_bridge_error"]=max(abs(float(r["bridge_error"])) for r in rows)
    return out


def state_abs_mean(cases,side,day,key):
    return mean([float(c[side]["states"][day][key]) for c in cases])


def main():
    source=Path(sys.argv[1] if len(sys.argv)>1 else "state_transition_growth_audit_v0_aggregate.json")
    raw=json.loads(source.read_text(encoding="utf-8"))
    cases=raw["cases"]

    self_rows=[lane_row(c,"self") for c in cases]
    opp_rows=[lane_row(c,"opponent") for c in cases]
    self_agg=aggregate_rows(self_rows)
    opp_agg=aggregate_rows(opp_rows)

    gap={
        k:opp_agg[k]-self_agg[k]
        for k in (
            "realized_sell","wheat_sell","non_wheat_sell","operating_spend",
            "net_wheat_after_operating","surplus_after_operating",
            "productive_spend","cash_growth","actual_production_units",
            "actual_harvest_units","productive_assets_growth",
            "production_potential_growth","land_growth",
        )
    }

    gap["surplus_decomposition_error"] = (
        gap["surplus_after_operating"]
        - gap["non_wheat_sell"]
        - gap["net_wheat_after_operating"]
    )
    gap["use_decomposition_error"] = (
        gap["surplus_after_operating"]
        - gap["productive_spend"]
        - gap["cash_growth"]
    )

    per_case=[]
    for c,s,o in zip(cases,self_rows,opp_rows):
        per_case.append({
            "seed":int(c["seed"]),
            "seat":int(c["seat"]),
            "self":s,
            "opponent":o,
            "gap_opponent_minus_self":{
                "surplus_after_operating":o["surplus_after_operating"]-s["surplus_after_operating"],
                "non_wheat_sell":o["non_wheat_sell"]-s["non_wheat_sell"],
                "net_wheat_after_operating":o["net_wheat_after_operating"]-s["net_wheat_after_operating"],
                "productive_spend":o["productive_spend"]-s["productive_spend"],
                "cash_growth":o["cash_growth"]-s["cash_growth"],
            },
        })

    non_gap=[x["gap_opponent_minus_self"]["non_wheat_sell"] for x in per_case]
    surplus_gap=[x["gap_opponent_minus_self"]["surplus_after_operating"] for x in per_case]
    residual=[
        s-n
        for s,n in zip(surplus_gap,non_gap)
    ]

    payload={
        "schema":"kaggriculture.strong-origin-v2.day4-day8-accounting-bridge.v0",
        "source_schema":raw.get("schema"),
        "battle_count":len(cases),
        "terminal":raw.get("terminal"),
        "day4":{
            "self_composition":composition_mean(cases,"self",START),
            "opponent_composition":composition_mean(cases,"opponent",START),
            "self_assets_due_by_day8":due_mean(cases,"self"),
            "opponent_assets_due_by_day8":due_mean(cases,"opponent"),
            "self_cash":state_abs_mean(cases,"self",START,"cash"),
            "opponent_cash":state_abs_mean(cases,"opponent",START,"cash"),
            "self_productive_assets":state_abs_mean(cases,"self",START,"productive_assets"),
            "opponent_productive_assets":state_abs_mean(cases,"opponent",START,"productive_assets"),
            "self_production_potential":state_abs_mean(cases,"self",START,"production_potential_mark"),
            "opponent_production_potential":state_abs_mean(cases,"opponent",START,"production_potential_mark"),
        },
        "day4_to_day8":{
            "self":self_agg,
            "opponent":opp_agg,
            "gap_opponent_minus_self":gap,
            "self_sell_by_item_mean":item_mean(cases,"self",["intervals",INTERVAL,"timing_quality","sell_cash_by_item"]),
            "opponent_sell_by_item_mean":item_mean(cases,"opponent",["intervals",INTERVAL,"timing_quality","sell_cash_by_item"]),
            "self_operating_by_item_mean":item_mean(cases,"self",["intervals",INTERVAL,"reinvestment_capacity","operating_spend_by_item"]),
            "opponent_operating_by_item_mean":item_mean(cases,"opponent",["intervals",INTERVAL,"reinvestment_capacity","operating_spend_by_item"]),
            "self_productive_spend_by_op_mean":item_mean(cases,"self",["intervals",INTERVAL,"reinvestment_capacity","productive_spend_by_op"]),
            "opponent_productive_spend_by_op_mean":item_mean(cases,"opponent",["intervals",INTERVAL,"reinvestment_capacity","productive_spend_by_op"]),
            "self_production_units_by_item_mean":item_mean(cases,"self",["intervals",INTERVAL,"timing_quality","production_units_by_item"]),
            "opponent_production_units_by_item_mean":item_mean(cases,"opponent",["intervals",INTERVAL,"timing_quality","production_units_by_item"]),
            "self_harvest_units_by_item_mean":item_mean(cases,"self",["intervals",INTERVAL,"timing_quality","harvest_units_by_item"]),
            "opponent_harvest_units_by_item_mean":item_mean(cases,"opponent",["intervals",INTERVAL,"timing_quality","harvest_units_by_item"]),
            "case_non_wheat_gap_minus_surplus_gap":{
                "mean":mean(residual),
                "median":median(residual),
                "min":min(residual),
                "max":max(residual),
            },
        },
        "day8":{
            "self_composition":composition_mean(cases,"self",END),
            "opponent_composition":composition_mean(cases,"opponent",END),
            "self_cash":state_abs_mean(cases,"self",END,"cash"),
            "opponent_cash":state_abs_mean(cases,"opponent",END,"cash"),
            "self_productive_assets":state_abs_mean(cases,"self",END,"productive_assets"),
            "opponent_productive_assets":state_abs_mean(cases,"opponent",END,"productive_assets"),
            "self_production_potential":state_abs_mean(cases,"self",END,"production_potential_mark"),
            "opponent_production_potential":state_abs_mean(cases,"opponent",END,"production_potential_mark"),
        },
        "cases":per_case,
        "boundary":[
            "This is an accounting bridge, not a causal attribution model.",
            "A specific SELL dollar is not assigned to a specific later investment because Cash is fungible.",
            "WHEAT SELL is netted against operating BUY_PRODUCT spend only as an accounting view; it does not assert physical unit lineage.",
            "Non-WHEAT SELL is reported separately because the observed operating spend in this interval is WHEAT BUY_PRODUCT.",
            "The bridge identity is required to close per case: SELL - operating = productive spend + Cash growth.",
            "Day4 asset maturity schedule is an opportunity schedule derived from public rules; actual production/HARVEST/SELL remain separate facts.",
            "No Candidate or adoption decision is generated."
        ],
    }

    out=Path("day4_day8_accounting_bridge_v0.json")
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    compact={
        "battle_count":len(cases),
        "day4":{
            "self_composition":payload["day4"]["self_composition"],
            "opponent_composition":payload["day4"]["opponent_composition"],
            "self_due":payload["day4"]["self_assets_due_by_day8"],
            "opponent_due":payload["day4"]["opponent_assets_due_by_day8"],
        },
        "bridge":{
            "self":self_agg,
            "opponent":opp_agg,
            "gap":gap,
            "self_sell_by_item":payload["day4_to_day8"]["self_sell_by_item_mean"],
            "opponent_sell_by_item":payload["day4_to_day8"]["opponent_sell_by_item_mean"],
            "self_productive_spend_by_op":payload["day4_to_day8"]["self_productive_spend_by_op_mean"],
            "opponent_productive_spend_by_op":payload["day4_to_day8"]["opponent_productive_spend_by_op_mean"],
        },
        "day8":{
            "self_composition":payload["day8"]["self_composition"],
            "opponent_composition":payload["day8"]["opponent_composition"],
        },
    }
    print("DAY4_DAY8_ACCOUNTING_BRIDGE "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
