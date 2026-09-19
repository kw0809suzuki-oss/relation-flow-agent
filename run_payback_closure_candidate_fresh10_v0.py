#!/usr/bin/env python3
"""Fresh10 A/B for Payback Closure Candidate v0 vs Current G17."""
import json
import os
from pathlib import Path

from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as current
import payback_closure_candidate_v0 as candidate

OPPONENT = base.OPPONENT
CASES = [(5401+i, i%2) for i in range(10)]
OUT = Path("payback_closure_candidate_fresh10_v0.json")


def configure(module):
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
    module.set_probe_enabled(True)
    module.set_attribution_enabled(True)
    if hasattr(module, "reset_experiment"):
        module.reset_experiment()
    else:
        module.reset_telemetry()


def play(fn, module, seed, seat):
    configure(module)
    env = make("kaggriculture", configuration={"seed":seed}, debug=False)
    players=[OPPONENT, OPPONENT]
    players[seat]=fn
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    acts = module.get_activations() if hasattr(module, "get_activations") else []
    return {
        "self":rewards[seat],
        "opp":rewards[1-seat],
        "margin":rewards[seat]-rewards[1-seat],
        "win":rewards[seat] > rewards[1-seat],
        "activations":acts,
    }


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def main():
    rows=[]
    for seed,seat in CASES:
        b=play(current.agent,current,seed,seat)
        c=play(candidate.agent,candidate,seed,seat)
        rows.append({
            "seed":seed,
            "seat":seat,
            "activation_count":len(c["activations"]),
            "activation_days":sorted({a["day"] for a in c["activations"]}),
            "current":{"self":b["self"],"margin":b["margin"],"win":b["win"]},
            "candidate":{"self":c["self"],"margin":c["margin"],"win":c["win"]},
            "self_diff":c["self"]-b["self"],
            "margin_diff":c["margin"]-b["margin"],
        })

    summary={
        "case_count":len(rows),
        "activated_cases":sum(r["activation_count"]>0 for r in rows),
        "activation_count":sum(r["activation_count"] for r in rows),
        "improved":sum(r["self_diff"]>0 for r in rows),
        "worsened":sum(r["self_diff"]<0 for r in rows),
        "equal":sum(r["self_diff"]==0 for r in rows),
        "mean_self_current":mean([r["current"]["self"] for r in rows]),
        "mean_self_candidate":mean([r["candidate"]["self"] for r in rows]),
        "mean_self_diff":mean([r["self_diff"] for r in rows]),
        "mean_margin_diff":mean([r["margin_diff"] for r in rows]),
        "current_wins":sum(r["current"]["win"] for r in rows),
        "candidate_wins":sum(r["candidate"]["win"] for r in rows),
    }

    result={
        "schema":"kaggriculture.payback-closure-candidate.fresh10.v0",
        "objective":"terminal self money primary; win count and margin supplemental",
        "candidate":"remaining_horizon <= 14 => suppress new expansion purchases",
        "boundary":"coarse Battle candidate only; not a general payback law or adopted Combat Rule",
        "cases":rows,
        "summary":summary,
    }
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PAYBACK_CLOSURE_FRESH10_SUMMARY "+json.dumps(summary,separators=(",",":")))
    print("PAYBACK_CLOSURE_FRESH10_ROWS "+json.dumps(rows,separators=(",",":")))

if __name__=="__main__":
    main()
