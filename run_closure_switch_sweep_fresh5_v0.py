#!/usr/bin/env python3
"""Closure switch timing sweep: Current + Day16/18/20/22/24 x same fresh5."""
import json
import os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import closure_switch_sweep_v0 as agent

OPPONENT = base.OPPONENT
CASES = [(5201+i, i%2) for i in range(5)]
MODELS = [("CURRENT", None), ("D16",16), ("D18",18), ("D20",20), ("D22",22), ("D24",24)]
OUT = Path("closure_switch_sweep_fresh5_v0.json")

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
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_experiment()
    agent.set_switch_day(day)

def play(label, day, seed, seat):
    configure(day)
    env = make("kaggriculture", configuration={"seed":seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = agent.agent
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    acts = agent.get_activations()
    return {
        "model":label,
        "switch_day":day,
        "seed":seed,
        "seat":seat,
        "self":rewards[seat],
        "opp":rewards[1-seat],
        "margin":rewards[seat]-rewards[1-seat],
        "win_loss":"win" if rewards[seat]>rewards[1-seat] else "loss" if rewards[seat]<rewards[1-seat] else "draw",
        "activation_count":len(acts),
        "activation_days":sorted({a["day"] for a in acts}),
    }

def mean(xs):
    return sum(xs)/len(xs) if xs else None

def main():
    rows=[play(label,day,seed,seat) for label,day in MODELS for seed,seat in CASES]
    base={(r["seed"],r["seat"]):r for r in rows if r["model"]=="CURRENT"}
    summary={}
    for label,day in MODELS:
        rs=[r for r in rows if r["model"]==label]
        diffs=[r["self"]-base[(r["seed"],r["seat"])]["self"] for r in rs]
        summary[label]={
            "switch_day":day,
            "battle_count":len(rs),
            "mean_self":mean([r["self"] for r in rs]),
            "mean_margin":mean([r["margin"] for r in rs]),
            "wins":sum(r["win_loss"]=="win" for r in rs),
            "activated_cases":sum(r["activation_count"]>0 for r in rs),
            "activation_count":sum(r["activation_count"] for r in rs),
            "improved_vs_current":sum(d>0 for d in diffs),
            "worsened_vs_current":sum(d<0 for d in diffs),
            "equal_vs_current":sum(d==0 for d in diffs),
            "mean_self_diff_vs_current":mean(diffs),
        }
    payload={
        "schema":"kaggriculture.closure-switch-sweep.fresh5.v0",
        "question":"where is the coarse terminal-self response along one closure switch-day axis?",
        "single_knob":"from switch_day onward suppress all new expansion purchases",
        "models":[x[0] for x in MODELS],
        "cases":CASES,
        "boundary":[
            "Switch days are test coordinates, not inferred optima.",
            "No adoption from fresh5.",
            "This maps one axis only; no internal trace interpretation."
        ],
        "rows":rows,
        "summary":summary,
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CLOSURE_SWITCH_SWEEP_SUMMARY "+json.dumps(summary,separators=(",",":")))
    print("CLOSURE_SWITCH_SWEEP_ROWS "+json.dumps(rows,separators=(",",":")))

if __name__=="__main__":
    main()
