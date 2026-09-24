#!/usr/bin/env python3
"""Day0 -> Day4 Composition Bundle Audit v0.

No candidate and no policy mutation.

Primary comparison:
  Body-only v0 vs Seyamalam

Flow:
  Day0 resources
  -> Day0-4 realized allocation
  -> Day4 Composition Bundle
  -> Day4 maturity schedule / operating burden
  -> Day4-8 actual realization / surplus
  -> productive reinvestment
  -> Day8 State

Facts and valuation remain separate. No composite score is created.
"""
import glob
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import analyze_state_transition_growth_audit_v0 as transition

START_DAY=0
COMPOSITION_DAY=4
OUTCOME_DAY=8

CATEGORIES=("crop","animal","land","hire","operating")


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def median(xs):
    return statistics.median(xs) if xs else None


def summarize_pair(self_vals,opp_vals):
    gaps=[o-s for s,o in zip(self_vals,opp_vals)]
    return {
        "self_absolute_mean":mean(self_vals),
        "opponent_absolute_mean":mean(opp_vals),
        "mean_gap_opponent_minus_self":mean(gaps),
        "median_gap_opponent_minus_self":median(gaps),
        "opponent_ahead_cases":sum(g>0 for g in gaps),
        "self_ahead_cases":sum(g<0 for g in gaps),
        "equal_cases":sum(g==0 for g in gaps),
        "min_gap":min(gaps) if gaps else None,
        "max_gap":max(gaps) if gaps else None,
    }


def classify_market_event(e):
    op=e.get("op")
    if op=="BUY_SEED":
        return "crop"
    if op=="BUY_ANIMAL":
        return "animal"
    if op=="BUY_LAND":
        return "land"
    if op=="HIRE":
        return "hire"
    if op=="BUY_PRODUCT":
        return "operating"
    return None


def allocation_window(raw,p,start=0,end=4):
    events=[
        e for e in raw.get("market_events",[])
        if int(e.get("player",-1))==p and start<=int(e.get("day",-1))<end
    ]

    spend={k:0.0 for k in CATEGORIES}
    spend_detail={k:defaultdict(float) for k in CATEGORIES}
    units_detail={k:defaultdict(float) for k in CATEGORIES}
    realized_sell=0.0
    sell_by_item=defaultdict(float)

    for e in events:
        op=e.get("op")
        delta=float(e.get("cash_delta",0) or 0)
        if op=="SELL":
            realized_sell+=delta
            sell_by_item[str(e.get("item"))]+=delta
            continue
        category=classify_market_event(e)
        if category is None or delta>=0:
            continue
        cost=-delta
        spend[category]+=cost
        if category=="crop":
            key=str(e.get("item"))
        elif category=="animal":
            key=str(e.get("item"))
        elif category=="operating":
            key=str(e.get("item"))
        else:
            key=str(op)
        spend_detail[category][key]+=cost
        units_detail[category][key]+=1.0

    total_spend=sum(spend.values())
    return {
        "spend":spend,
        "total_spend":total_spend,
        "realized_sell_cash":realized_sell,
        "spend_detail":{k:dict(sorted(v.items())) for k,v in spend_detail.items()},
        "executed_order_units":{k:dict(sorted(v.items())) for k,v in units_detail.items()},
        "sell_by_item":dict(sorted(sell_by_item.items())),
    }


def cash_validation_initial(raw,p):
    for row in raw.get("cash_validation",[]):
        if int(row.get("player",-1))==p:
            return float(row.get("initial_cash",0) or 0)
    raise KeyError(f"initial cash missing for player {p}")


def day_obs(raw,p,day):
    return raw["state_export"][str(p)][str(day)]["observation"]


def aggregate_schedule(state):
    schedule=state.get("next_output_schedule",[]) or []
    by_day=Counter()
    by_item=Counter()
    by_type=Counter()
    reasons=Counter()
    for x in schedule:
        by_day[str(int(x["next_output_day"]))]+=1
        by_item[str(x["output_item"])]+=1
        by_type[str(x["asset_type"])]+=1
        reasons[str(x["reason"])]+=1
    return {
        "asset_count":len(schedule),
        "by_day":dict(sorted(by_day.items(),key=lambda kv:int(kv[0]))),
        "by_item":dict(sorted(by_item.items())),
        "by_asset_type":dict(sorted(by_type.items())),
        "by_reason":dict(sorted(reasons.items())),
    }


def side_case(raw,p):
    obs0=day_obs(raw,p,0)
    obs4=day_obs(raw,p,4)
    obs8=day_obs(raw,p,8)

    state0=transition.derive_state(obs0)
    state4=transition.derive_state(obs4)
    state8=transition.derive_state(obs8)

    allocation=allocation_window(raw,p,0,4)
    opening_cash=cash_validation_initial(raw,p)
    day4_cash=float(state4["cash"])

    spend=allocation["spend"]
    total_spend=float(allocation["total_spend"])
    sell=float(allocation["realized_sell_cash"])
    identity_error=opening_cash+sell-total_spend-day4_cash

    allocation["opening_cash"]=opening_cash
    allocation["day4_cash"]=day4_cash
    allocation["cash_identity_error"]=identity_error
    allocation["spend_share_of_opening_cash"]={
        k:(spend[k]/opening_cash if opening_cash else None) for k in CATEGORIES
    }
    allocation["total_spend_share_of_opening_cash"]=(total_spend/opening_cash if opening_cash else None)
    allocation["spend_share_of_total_spend"]={
        k:(spend[k]/total_spend if total_spend else 0.0) for k in CATEGORIES
    }

    interval=transition.interval_metrics(raw,p,4,8,state4,state8)

    return {
        "day0":{
            "cash":float(state0["cash"]),
            "land_quadrants":int(state0["land_quadrants"]),
            "unlocked_tiles":int(state0["unlocked_tiles"]),
            "productive_assets":int(state0["productive_assets"]),
            "crop_count":dict(state0["crop_count"]),
            "animal_count":dict(state0["animal_count"]),
        },
        "day0_to_day4_allocation":allocation,
        "day4":{
            **state4,
            "maturity_schedule":aggregate_schedule(state4),
        },
        "day4_to_day8":interval,
        "day8":state8,
    }


def scalar_pair(cases,path):
    def pick(side):
        x=side
        for k in path:
            x=x[k]
        return float(x)
    return summarize_pair(
        [pick(c["self"]) for c in cases],
        [pick(c["opponent"]) for c in cases],
    )


def dict_means(cases,side,path):
    keys=set()
    for c in cases:
        x=c[side]
        for k in path:
            x=x[k]
        keys.update(x.keys())
    return {
        k:mean([
            float((lambda z: z)((
                (lambda x: x)(None)
            ))) for _ in []
        ])
        for k in []
    } if False else {
        k:mean([
            float(_get(c[side],path).get(k,0) or 0)
            for c in cases
        ])
        for k in sorted(keys)
    }


def _get(x,path):
    for k in path:
        x=x[k]
    return x


def nested_dict_means(cases,side,path):
    keys=set()
    for c in cases:
        keys.update(_get(c[side],path).keys())
    return {
        k:mean([float(_get(c[side],path).get(k,0) or 0) for c in cases])
        for k in sorted(keys)
    }


def composition_means(cases,side,day):
    return {
        "crop_count":nested_dict_means(cases,side,[day,"crop_count"]),
        "animal_count":nested_dict_means(cases,side,[day,"animal_count"]),
    }


def maturity_means(cases,side):
    return {
        "asset_count_mean":mean([
            float(c[side]["day4"]["maturity_schedule"]["asset_count"]) for c in cases
        ]),
        "by_day_mean":nested_dict_means(cases,side,["day4","maturity_schedule","by_day"]),
        "by_item_mean":nested_dict_means(cases,side,["day4","maturity_schedule","by_item"]),
        "by_asset_type_mean":nested_dict_means(cases,side,["day4","maturity_schedule","by_asset_type"]),
    }


def allocation_detail_means(cases,side,category):
    return nested_dict_means(cases,side,["day0_to_day4_allocation","spend_detail",category])


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/state_transition_growth_audit_v0_*.json"))
    if not files:
        files=[Path(p) for p in glob.glob(str(root/"**"/"state_transition_growth_audit_v0_*.json"),recursive=True)]
    if not files:
        raise SystemExit("No State Transition Growth Audit raw files")

    raws=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    raws.sort(key=lambda x:int(x["seed"]))

    cases=[]
    for raw in raws:
        for p in (0,1):
            for d in (0,4,8):
                if str(d) not in raw["state_export"].get(str(p),{}):
                    raise SystemExit(f"Missing day {d} player {p} seed {raw['seed']}")
        errors=[abs(float(x.get("error",0) or 0)) for x in raw.get("cash_validation",[])]
        if any(e>1e-9 for e in errors):
            raise SystemExit(f"Cash reconstruction failed seed {raw['seed']}: {errors}")

        seat=int(raw["seat"])
        case={
            "seed":int(raw["seed"]),
            "seat":seat,
            "terminal":raw["terminal"],
            "self":side_case(raw,seat),
            "opponent":side_case(raw,1-seat),
        }
        for side in ("self","opponent"):
            err=abs(float(case[side]["day0_to_day4_allocation"]["cash_identity_error"]))
            if err>1e-9:
                raise SystemExit(f"Day0-4 Cash identity failed seed {raw['seed']} {side}: {err}")
        cases.append(case)

    allocation_agg={}
    for category in CATEGORIES:
        allocation_agg[category]=scalar_pair(
            cases,["day0_to_day4_allocation","spend",category]
        )

    day4_8={
        "realized_sell_cash":scalar_pair(cases,["day4_to_day8","reinvestment_capacity","realized_sell_cash"]),
        "operating_spend":scalar_pair(cases,["day4_to_day8","reinvestment_capacity","operating_spend"]),
        "surplus_after_operating":summarize_pair(
            [
                float(c["self"]["day4_to_day8"]["reinvestment_capacity"]["realized_sell_cash"])
                - float(c["self"]["day4_to_day8"]["reinvestment_capacity"]["operating_spend"])
                for c in cases
            ],
            [
                float(c["opponent"]["day4_to_day8"]["reinvestment_capacity"]["realized_sell_cash"])
                - float(c["opponent"]["day4_to_day8"]["reinvestment_capacity"]["operating_spend"])
                for c in cases
            ],
        ),
        "productive_spend":scalar_pair(cases,["day4_to_day8","reinvestment_capacity","productive_spend"]),
        "productive_assets_growth":scalar_pair(cases,["day4_to_day8","state_growth","productive_assets_delta"]),
        "production_potential_growth":scalar_pair(cases,["day4_to_day8","state_growth","production_potential_mark_delta"]),
    }

    payload={
        "schema":"kaggriculture.strong-origin-v2.composition-bundle-audit.v0",
        "battle_count":len(cases),
        "terminal":{
            "self_absolute_mean":mean([float(c["terminal"]["self"]) for c in cases]),
            "opponent_absolute_mean":mean([float(c["terminal"]["opponent"]) for c in cases]),
            "mean_margin":mean([float(c["terminal"]["margin"]) for c in cases]),
            "wins":sum(float(c["terminal"]["margin"])>0 for c in cases),
        },
        "day0_resources":{
            "cash":scalar_pair(cases,["day0","cash"]),
            "land_quadrants":scalar_pair(cases,["day0","land_quadrants"]),
            "productive_assets":scalar_pair(cases,["day0","productive_assets"]),
            "self_composition":composition_means(cases,"self","day0"),
            "opponent_composition":composition_means(cases,"opponent","day0"),
        },
        "day0_to_day4_allocation":{
            "spend_by_category":allocation_agg,
            "total_spend":scalar_pair(cases,["day0_to_day4_allocation","total_spend"]),
            "realized_sell_cash":scalar_pair(cases,["day0_to_day4_allocation","realized_sell_cash"]),
            "day4_cash":scalar_pair(cases,["day0_to_day4_allocation","day4_cash"]),
            "total_spend_share_of_opening_cash":scalar_pair(cases,["day0_to_day4_allocation","total_spend_share_of_opening_cash"]),
            "self_detail":{
                k:allocation_detail_means(cases,"self",k) for k in CATEGORIES
            },
            "opponent_detail":{
                k:allocation_detail_means(cases,"opponent",k) for k in CATEGORIES
            },
        },
        "day4_composition":{
            "cash":scalar_pair(cases,["day4","cash"]),
            "land_quadrants":scalar_pair(cases,["day4","land_quadrants"]),
            "unlocked_tiles":scalar_pair(cases,["day4","unlocked_tiles"]),
            "empty_unlocked_tiles":scalar_pair(cases,["day4","empty_unlocked_tiles"]),
            "productive_assets":scalar_pair(cases,["day4","productive_assets"]),
            "production_potential_mark":scalar_pair(cases,["day4","production_potential_mark"]),
            "self_composition":composition_means(cases,"self","day4"),
            "opponent_composition":composition_means(cases,"opponent","day4"),
            "self_maturity_schedule":maturity_means(cases,"self"),
            "opponent_maturity_schedule":maturity_means(cases,"opponent"),
        },
        "day4_to_day8":day4_8,
        "day8_state":{
            "cash":scalar_pair(cases,["day8","cash"]),
            "land_quadrants":scalar_pair(cases,["day8","land_quadrants"]),
            "productive_assets":scalar_pair(cases,["day8","productive_assets"]),
            "production_potential_mark":scalar_pair(cases,["day8","production_potential_mark"]),
            "self_composition":composition_means(cases,"self","day8"),
            "opponent_composition":composition_means(cases,"opponent","day8"),
        },
        "cases":cases,
        "boundary":[
            "No Candidate or policy mutation is introduced.",
            "Day0-4 allocation is realized Cash spend by public market category, not an inferred intent.",
            "Opening-Cash shares are reference ratios only and may exceed 100% because realized SELL can recycle Cash before Day4.",
            "Day4 maturity schedule is a public-rule opportunity schedule; it is not guaranteed realized output.",
            "Production-potential mark is a valuation under the existing WB-0001 assumptions, not realized profit.",
            "Actual Day4-8 SELL/spend and State growth remain Facts.",
            "Cash is fungible; no specific sale is assigned to a specific investment.",
            "No single Composition score is created and Seyamalam's bundle is not treated as a template to copy."
        ],
    }

    Path("composition_bundle_audit_v0.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={
        "battle_count":len(cases),
        "terminal":payload["terminal"],
        "day0_cash":payload["day0_resources"]["cash"],
        "allocation":payload["day0_to_day4_allocation"]["spend_by_category"],
        "day4":{
            "cash":payload["day4_composition"]["cash"],
            "assets":payload["day4_composition"]["productive_assets"],
            "potential":payload["day4_composition"]["production_potential_mark"],
            "self_mix":payload["day4_composition"]["self_composition"],
            "opponent_mix":payload["day4_composition"]["opponent_composition"],
            "self_maturity":payload["day4_composition"]["self_maturity_schedule"],
            "opponent_maturity":payload["day4_composition"]["opponent_maturity_schedule"],
        },
        "day4_8":day4_8,
        "day8":{
            "assets":payload["day8_state"]["productive_assets"],
            "potential":payload["day8_state"]["production_potential_mark"],
            "land":payload["day8_state"]["land_quadrants"],
        },
    }
    print("COMPOSITION_BUNDLE_AUDIT "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
