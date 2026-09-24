#!/usr/bin/env python3
"""Temporal Stack Audit v0.

No Candidate, no Direction, no composite score.

Question:
Does stronger State growth coincide with a time structure where future maturity
is already in flight while current realization and new productive spending occur?

All maturity values are public-rule opportunities, not guaranteed realized cash.
Actual production/SELL/spend stay separate.
"""
import glob,json,sys
from collections import defaultdict
from pathlib import Path

import analyze_sb01_economic_layers_v0 as econ

PRODUCTIVE_OPS=("HIRE","BUY_LAND","BUY_SEED","BUY_ANIMAL")
OPERATING_OPS=("BUY_PRODUCT",)
DAYS=tuple(range(0,12))


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def next_due(asset,day):
    kind=asset.get("asset_type")
    name=asset.get("asset")
    origin=int(asset.get("origin_day",day) or day)
    held=int(asset.get("yield_units",0) or 0)

    if kind=="crop" and name in econ.CROPS:
        r=econ.CROPS[name]
        age=day-origin
        if held>0 and age>=r["first"]:
            return day
        if r["ongoing"]:
            for n in range(r["max_yield"]):
                d=origin+r["first"]+n*r["interval"]
                if d>day:
                    return d
            return None
        first=origin+r["first"]
        if day<first:
            return first
        return None

    if kind=="animal" and name in econ.ANIMALS:
        r=econ.ANIMALS[name]
        if held>0:
            return day
        d=origin+r["first"]
        while d<=econ.SEASON_DAYS:
            if d>day:
                return d
            d+=r["interval"]
        return None
    return None


def trace_index(raw,p):
    idx={}
    for row in raw["commitment_trace"][str(p)]:
        idx[(int(row.get("day",0)),int(row.get("hour",0)))]=row
    return idx


def day_start_row(raw,p,day):
    rows=[r for r in raw["commitment_trace"][str(p)] if int(r.get("day",-1))==day]
    if not rows:
        return None
    return min(rows,key=lambda r:int(r.get("hour",0)))


def maturity_context(row):
    if not row:
        return {"due_now_or_2d":0,"due_3plus":0,"future_total":0,"by_item":{}}
    day=int(row.get("day",0))
    near=0;far=0;by=defaultdict(int)
    for a in row.get("maturity_assets",[]) or []:
        d=next_due(a,day)
        if d is None:
            continue
        lag=d-day
        by[str(a.get("asset"))]+=1
        if lag<=2:
            near+=1
        else:
            far+=1
    return {
        "due_now_or_2d":near,
        "due_3plus":far,
        "future_total":near+far,
        "by_item":dict(sorted(by.items())),
    }


def event_day_amounts(raw,p):
    sell=defaultdict(float)
    operating=defaultdict(float)
    productive=defaultdict(float)
    productive_by_op=defaultdict(lambda:defaultdict(float))
    for e in raw.get("market_events",[]) or []:
        if int(e.get("player",-1))!=p:
            continue
        d=int(e.get("day",-1))
        if not (0<=d<12):
            continue
        op=e.get("op")
        delta=float(e.get("cash_delta",0) or 0)
        if op=="SELL":
            sell[d]+=max(0.0,delta)
        elif op in OPERATING_OPS:
            operating[d]+=max(0.0,-delta)
        elif op in PRODUCTIVE_OPS:
            v=max(0.0,-delta)
            productive[d]+=v
            productive_by_op[d][str(op)]+=v

    production=defaultdict(float)
    for e in raw.get("production_events",[]) or []:
        if int(e.get("player",-1))!=p:
            continue
        d=int(e.get("result_state_day",e.get("transition_day",-1)))
        if 0<=d<12:
            production[d]+=float(e.get("units",0) or 0)

    return sell,operating,productive,productive_by_op,production


def spend_event_context(raw,p):
    idx=trace_index(raw,p)
    rows=[]
    for e in raw.get("market_events",[]) or []:
        if int(e.get("player",-1))!=p or e.get("op") not in PRODUCTIVE_OPS:
            continue
        d=int(e.get("day",-1));h=int(e.get("hour",-1))
        if not (0<=d<12):
            continue
        row=idx.get((d,h))
        ctx=maturity_context(row)
        spend=max(0.0,-float(e.get("cash_delta",0) or 0))
        rows.append({
            "day":d,"hour":h,"op":str(e.get("op")),"spend":spend,
            "future_maturity_total":ctx["future_total"],
            "near_maturity":ctx["due_now_or_2d"],
            "far_maturity":ctx["due_3plus"],
        })
    return rows


def sell_event_context(raw,p):
    idx=trace_index(raw,p)
    rows=[]
    for e in raw.get("market_events",[]) or []:
        if int(e.get("player",-1))!=p or e.get("op")!="SELL":
            continue
        d=int(e.get("day",-1));h=int(e.get("hour",-1))
        if not (0<=d<12):
            continue
        row=idx.get((d,h))
        ctx=maturity_context(row)
        cash=max(0.0,float(e.get("cash_delta",0) or 0))
        rows.append({
            "day":d,"hour":h,"item":str(e.get("item")),"cash":cash,
            "future_maturity_total":ctx["future_total"],
            "near_maturity":ctx["due_now_or_2d"],
            "far_maturity":ctx["due_3plus"],
        })
    return rows


def side_case(raw,p):
    sell,oper,prod,pby,production=event_day_amounts(raw,p)
    days={}
    for d in DAYS:
        row=day_start_row(raw,p,d)
        ctx=maturity_context(row)
        days[str(d)]={
            "cash":float(row.get("cash",0) or 0) if row else None,
            "near_maturity_assets":ctx["due_now_or_2d"],
            "far_maturity_assets":ctx["due_3plus"],
            "future_maturity_assets":ctx["future_total"],
            "actual_production_units":production[d],
            "sell_cash":sell[d],
            "operating_spend":oper[d],
            "surplus_after_operating":sell[d]-oper[d],
            "productive_spend":prod[d],
            "productive_spend_by_op":dict(sorted(pby[d].items())),
        }

    pe=spend_event_context(raw,p)
    se=sell_event_context(raw,p)
    spend_total=sum(x["spend"] for x in pe)
    spend_with_future=sum(x["spend"] for x in pe if x["future_maturity_total"]>0)
    spend_with_both=sum(x["spend"] for x in pe if x["near_maturity"]>0 and x["far_maturity"]>0)
    sell_total=sum(x["cash"] for x in se)
    sell_with_far=sum(x["cash"] for x in se if x["far_maturity"]>0)

    return {
        "days":days,
        "productive_spend_events":pe,
        "sell_events":se,
        "summary":{
            "productive_spend_total":spend_total,
            "productive_spend_while_future_maturity_in_flight":spend_with_future,
            "productive_spend_while_near_and_far_coexist":spend_with_both,
            "share_productive_spend_with_future_maturity":spend_with_future/spend_total if spend_total else None,
            "share_productive_spend_with_near_and_far":spend_with_both/spend_total if spend_total else None,
            "sell_cash_total":sell_total,
            "sell_cash_while_far_maturity_in_flight":sell_with_far,
            "share_sell_cash_while_far_maturity_in_flight":sell_with_far/sell_total if sell_total else None,
            "days_near_and_far_coexist":sum(
                1 for d in DAYS
                if days[str(d)]["near_maturity_assets"]>0 and days[str(d)]["far_maturity_assets"]>0
            ),
            "productive_spend_days":sum(days[str(d)]["productive_spend"]>0 for d in DAYS),
            "sell_days":sum(days[str(d)]["sell_cash"]>0 for d in DAYS),
        }
    }


def pair_summary(cases,path):
    def pick(side):
        x=side
        for k in path:
            x=x[k]
        return None if x is None else float(x)
    sv=[];ov=[]
    for c in cases:
        a=pick(c["self"]);b=pick(c["opponent"])
        if a is None or b is None:
            continue
        sv.append(a);ov.append(b)
    gaps=[o-s for s,o in zip(sv,ov)]
    return {
        "self_absolute_mean":mean(sv),
        "opponent_absolute_mean":mean(ov),
        "mean_gap_opponent_minus_self":mean(gaps),
        "opponent_ahead_cases":sum(g>0 for g in gaps),
        "self_ahead_cases":sum(g<0 for g in gaps),
        "equal_cases":sum(g==0 for g in gaps),
    }


def day_pair(cases,d,key):
    return pair_summary(cases,["days",str(d),key])


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/state_transition_growth_audit_v0_*.json"))
    if not files:
        files=[Path(p) for p in glob.glob(str(root/"**"/"state_transition_growth_audit_v0_*.json"),recursive=True)]
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    if not raws:
        raise SystemExit("No raw audit files")
    raws.sort(key=lambda x:int(x["seed"]))

    cases=[]
    for raw in raws:
        seat=int(raw["seat"])
        cases.append({
            "seed":int(raw["seed"]),
            "seat":seat,
            "self":side_case(raw,seat),
            "opponent":side_case(raw,1-seat),
        })

    day_agg={}
    for d in DAYS:
        day_agg[str(d)]={k:day_pair(cases,d,k) for k in (
            "cash","near_maturity_assets","far_maturity_assets","future_maturity_assets",
            "actual_production_units","sell_cash","operating_spend",
            "surplus_after_operating","productive_spend"
        )}

    summary_keys=(
        "productive_spend_total",
        "productive_spend_while_future_maturity_in_flight",
        "productive_spend_while_near_and_far_coexist",
        "share_productive_spend_with_future_maturity",
        "share_productive_spend_with_near_and_far",
        "sell_cash_total",
        "sell_cash_while_far_maturity_in_flight",
        "share_sell_cash_while_far_maturity_in_flight",
        "days_near_and_far_coexist",
        "productive_spend_days",
        "sell_days",
    )
    summary={k:pair_summary(cases,["summary",k]) for k in summary_keys}

    out={
        "schema":"kaggriculture.strong-origin-v2.temporal-stack-audit.v0",
        "battle_count":len(cases),
        "days":day_agg,
        "summary":summary,
        "cases":cases,
        "boundary":[
            "No Candidate, Direction, pressure variable, or policy mutation is introduced.",
            "Near maturity means a public-rule next-output opportunity within 0-2 days; far maturity means 3+ days.",
            "Maturity is opportunity, not guaranteed realization or profit.",
            "Actual production, SELL, operating spend, and productive spend remain separately observed facts.",
            "SELL and later spend are not linked by Cash lineage because Cash is fungible.",
            "Coexistence of maturity horizons is descriptive and is not itself a strength score."
        ]
    }
    Path("temporal_stack_audit_v0.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    compact={
        "battle_count":len(cases),
        "summary":summary,
        "days":{
            str(d):{
                "near":day_agg[str(d)]["near_maturity_assets"],
                "far":day_agg[str(d)]["far_maturity_assets"],
                "sell":day_agg[str(d)]["sell_cash"],
                "surplus":day_agg[str(d)]["surplus_after_operating"],
                "productive_spend":day_agg[str(d)]["productive_spend"],
                "production":day_agg[str(d)]["actual_production_units"],
            }
            for d in DAYS
        }
    }
    print("TEMPORAL_STACK_AUDIT "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
