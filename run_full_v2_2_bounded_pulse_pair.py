#!/usr/bin/env python3
"""Fresh-50 paired falsification test: Full v1 vs Whole v2.2 bounded pulse."""

import copy
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import full_strong_origin_v1 as baseline_agent
import full_strong_origin_v2_2_bounded_pulse as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3712) % 2) for seed in range(3712, 3762))


def score(rewards, seat):
    own = float(rewards[seat])
    opponent = float(rewards[1-seat])
    return {"self": own, "opponent": opponent, "margin": own-opponent, "win": own > opponent}


def play(seed, seat, module):
    module.reset_telemetry()
    actions = []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        action = module.agent(obs)
        actions.append(copy.deepcopy(action))
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]
    return {"score": score(rewards, seat), "actions": actions, "telemetry": module.get_telemetry()}


def percentile(values, p):
    vals = sorted(values)
    k = (len(vals)-1)*p
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return vals[lo]
    return vals[lo]*(hi-k)+vals[hi]*(k-lo)


def first_difference(left, right):
    for i, (a,b) in enumerate(zip(left,right)):
        if a != b:
            return i
    return None


def main():
    rows=[]
    for seed, seat in CASES:
        baseline = play(seed, seat, baseline_agent)
        candidate = play(seed, seat, candidate_agent)
        delta = {k: candidate["score"][k]-baseline["score"][k] for k in ("self","opponent","margin")}
        rows.append({
            "seed": seed,
            "seat": seat,
            "baseline": baseline["score"],
            "candidate": candidate["score"],
            "terminal_delta": delta,
            "self_direction": "improved" if delta["self"]>0 else "worsened" if delta["self"]<0 else "equal",
            "margin_direction": "improved" if delta["margin"]>0 else "worsened" if delta["margin"]<0 else "equal",
            "first_action_difference": first_difference(candidate["actions"], baseline["actions"]),
            "action_difference_count": sum(a!=b for a,b in zip(candidate["actions"], baseline["actions"])),
            "candidate_telemetry": candidate["telemetry"],
        })

    self_deltas=[r["terminal_delta"]["self"] for r in rows]
    margin_deltas=[r["terminal_delta"]["margin"] for r in rows]
    candidate_scores=[r["candidate"]["self"] for r in rows]
    baseline_scores=[r["baseline"]["self"] for r in rows]
    totals=Counter()
    for row in rows:
        for key,value in row["candidate_telemetry"].get("whole_v2_2",{}).items():
            if isinstance(value,(int,float)):
                totals[key]+=value

    summary={
        "case_count":len(rows),
        "primary_metric":"self_score_delta",
        "mean_self_delta":statistics.mean(self_deltas),
        "median_self_delta":statistics.median(self_deltas),
        "self_direction_counts":dict(Counter(r["self_direction"] for r in rows)),
        "mean_margin_delta":statistics.mean(margin_deltas),
        "median_margin_delta":statistics.median(margin_deltas),
        "margin_direction_counts":dict(Counter(r["margin_direction"] for r in rows)),
        "baseline_wins":sum(r["baseline"]["win"] for r in rows),
        "candidate_wins":sum(r["candidate"]["win"] for r in rows),
        "baseline_self_mean":statistics.mean(baseline_scores),
        "candidate_self_mean":statistics.mean(candidate_scores),
        "baseline_self_stdev":statistics.pstdev(baseline_scores),
        "candidate_self_stdev":statistics.pstdev(candidate_scores),
        "baseline_self_p10":percentile(baseline_scores,0.10),
        "candidate_self_p10":percentile(candidate_scores,0.10),
        "baseline_self_min":min(baseline_scores),
        "candidate_self_min":min(candidate_scores),
        "largest_self_improvement":max(self_deltas),
        "largest_self_worsening":min(self_deltas),
        "action_difference_cases":sum(r["first_action_difference"] is not None for r in rows),
        "total_action_differences":sum(r["action_difference_count"] for r in rows),
        "whole_v2_2_totals":dict(totals),
    }
    result={
        "schema":"kaggriculture.full-v2-2-bounded-pulse-pair.v1",
        "question":"does bounding zero-detour intervention episodes reduce downside while intervention still genuinely fires?",
        "falsification_target":"continuity-break intervention cost hypothesis",
        "baseline":"full_strong_origin_v1.py",
        "candidate":"full_strong_origin_v2_2_bounded_pulse.py",
        "cases":rows,
        "summary":summary,
        "runtime_inputs_excluded":["seed","paired_difference","terminal_reward","future_state"],
        "baseline_mutated":False,
        "causal_attribution":False,
        "evaluation_rule":"if bounded episodes still show similar self-score downside while firing materially, continuity-break hypothesis weakens; if downside contracts materially, hypothesis survives but is not proven",
    }
    Path("full_v2_2_bounded_pulse_pair_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("FULL_V2_2_BOUNDED_PULSE_PAIR "+json.dumps(summary,separators=(",",":")))

if __name__=="__main__":
    main()
