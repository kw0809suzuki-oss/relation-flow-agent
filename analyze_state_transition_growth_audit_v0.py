#!/usr/bin/env python3
"""Aggregate State Transition Growth Audit v0.

Primary comparison:
  Body-only v0 vs Seyamalam
  Day4 State -> transition -> Day8 State -> transition -> Day12 State

The aggregate keeps State Growth, Reinvestment Capacity, and Timing Quality
separate. It does not create a composite score or infer Cash lineage.
"""
import glob
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import analyze_sb01_economic_layers_v0 as econ

DAYS=(4,8,12)
INTERVALS=((4,8),(8,12))
PRODUCTIVE_OPS=("HIRE","BUY_LAND","BUY_SEED","BUY_ANIMAL")
OPERATING_OPS=("BUY_PRODUCT",)


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def median(xs):
    return statistics.median(xs) if xs else None


def summary_pair(self_vals,opp_vals):
    gaps=[o-s for s,o in zip(self_vals,opp_vals)]
    return {
        "self_absolute_mean":mean(self_vals),
        "opponent_absolute_mean":mean(opp_vals),
        "mean_gap_opponent_minus_self":mean(gaps),
        "median_gap_opponent_minus_self":median(gaps),
        "opponent_ahead_cases":sum(g>0 for g in gaps),
        "self_ahead_cases":sum(g<0 for g in gaps),
        "equal_cases":sum(g==0 for g in gaps),
    }


def next_output_schedule(obs):
    day=int(obs.get("day",0) or 0)
    p=int(obs["player"])
    farm=obs["farms"][p]
    rows=[]

    for y,row in enumerate(farm.get("tiles",[]) or []):
        for x,t in enumerate(row or []):
            if not isinstance(t,dict):
                continue

            crop=t.get("crop")
            if crop in econ.CROPS:
                rule=econ.CROPS[crop]
                planted=int(t.get("planted_day",day) or day)
                held=int(t.get("yield_units",0) or 0)
                age=day-planted
                next_day=None
                reason=None

                if held>0 and age>=rule["first"]:
                    next_day=day
                    reason="held_harvestable_output"
                elif rule["ongoing"]:
                    for n in range(rule["max_yield"]):
                        d=planted+rule["first"]+n*rule["interval"]
                        if d>day:
                            next_day=d
                            reason="scheduled_ongoing_production"
                            break
                else:
                    eligible=planted+rule["first"]
                    if day<eligible:
                        next_day=eligible
                        reason="first_harvest_eligibility"
                    elif held>0:
                        next_day=day
                        reason="held_harvestable_output"

                if next_day is not None:
                    rows.append({
                        "asset_type":"crop",
                        "asset":crop,
                        "output_item":crop,
                        "x":x,"y":y,
                        "origin_day":planted,
                        "next_output_day":int(next_day),
                        "days_to_output":int(next_day-day),
                        "reason":reason,
                    })

            animal=t.get("animal")
            if animal in econ.ANIMALS:
                rule=econ.ANIMALS[animal]
                placed=int(t.get("placed_day",day) or day)
                held=int(t.get("yield_units",0) or 0)
                next_day=None
                reason=None

                if held>0:
                    next_day=day
                    reason="held_harvestable_output"
                else:
                    d=placed+rule["first"]
                    while d<=econ.SEASON_DAYS:
                        if d>day:
                            next_day=d
                            reason="scheduled_animal_production"
                            break
                        d+=rule["interval"]

                if next_day is not None:
                    rows.append({
                        "asset_type":"animal",
                        "asset":animal,
                        "output_item":rule["product"],
                        "x":x,"y":y,
                        "origin_day":placed,
                        "next_output_day":int(next_day),
                        "days_to_output":int(next_day-day),
                        "reason":reason,
                    })
    return rows


def derive_state(obs):
    side=econ.derive_side(obs)
    p=int(obs["player"])
    farm=obs["farms"][p]
    crops=side["committed_production"]["crop_count"]
    animals=side["committed_production"]["animal_count"]
    schedule=next_output_schedule(obs)
    by_day=Counter(str(x["next_output_day"]) for x in schedule)
    by_item=Counter(x["output_item"] for x in schedule)
    by_days_to=Counter(str(x["days_to_output"]) for x in schedule)
    return {
        "day":int(obs.get("day",0) or 0),
        "cash":float(side["cash"]),
        "land_quadrants":len(farm.get("unlocked_quadrants",[]) or []),
        "unlocked_tiles":int(side["uncommitted_capacity"]["unlocked_tiles"]),
        "empty_unlocked_tiles":int(side["uncommitted_capacity"]["empty_unlocked_tiles"]),
        "productive_assets":int(sum(crops.values())+sum(animals.values())),
        "crop_count":dict(crops),
        "animal_count":dict(animals),
        "production_potential_mark":float(side["committed_production"]["same_basis_subtotal"]),
        "inventory_mark":float(side["liquidatable_inventory"]["display_price_mark"]),
        "next_output_schedule":schedule,
        "next_output_count_by_day":dict(sorted(by_day.items(),key=lambda kv:int(kv[0]))),
        "next_output_count_by_item":dict(sorted(by_item.items())),
        "days_to_output_count":dict(sorted(by_days_to.items(),key=lambda kv:int(kv[0]))),
    }


def market_event_spend(e):
    delta=float(e.get("cash_delta",0) or 0)
    return max(0.0,-delta)


def interval_events(raw,p,start,end):
    market=[
        e for e in raw["market_events"]
        if int(e.get("player",-1))==p and start<=int(e.get("day",-1))<end
    ]
    prod=[
        e for e in raw["production_events"]
        if int(e.get("player",-1))==p and start<=int(e.get("transition_day",-1))<end
    ]
    harvest=[
        e for e in raw["harvest_events"]
        if int(e.get("player",-1))==p and start<=int(e.get("day",-1))<end
    ]
    return market,prod,harvest


def interval_metrics(raw,p,start,end,state_start,state_end):
    market,prod,harvest=interval_events(raw,p,start,end)

    sell=[e for e in market if e.get("op")=="SELL"]
    productive=[e for e in market if e.get("op") in PRODUCTIVE_OPS]
    operating=[e for e in market if e.get("op") in OPERATING_OPS]

    sell_by_day=defaultdict(float)
    prod_spend_by_day=defaultdict(float)
    op_spend_by_day=defaultdict(float)
    production_units_by_day=defaultdict(float)
    harvest_units_by_day=defaultdict(float)

    sell_by_item=defaultdict(float)
    productive_by_op=defaultdict(float)
    operating_by_item=defaultdict(float)
    production_by_item=defaultdict(float)
    harvest_by_item=defaultdict(float)

    for e in sell:
        v=float(e.get("cash_delta",0) or 0)
        sell_by_day[str(int(e["day"]))]+=v
        sell_by_item[str(e.get("item"))]+=v
    for e in productive:
        v=market_event_spend(e)
        prod_spend_by_day[str(int(e["day"]))]+=v
        productive_by_op[str(e.get("op"))]+=v
    for e in operating:
        v=market_event_spend(e)
        op_spend_by_day[str(int(e["day"]))]+=v
        operating_by_item[str(e.get("item"))]+=v
    for e in prod:
        v=float(e.get("units",0) or 0)
        d=str(int(e.get("result_state_day",e.get("transition_day",0))))
        production_units_by_day[d]+=v
        production_by_item[str(e.get("item"))]+=v
    for e in harvest:
        v=float(e.get("units",0) or 0)
        harvest_units_by_day[str(int(e["day"]))]+=v
        harvest_by_item[str(e.get("item"))]+=v

    due=[
        x for x in state_start["next_output_schedule"]
        if start<=int(x["next_output_day"])<=end
    ]

    return {
        "state_growth":{
            "cash_delta":state_end["cash"]-state_start["cash"],
            "land_quadrants_delta":state_end["land_quadrants"]-state_start["land_quadrants"],
            "unlocked_tiles_delta":state_end["unlocked_tiles"]-state_start["unlocked_tiles"],
            "empty_unlocked_tiles_delta":state_end["empty_unlocked_tiles"]-state_start["empty_unlocked_tiles"],
            "productive_assets_delta":state_end["productive_assets"]-state_start["productive_assets"],
            "production_potential_mark_delta":state_end["production_potential_mark"]-state_start["production_potential_mark"],
            "inventory_mark_delta":state_end["inventory_mark"]-state_start["inventory_mark"],
        },
        "reinvestment_capacity":{
            "realized_sell_cash":sum(float(e.get("cash_delta",0) or 0) for e in sell),
            "productive_spend":sum(market_event_spend(e) for e in productive),
            "operating_spend":sum(market_event_spend(e) for e in operating),
            "productive_spend_by_op":dict(sorted(productive_by_op.items())),
            "operating_spend_by_item":dict(sorted(operating_by_item.items())),
            "productive_spend_days":len(prod_spend_by_day),
            "sell_days":len(sell_by_day),
        },
        "timing_quality":{
            "start_state_assets_due_by_end":len(due),
            "start_state_due_by_item":dict(Counter(x["output_item"] for x in due)),
            "actual_production_units":sum(float(e.get("units",0) or 0) for e in prod),
            "actual_harvest_units":sum(float(e.get("units",0) or 0) for e in harvest),
            "production_units_by_item":dict(sorted(production_by_item.items())),
            "harvest_units_by_item":dict(sorted(harvest_by_item.items())),
            "sell_cash_by_item":dict(sorted(sell_by_item.items())),
            "sell_cash_by_day":dict(sorted(sell_by_day.items(),key=lambda kv:int(kv[0]))),
            "productive_spend_by_day":dict(sorted(prod_spend_by_day.items(),key=lambda kv:int(kv[0]))),
            "operating_spend_by_day":dict(sorted(op_spend_by_day.items(),key=lambda kv:int(kv[0]))),
            "production_units_by_result_day":dict(sorted(production_units_by_day.items(),key=lambda kv:int(kv[0]))),
            "harvest_units_by_day":dict(sorted(harvest_units_by_day.items(),key=lambda kv:int(kv[0]))),
        },
    }


def side_case(raw,p):
    states={}
    for d in DAYS:
        obs=raw["state_export"][str(p)][str(d)]["observation"]
        states[str(d)]=derive_state(obs)
    intervals={}
    for start,end in INTERVALS:
        intervals[f"{start}_{end}"]=interval_metrics(
            raw,p,start,end,states[str(start)],states[str(end)]
        )
    return {"states":states,"intervals":intervals}


def metric_summary(cases,path):
    def get(side,path):
        x=side
        for k in path:
            x=x[k]
        return float(x)
    sv=[get(c["self"],path) for c in cases]
    ov=[get(c["opponent"],path) for c in cases]
    return summary_pair(sv,ov)


def day_wave_mean(cases,interval,side,field,days):
    out={}
    for d in days:
        vals=[]
        for c in cases:
            m=c[side]["intervals"][interval]["timing_quality"][field]
            vals.append(float(m.get(str(d),0) or 0))
        out[str(d)]=mean(vals)
    return out


def aggregate_item_dict(cases,interval,side,section,field):
    keys=set()
    for c in cases:
        keys.update(c[side]["intervals"][interval][section][field].keys())
    return {
        k:mean([
            float(c[side]["intervals"][interval][section][field].get(k,0) or 0)
            for c in cases
        ])
        for k in sorted(keys)
    }


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/state_transition_growth_audit_v0_*.json"))
    if not files:
        files=[Path(p) for p in glob.glob(str(root/"**"/"state_transition_growth_audit_v0_*.json"),recursive=True)]
    if not files:
        raise SystemExit("No State Transition Growth Audit files")

    raws=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    raws.sort(key=lambda x:int(x["seed"]))

    for raw in raws:
        missing=raw["audit"].get("missing_target_states",[])
        if missing:
            raise SystemExit(f"Missing target State seed {raw['seed']}: {missing}")
        errors=[abs(float(x.get("error",0) or 0)) for x in raw["cash_validation"]]
        if any(e>1e-9 for e in errors):
            raise SystemExit(f"Cash reconstruction failed seed {raw['seed']}: {errors}")
        if int(raw["audit"].get("unmapped_relevant_events",0) or 0)>0:
            raise SystemExit(f"Unmapped relevant events seed {raw['seed']}: {raw['audit']['unmapped_relevant_events']}")

    cases=[]
    for raw in raws:
        seat=int(raw["seat"])
        opp=1-seat
        cases.append({
            "seed":int(raw["seed"]),
            "seat":seat,
            "terminal":raw["terminal"],
            "self":side_case(raw,seat),
            "opponent":side_case(raw,opp),
        })

    day_agg={}
    for d in DAYS:
        key=str(d)
        day_agg[key]={
            "cash":metric_summary(cases,["states",key,"cash"]),
            "land_quadrants":metric_summary(cases,["states",key,"land_quadrants"]),
            "unlocked_tiles":metric_summary(cases,["states",key,"unlocked_tiles"]),
            "empty_unlocked_tiles":metric_summary(cases,["states",key,"empty_unlocked_tiles"]),
            "productive_assets":metric_summary(cases,["states",key,"productive_assets"]),
            "production_potential_mark":metric_summary(cases,["states",key,"production_potential_mark"]),
            "inventory_mark":metric_summary(cases,["states",key,"inventory_mark"]),
        }

    interval_agg={}
    for start,end in INTERVALS:
        ik=f"{start}_{end}"
        days=range(start,end)
        interval_agg[ik]={
            "state_growth":{
                k:metric_summary(cases,["intervals",ik,"state_growth",k])
                for k in (
                    "cash_delta","land_quadrants_delta","unlocked_tiles_delta",
                    "empty_unlocked_tiles_delta","productive_assets_delta",
                    "production_potential_mark_delta","inventory_mark_delta"
                )
            },
            "reinvestment_capacity":{
                k:metric_summary(cases,["intervals",ik,"reinvestment_capacity",k])
                for k in (
                    "realized_sell_cash","productive_spend","operating_spend",
                    "productive_spend_days","sell_days"
                )
            },
            "timing_quality":{
                k:metric_summary(cases,["intervals",ik,"timing_quality",k])
                for k in (
                    "start_state_assets_due_by_end","actual_production_units","actual_harvest_units"
                )
            },
            "self_waves":{
                "sell_cash_by_day_mean":day_wave_mean(cases,ik,"self","sell_cash_by_day",days),
                "productive_spend_by_day_mean":day_wave_mean(cases,ik,"self","productive_spend_by_day",days),
                "operating_spend_by_day_mean":day_wave_mean(cases,ik,"self","operating_spend_by_day",days),
                "production_units_by_result_day_mean":day_wave_mean(cases,ik,"self","production_units_by_result_day",range(start,end+1)),
                "harvest_units_by_day_mean":day_wave_mean(cases,ik,"self","harvest_units_by_day",days),
            },
            "opponent_waves":{
                "sell_cash_by_day_mean":day_wave_mean(cases,ik,"opponent","sell_cash_by_day",days),
                "productive_spend_by_day_mean":day_wave_mean(cases,ik,"opponent","productive_spend_by_day",days),
                "operating_spend_by_day_mean":day_wave_mean(cases,ik,"opponent","operating_spend_by_day",days),
                "production_units_by_result_day_mean":day_wave_mean(cases,ik,"opponent","production_units_by_result_day",range(start,end+1)),
                "harvest_units_by_day_mean":day_wave_mean(cases,ik,"opponent","harvest_units_by_day",days),
            },
            "self_composition":{
                "productive_spend_by_op_mean":aggregate_item_dict(cases,ik,"self","reinvestment_capacity","productive_spend_by_op"),
                "operating_spend_by_item_mean":aggregate_item_dict(cases,ik,"self","reinvestment_capacity","operating_spend_by_item"),
                "production_units_by_item_mean":aggregate_item_dict(cases,ik,"self","timing_quality","production_units_by_item"),
                "harvest_units_by_item_mean":aggregate_item_dict(cases,ik,"self","timing_quality","harvest_units_by_item"),
                "sell_cash_by_item_mean":aggregate_item_dict(cases,ik,"self","timing_quality","sell_cash_by_item"),
            },
            "opponent_composition":{
                "productive_spend_by_op_mean":aggregate_item_dict(cases,ik,"opponent","reinvestment_capacity","productive_spend_by_op"),
                "operating_spend_by_item_mean":aggregate_item_dict(cases,ik,"opponent","reinvestment_capacity","operating_spend_by_item"),
                "production_units_by_item_mean":aggregate_item_dict(cases,ik,"opponent","timing_quality","production_units_by_item"),
                "harvest_units_by_item_mean":aggregate_item_dict(cases,ik,"opponent","timing_quality","harvest_units_by_item"),
                "sell_cash_by_item_mean":aggregate_item_dict(cases,ik,"opponent","timing_quality","sell_cash_by_item"),
            },
        }

    terminal_self=[float(c["terminal"]["self"]) for c in cases]
    terminal_opp=[float(c["terminal"]["opponent"]) for c in cases]
    terminal_margin=[float(c["terminal"]["margin"]) for c in cases]

    payload={
        "schema":"kaggriculture.strong-origin-v2.state-transition-growth-audit.aggregate.v0",
        "battle_count":len(cases),
        "terminal":{
            "self_absolute_mean":mean(terminal_self),
            "opponent_absolute_mean":mean(terminal_opp),
            "mean_margin":mean(terminal_margin),
            "wins":sum(x>0 for x in terminal_margin),
        },
        "days":day_agg,
        "intervals":interval_agg,
        "cases":cases,
        "boundary":[
            "The primary comparison is Body-only v0 vs Seyamalam; there is no new Candidate.",
            "State Growth, Reinvestment Capacity, and Timing Quality remain separate axes; no composite strength score is created.",
            "Realized SELL Cash and spend are temporally co-observed but Cash fungibility prevents attribution of a specific sale to a specific investment.",
            "Next-output schedules are public-rule opportunities from the snapshot, not guaranteed realized production.",
            "Actual production, HARVEST, SELL, and spend events are retained separately from schedule.",
            "A Maturity Ladder hypothesis requires repeated recovery timing + repeated productive spend + continuing State growth; this audit does not assume it in advance."
        ]
    }
    Path("state_transition_growth_audit_v0_aggregate.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={
        "battle_count":len(cases),
        "terminal":payload["terminal"],
        "days":{
            d:{
                "cash":day_agg[d]["cash"],
                "land":day_agg[d]["land_quadrants"],
                "empty":day_agg[d]["empty_unlocked_tiles"],
                "assets":day_agg[d]["productive_assets"],
                "potential":day_agg[d]["production_potential_mark"],
            }
            for d in map(str,DAYS)
        },
        "intervals":{
            ik:{
                "asset_growth":interval_agg[ik]["state_growth"]["productive_assets_delta"],
                "potential_growth":interval_agg[ik]["state_growth"]["production_potential_mark_delta"],
                "sell_cash":interval_agg[ik]["reinvestment_capacity"]["realized_sell_cash"],
                "productive_spend":interval_agg[ik]["reinvestment_capacity"]["productive_spend"],
                "operating_spend":interval_agg[ik]["reinvestment_capacity"]["operating_spend"],
                "production_units":interval_agg[ik]["timing_quality"]["actual_production_units"],
                "sell_days":interval_agg[ik]["reinvestment_capacity"]["sell_days"],
                "productive_spend_days":interval_agg[ik]["reinvestment_capacity"]["productive_spend_days"],
                "self_waves":interval_agg[ik]["self_waves"],
                "opponent_waves":interval_agg[ik]["opponent_waves"],
            }
            for ik in interval_agg
        }
    }
    print("STATE_TRANSITION_GROWTH_AUDIT_AGG "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
