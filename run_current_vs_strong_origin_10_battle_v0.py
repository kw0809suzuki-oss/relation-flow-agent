#!/usr/bin/env python3
"""Outer Battle comparison: Current Combat Model vs frozen Strong Origin.

No new Rule/Gate/theory. Same fresh10 conditions as current baseline.
Only terminal shape is compared.
"""

import json
import os
import statistics
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as current
import strong_origin

OPPONENT = base.OPPONENT
CASES = [(4602+i, i%2) for i in range(10)]
OUTPUT = Path("current_vs_strong_origin_10_battle_v0.json")


def configure_common():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"


def score(rewards, seat):
    own=float(rewards[seat]); opp=float(rewards[1-seat]); margin=own-opp
    return {
        "self":own,
        "opponent":opp,
        "margin":margin,
        "win_loss":"win" if margin>0 else "loss" if margin<0 else "draw",
    }


def play_current(seed, seat):
    configure_common()
    current.set_control_enabled(False)
    current.set_probe_enabled(True)
    current.set_attribution_enabled(True)
    current.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    players=[OPPONENT,OPPONENT]; players[seat]=current.agent
    env.run(players)
    return score([s.reward for s in env.state], seat)


def play_origin(seed, seat):
    configure_common()
    strong_origin.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    players=[OPPONENT,OPPONENT]; players[seat]=strong_origin.agent
    env.run(players)
    return score([s.reward for s in env.state], seat)


def summarize(rows, key):
    vals=[r[key]["self"] for r in rows]
    margins=[r[key]["margin"] for r in rows]
    return {
        "mean_self":sum(vals)/len(vals),
        "median_self":statistics.median(vals),
        "min_self":min(vals),
        "max_self":max(vals),
        "mean_margin":sum(margins)/len(margins),
        "wins":sum(r[key]["win_loss"]=="win" for r in rows),
        "losses":sum(r[key]["win_loss"]=="loss" for r in rows),
        "draws":sum(r[key]["win_loss"]=="draw" for r in rows),
    }


def main():
    rows=[]
    for seed,seat in CASES:
        c=play_current(seed,seat)
        o=play_origin(seed,seat)
        rows.append({
            "seed":seed,
            "seat":seat,
            "opponent":"Seyamalam v21",
            "current":c,
            "strong_origin":o,
            "self_diff_origin_minus_current":o["self"]-c["self"],
            "margin_diff_origin_minus_current":o["margin"]-c["margin"],
        })

    cur=summarize(rows,"current")
    ori=summarize(rows,"strong_origin")
    comparison={
        "mean_self_diff":ori["mean_self"]-cur["mean_self"],
        "median_self_diff":ori["median_self"]-cur["median_self"],
        "win_diff":ori["wins"]-cur["wins"],
        "improved_self_cases":sum(r["self_diff_origin_minus_current"]>0 for r in rows),
        "worsened_self_cases":sum(r["self_diff_origin_minus_current"]<0 for r in rows),
        "equal_self_cases":sum(r["self_diff_origin_minus_current"]==0 for r in rows),
    }

    out={
        "schema":"kaggriculture.current-vs-strong-origin-10-battle.v0",
        "purpose":"outer Battle only: test whether frozen Strong Origin improves the current 10-battle shape",
        "analysis_boundary":"No internal trace analysis or rescue conditions.",
        "cases":rows,
        "current_summary":cur,
        "strong_origin_summary":ori,
        "comparison":comparison,
    }
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CURRENT_VS_STRONG_ORIGIN_ROWS "+json.dumps(rows,separators=(",",":")))
    print("CURRENT_VS_STRONG_ORIGIN_SUMMARY "+json.dumps({
        "current":cur,
        "strong_origin":ori,
        "comparison":comparison,
    },separators=(",",":")))


if __name__=="__main__":
    main()
