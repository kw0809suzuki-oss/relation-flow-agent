#!/usr/bin/env python3
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import cow_first_purchase_suppress_v0 as candidate
from economic_flow_upstream_observer_v01 import EconomicFlowUpstreamObserver

OPPONENT = base.OPPONENT
FRESH10 = [(4402 + i, i % 2) for i in range(10)]
STATE_PROXIES = (
    "money","cash_delta","drawdown","cows","farm_cows","wheat","feed_need",
    "outputs","land","units","feed_gap","feed_stress","cow_workload",
    "output_residence_streak",
)
ACTION_PROXIES = (
    "cum_BUY_ANIMAL_COW","cum_BUY_PRODUCT_COW","cum_BUY_SEED_WHEAT",
    "cum_BUY_PRODUCT_WHEAT","cum_BUY_LAND","cum_HIRE","cum_SELL",
    "cum_unit_MOVE","cum_unit_WORK","cum_unit_PASS","cum_unit_OTHER",
)
PROXIES = STATE_PROXIES + ACTION_PROXIES


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    baseline.set_control_enabled(False)
    baseline.set_probe_enabled(True)
    baseline.set_attribution_enabled(True)
    baseline.reset_telemetry()


def play(agent_fn, seed, seat, reset=None):
    configure()
    if reset:
        reset()
    observer = EconomicFlowUpstreamObserver()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        observer.observe(obs)
        action = agent_fn(obs)
        observer.observe_action(action)
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return {
        "score": {"self": rewards[seat], "opp": rewards[1-seat], "margin": rewards[seat]-rewards[1-seat]},
        "rows": observer.rows,
    }


def val(row, key):
    v = row.get(key, 0)
    if isinstance(v, bool):
        return int(v)
    return float(v or 0)


def paired_deltas(b, c):
    n = min(len(b["rows"]), len(c["rows"]))
    out = []
    for i in range(n):
        br, cr = b["rows"][i], c["rows"][i]
        out.append({
            "turn": i,
            "day": cr["day"],
            **{p: val(cr,p) - val(br,p) for p in PROXIES},
        })
    return out


def earliest_strict(cases, left_class, right_class, before_turn=None):
    max_turn = min(len(c["deltas"]) for c in cases)
    if before_turn is not None:
        max_turn = min(max_turn, before_turn)
    for turn in range(max_turn):
        found = []
        for p in PROXIES:
            a = [c["deltas"][turn][p] for c in cases if c["class"] == left_class]
            b = [c["deltas"][turn][p] for c in cases if c["class"] == right_class]
            if not a or not b:
                continue
            rel = None
            if max(a) < min(b):
                rel = left_class + "_below_" + right_class
            elif max(b) < min(a):
                rel = left_class + "_above_" + right_class
            if rel:
                found.append({
                    "turn": turn,
                    "day": cases[0]["deltas"][turn]["day"],
                    "proxy": p,
                    "relation": rel,
                    left_class: {"min": min(a), "max": max(a), "values": a},
                    right_class: {"min": min(b), "max": max(b), "values": b},
                })
        if found:
            return found
    return []


def first_nonzero_each_case(cases):
    result = {}
    for c in cases:
        rows = c["deltas"]
        first = {}
        for p in PROXIES:
            for r in rows:
                if abs(r[p]) > 1e-12:
                    first[p] = {"turn": r["turn"], "day": r["day"], "delta": r[p]}
                    break
        result[str(c["seed"])] = first
    return result


def main():
    cases=[]
    for seed, seat in FRESH10:
        b=play(baseline.agent, seed, seat)
        c=play(candidate.agent, seed, seat, candidate.reset_experiment)
        self_diff=c["score"]["self"]-b["score"]["self"]
        cls="improved" if self_diff>0 else ("worsened" if self_diff<0 else "equal")
        cases.append({
            "seed":seed,"seat":seat,"class":cls,"accident3":seed in (4404,4407,4409),
            "self_diff":self_diff,
            "margin_diff":c["score"]["margin"]-b["score"]["margin"],
            "deltas":paired_deltas(b,c),
        })

    strict_pre_cash = earliest_strict(cases,"improved","worsened",before_turn=224)
    accident_cases=[]
    for c in cases:
        if c["class"]=="improved":
            cc=dict(c); cc["class"]="improved"; accident_cases.append(cc)
        elif c["accident3"]:
            cc=dict(c); cc["class"]="accident"; accident_cases.append(cc)
    strict_pre_accident_cash=earliest_strict(accident_cases,"improved","accident",before_turn=198)

    out={
        "schema":"kaggriculture.economic-flow-upstream-observer.v0.1",
        "source":{"historical_commit":"27cac110515eca257c157904984add017d5ea8bb","historical_run":35422159593},
        "window":{"full_worsened_cash_separator_turn":224,"accident3_cash_separator_turn":198},
        "principle":{"observer_only":True,"unified_score":False,"search_before_known_cash_separator":True},
        "proxies":{"state":STATE_PROXIES,"cumulative_actions":ACTION_PROXIES},
        "cases":cases,
        "summary":{
            "improved":sum(c["class"]=="improved" for c in cases),
            "worsened":sum(c["class"]=="worsened" for c in cases),
            "earliest_strict_pre_cash":strict_pre_cash,
            "earliest_strict_pre_accident_cash":strict_pre_accident_cash,
            "first_nonzero_by_seed":first_nonzero_each_case(cases),
        },
        "boundary":"upstream_proxy_observation_only_no_causal_claim_no_candidate_adoption",
        "promote":False,
    }
    Path("cow_economic_flow_upstream_v01.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        "improved":out["summary"]["improved"],
        "worsened":out["summary"]["worsened"],
        "earliest_strict_pre_cash":strict_pre_cash,
        "earliest_strict_pre_accident_cash":strict_pre_accident_cash,
    },ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
