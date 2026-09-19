#!/usr/bin/env python3
"""Run only the uncovered bundle directions: M3/M4/M6/M7 x same fresh5.

M0/M2 are reused from Run #35440537012 rather than re-bought.
"""
import json
import os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import closure_timing_bundle_v1 as agent

OPPONENT = base.OPPONENT
CASES = [(5201+i, i%2) for i in range(5)]
MODELS = ["M3","M4","M6","M7"]
OUT = Path("closure_timing_bundle_fresh5_v1.json")

REFERENCE = {
    5201: {"seat":0,"M0_self":26932.0,"M2_self":29581.0},
    5202: {"seat":1,"M0_self":38671.0,"M2_self":40178.0},
    5203: {"seat":0,"M0_self":20147.0,"M2_self":21243.0},
    5204: {"seat":1,"M0_self":35526.0,"M2_self":35793.0},
    5205: {"seat":0,"M0_self":11379.0,"M2_self":14636.0},
}

def configure(model):
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
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_experiment()
    agent.set_variant(model)

def play(model, seed, seat):
    configure(model)
    env = make("kaggriculture", configuration={"seed":seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = agent.agent
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    acts = agent.get_activations()
    ref = REFERENCE[seed]
    return {
        "model": model,
        "seed": seed,
        "seat": seat,
        "self": rewards[seat],
        "opp": rewards[1-seat],
        "margin": rewards[seat]-rewards[1-seat],
        "win_loss": "win" if rewards[seat] > rewards[1-seat] else "loss" if rewards[seat] < rewards[1-seat] else "draw",
        "activation_count": len(acts),
        "activation_days": sorted({a["day"] for a in acts}),
        "self_diff_vs_M0": rewards[seat]-ref["M0_self"],
        "self_diff_vs_M2": rewards[seat]-ref["M2_self"],
    }

def mean(xs):
    return sum(xs)/len(xs) if xs else None

def main():
    rows = [play(m,s,seat) for m in MODELS for s,seat in CASES]
    summary = {}
    for m in MODELS:
        rs=[r for r in rows if r["model"]==m]
        summary[m]={
            "battle_count":len(rs),
            "mean_self":mean([r["self"] for r in rs]),
            "mean_margin":mean([r["margin"] for r in rs]),
            "wins":sum(r["win_loss"]=="win" for r in rs),
            "activated_cases":sum(r["activation_count"]>0 for r in rs),
            "activation_count":sum(r["activation_count"] for r in rs),
            "improved_vs_M0":sum(r["self_diff_vs_M0"]>0 for r in rs),
            "worsened_vs_M0":sum(r["self_diff_vs_M0"]<0 for r in rs),
            "mean_self_diff_vs_M0":mean([r["self_diff_vs_M0"] for r in rs]),
            "improved_vs_M2":sum(r["self_diff_vs_M2"]>0 for r in rs),
            "worsened_vs_M2":sum(r["self_diff_vs_M2"]<0 for r in rs),
            "mean_self_diff_vs_M2":mean([r["self_diff_vs_M2"] for r in rs]),
        }
    payload={
        "schema":"kaggriculture.closure-timing-bundle.fresh5.v1",
        "reference_run":35440537012,
        "reference_note":"M0 and M2 are reused from the paired M2 fresh5 run on the same seeds/seats.",
        "models":MODELS,
        "definitions":{
            "M3":"Day26+ stop all new expansion",
            "M4":"time-weighted cash reserve, linear with elapsed season fraction",
            "M6":"recovery-first: SEED>=4 days, COW>=8 days; LAND untouched",
            "M7":"Day20+ stop LAND/COW; Day26+ stop all expansion",
        },
        "boundary":[
            "All thresholds are test knobs, not inferred optima.",
            "No adoption from fresh5.",
            "This is external design-space mapping, not winner ranking."
        ],
        "rows":rows,
        "summary":summary,
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CLOSURE_TIMING_BUNDLE_SUMMARY "+json.dumps(summary,separators=(",",":")))
    print("CLOSURE_TIMING_BUNDLE_ROWS "+json.dumps(rows,separators=(",",":")))

if __name__=="__main__":
    main()
