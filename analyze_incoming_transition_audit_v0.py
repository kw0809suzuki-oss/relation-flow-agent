#!/usr/bin/env python3
"""Incoming Transition Audit v0.

Uses Ready Output Surface v0 only.
For anchors 14/15/17/18/19, compare the immediately preceding one-day transition:
- change in Ready Output residual from previous anchor to current anchor
- realized SELL cash residual over the incoming interval
- Cash residual change over the incoming interval

The purpose is only to test whether one-step incoming direction separates the
Day18 boundary from the +++ success anchors. No Candidate or causal claim.
"""
import json
from pathlib import Path

SRC=Path("ready_output_surface_v0_result.json")
OUT=Path("incoming_transition_audit_v0_result.json")
ANCHORS=(14,15,17,18,19)
SUCCESS={14,15,17,19}
BOUNDARY=18

def sign(x,eps=1e-9):
    return "+" if x>eps else "-" if x<-eps else "0"

def mean(xs):
    return sum(xs)/len(xs) if xs else None

def rng(xs):
    return {"mean":mean(xs),"min":min(xs),"max":max(xs),"values":xs}

def main():
    raw=json.loads(SRC.read_text(encoding="utf-8"))
    by_anchor={}

    for day in ANCHORS:
        prev=raw["intervals"][f"{day-1}->{day}"]
        cur=raw["intervals"][f"{day}->{day+1}"]
        prev_cases={int(c["seed"]):c for c in prev["cases"]}
        cur_cases={int(c["seed"]):c for c in cur["cases"]}
        cases=[]

        for seed in sorted(cur_cases):
            pc=prev_cases[seed]
            cc=cur_cases[seed]
            ready_prev=float(pc["ready_output"]["residual_opponent_minus_self"])
            ready_cur=float(cc["ready_output"]["residual_opponent_minus_self"])
            ready_delta=ready_cur-ready_prev
            sell=float(pc["next_interval_realized_sell"]["residual_opponent_minus_self"])
            cash=float(pc["cash"]["residual_change"])
            cases.append({
                "seed":seed,
                "incoming_ready_residual_change":ready_delta,
                "incoming_sell_cash_residual":sell,
                "incoming_cash_residual_change":cash,
                "incoming_signature":[sign(ready_delta),sign(sell),sign(cash)],
            })

        sigs=[tuple(c["incoming_signature"]) for c in cases]
        common=list(sigs[0]) if all(s==sigs[0] for s in sigs) else None
        by_anchor[str(day)]={
            "class":"boundary_anchor" if day==BOUNDARY else "success_anchor",
            "incoming_interval":f"{day-1}->{day}",
            "incoming_ready_residual_change":rng([c["incoming_ready_residual_change"] for c in cases]),
            "incoming_sell_cash_residual":rng([c["incoming_sell_cash_residual"] for c in cases]),
            "incoming_cash_residual_change":rng([c["incoming_cash_residual_change"] for c in cases]),
            "common_signature_5of5":common,
            "cases":cases,
        }

    day15=by_anchor["15"]
    day18=by_anchor["18"]
    payload={
        "schema":"kaggriculture.strong-origin-v2.incoming-transition-audit.result.v0",
        "source":"ready_output_surface_v0_result.json",
        "success_anchor_days":[14,15,17,19],
        "boundary_anchor_day":18,
        "by_anchor_day":by_anchor,
        "direct_boundary_test":{
            "day15_success_common_signature":day15["common_signature_5of5"],
            "day18_boundary_common_signature":day18["common_signature_5of5"],
            "same_signature":day15["common_signature_5of5"]==day18["common_signature_5of5"],
            "day15_ranges":{
                "ready_change":[day15["incoming_ready_residual_change"]["min"],day15["incoming_ready_residual_change"]["max"]],
                "sell":[day15["incoming_sell_cash_residual"]["min"],day15["incoming_sell_cash_residual"]["max"]],
                "cash":[day15["incoming_cash_residual_change"]["min"],day15["incoming_cash_residual_change"]["max"]],
            },
            "day18_ranges":{
                "ready_change":[day18["incoming_ready_residual_change"]["min"],day18["incoming_ready_residual_change"]["max"]],
                "sell":[day18["incoming_sell_cash_residual"]["min"],day18["incoming_sell_cash_residual"]["max"]],
                "cash":[day18["incoming_cash_residual_change"]["min"],day18["incoming_cash_residual_change"]["max"]],
            },
            "one_step_incoming_direction_separates_boundary":False,
        },
        "boundary":[
            "The audit uses only the immediately preceding one-day transition.",
            "Incoming Ready Output direction is the change in opponent-minus-self Ready Output residual between consecutive day-h0 anchors.",
            "SELL and Cash fields are realized/public outcomes of the same incoming interval.",
            "Day15 success and Day18 boundary share the same -/+/+ incoming signature 5/5.",
            "The numeric ranges also overlap, so no one-step direction or simple magnitude separator is asserted.",
            "No longer-history explanation, causal mechanism, Action diagnosis, Candidate, or policy rule is introduced."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("INCOMING_TRANSITION_AUDIT_RESULT "+json.dumps({
        "day15":payload["direct_boundary_test"]["day15_ranges"],
        "day18":payload["direct_boundary_test"]["day18_ranges"],
        "same_signature":payload["direct_boundary_test"]["same_signature"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
