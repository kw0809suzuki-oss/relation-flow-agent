#!/usr/bin/env python3
"""Observed payback-duration separator v0.

Replays the same D16/D18 fresh5 and extracts only:
- first meaningful D18-only expansion commitment day
- first added output day
- first added cash-conversion day
- observed recovery completion day
- remaining horizon at commitment
- observed payback duration

Question:
Does observed_payback_duration <= remaining_horizon separate the sign of
D18-vs-D16 terminal self money in these five cases?

No predictor. No new strategy. No capital/irreversibility model yet.
"""
import copy
import json
import os
from pathlib import Path

from kaggle_environments import make
import export_scale_baseline_v1 as base
import closure_switch_sweep_v0 as switcher

OPPONENT = base.OPPONENT
CASES = [(5201+i, i%2) for i in range(5)]
TERMINAL_DAY = 30
OUT = Path("payback_duration_separator_v0.json")

OUTPUT_ITEMS = ("MILK","WOOL","EGG","FERTILIZER")
INV_ITEMS = ("WHEAT","MELON","POTATO","MILK","WOOL","EGG","FERTILIZER","COW")

def configure(day):
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    switcher.set_probe_enabled(True)
    switcher.set_attribution_enabled(True)
    switcher.reset_experiment()
    switcher.set_switch_day(day)

def total_private(obs,item):
    p=obs.get("private",{}) or {}
    shed=p.get("shed",{}) or {}
    invs=p.get("inventories",[]) or []
    return float(shed.get(item,0) or 0)+sum(float((x or {}).get(item,0) or 0) for x in invs)

def snap(obs):
    me=obs["farms"][obs["player"]]
    tiles=0
    cows_on_tiles=0
    for row in me.get("tiles",[]) or []:
        for tile in row:
            if tile in (None,"LOCKED"):
                continue
            tiles += 1
            if isinstance(tile,dict) and tile.get("animal")=="COW":
                cows_on_tiles += 1
    inv={k:total_private(obs,k) for k in INV_ITEMS}
    return {
        "day":int(obs.get("day",0) or 0),
        "money":float(me.get("money",0) or 0),
        "hands":len(me.get("hands",[]) or []),
        "active_tiles":tiles,
        "cows":inv.get("COW",0.0)+cows_on_tiles,
        "outputs":sum(inv.get(k,0.0) for k in OUTPUT_ITEMS),
        "inventory":inv,
    }

def play(seed,seat,switch_day):
    configure(switch_day)
    trace=[]
    actions=[]
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    def observed(obs):
        trace.append(snap(obs))
        a=switcher.agent(obs)
        actions.append(copy.deepcopy(a))
        return a
    players=[OPPONENT,OPPONENT]
    players[seat]=observed
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {"score":{"self":rewards[seat]},"trace":trace,"actions":actions}

def daily_last(trace):
    d={}
    for s in trace:
        d[s["day"]]=s
    return d

def first_action_difference(a,b):
    for i,(x,y) in enumerate(zip(a,b)):
        if x!=y:
            return i
    return None

def positive(x):
    return max(0.0,float(x))

def extract(seed,d16,d18):
    t16=daily_last(d16["trace"])
    t18=daily_last(d18["trace"])
    days=sorted(set(t16)&set(t18))

    first_commit_day=None
    first_output_day=None
    first_cash_conversion_day=None
    recovery_completion_day=None
    max_cash_commit_gap=0.0

    rows=[]
    for day in days:
        if day < 16:
            continue
        a=t16[day]
        b=t18[day]

        cash_commit_gap=positive(a["money"]-b["money"])
        productive_gap=(
            positive(b["active_tiles"]-a["active_tiles"]) +
            positive(b["hands"]-a["hands"]) +
            positive(b["cows"]-a["cows"])
        )
        output_gap=positive(b["outputs"]-a["outputs"])

        if first_commit_day is None and (cash_commit_gap>0 or productive_gap>0):
            first_commit_day=day
        if first_output_day is None and output_gap>0:
            first_output_day=day

        max_cash_commit_gap=max(max_cash_commit_gap,cash_commit_gap)

        # First day the D18 path has more cash than D16 after a meaningful
        # commitment branch has already appeared.
        cash_delta=b["money"]-a["money"]
        if first_commit_day is not None and first_cash_conversion_day is None and day>first_commit_day and cash_delta>0:
            first_cash_conversion_day=day

        # Operational recovery completion:
        # after a meaningful commitment, D18 cash has caught up/exceeded D16
        # and no positive output/inventory gap remains on that daily snapshot.
        inv_gap=sum(positive(b["inventory"].get(k,0)-a["inventory"].get(k,0)) for k in INV_ITEMS)
        residual=inv_gap+output_gap
        if (
            first_commit_day is not None and
            day>first_commit_day and
            cash_delta>=0 and
            residual<=0 and
            recovery_completion_day is None
        ):
            recovery_completion_day=day

        rows.append({
            "day":day,
            "cash_delta_d18_minus_d16":cash_delta,
            "cash_commit_gap":cash_commit_gap,
            "productive_gap":productive_gap,
            "output_gap":output_gap,
            "positive_inventory_gap":inv_gap,
        })

    terminal_delta=d18["score"]["self"]-d16["score"]["self"]
    remaining_horizon=(TERMINAL_DAY-first_commit_day) if first_commit_day is not None else None
    payback_duration=(recovery_completion_day-first_commit_day) if recovery_completion_day is not None else None
    separator_value=(
        payback_duration is not None and remaining_horizon is not None and payback_duration <= remaining_horizon
    )

    return {
        "seed":seed,
        "terminal_d18_minus_d16":terminal_delta,
        "observed_sign":"D18>D16" if terminal_delta>0 else "D16>D18" if terminal_delta<0 else "equal",
        "first_commit_day":first_commit_day,
        "first_added_output_day":first_output_day,
        "first_added_cash_conversion_day":first_cash_conversion_day,
        "recovery_completion_day":recovery_completion_day,
        "remaining_horizon_at_commit":remaining_horizon,
        "observed_payback_duration":payback_duration,
        "payback_within_horizon":separator_value,
        "max_observed_cash_commit_gap":max_cash_commit_gap,
        "daily":rows,
    }

def main():
    cases=[]
    for seed,seat in CASES:
        d16=play(seed,seat,16)
        d18=play(seed,seat,18)
        cases.append(extract(seed,d16,d18))

    positives=[r for r in cases if r["terminal_d18_minus_d16"]>0]
    negatives=[r for r in cases if r["terminal_d18_minus_d16"]<0]
    perfect=(
        positives and negatives and
        all(r["payback_within_horizon"] is True for r in positives) and
        all(r["payback_within_horizon"] is False for r in negatives)
    )

    result={
        "schema":"kaggriculture.payback-duration-separator.v0",
        "question":"does observed_payback_duration <= remaining_horizon separate D18-vs-D16 terminal sign in the five replay cases?",
        "operational_definition":{
            "commit_day":"first daily snapshot after Day16 where D18 has positive cash-commit gap or productive-state gap vs D16",
            "first_added_output":"first day D18 output inventory exceeds D16",
            "first_added_cash_conversion":"first post-commit day D18 cash exceeds D16",
            "recovery_completion":"first post-commit day D18 cash has caught up/exceeded D16 and no positive D18 output/inventory residual remains",
            "payback_duration":"recovery_completion_day - first_commit_day",
            "remaining_horizon":"30 - first_commit_day",
        },
        "boundary":[
            "This is an observed replay separator, not a predictive payback estimator.",
            "No capital size, conversion-speed model, or irreversibility term is added yet.",
            "If this does not separate sign, do not rescue it post hoc; move to the next state quantity."
        ],
        "cases":cases,
        "perfect_separator_on_this_set":perfect,
    }

    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PAYBACK_DURATION_SEPARATOR "+json.dumps({
        "cases":[{
            "seed":r["seed"],
            "sign":r["observed_sign"],
            "commit_day":r["first_commit_day"],
            "output_day":r["first_added_output_day"],
            "cash_day":r["first_added_cash_conversion_day"],
            "recovery_day":r["recovery_completion_day"],
            "remaining":r["remaining_horizon_at_commit"],
            "payback":r["observed_payback_duration"],
            "within_horizon":r["payback_within_horizon"],
        } for r in cases],
        "perfect_separator_on_this_set":perfect,
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
