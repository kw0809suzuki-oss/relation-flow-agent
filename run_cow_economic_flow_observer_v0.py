#!/usr/bin/env python3
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import cow_first_purchase_suppress_v0 as candidate
from economic_flow_observer_v0 import EconomicFlowObserver

OPPONENT = base.OPPONENT
FRESH10 = [(4402 + i, i % 2) for i in range(10)]
PROXIES = (
    "money", "drawdown", "feed_gap", "feed_stress",
    "outputs", "output_residence_streak", "cow_workload",
)


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
    observer = EconomicFlowObserver()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        observer.observe(obs)
        return agent_fn(obs)

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return {
        "score": {
            "self": rewards[seat],
            "opp": rewards[1-seat],
            "margin": rewards[seat] - rewards[1-seat],
        },
        "flow_rows": observer.rows,
        "flow_summary": observer.summary(),
    }


def paired_proxy_deltas(b, c):
    n = min(len(b["flow_rows"]), len(c["flow_rows"]))
    rows = []
    for i in range(n):
        br, cr = b["flow_rows"][i], c["flow_rows"][i]
        rows.append({
            "turn": i,
            "day": cr["day"],
            **{p: cr[p] - br[p] for p in PROXIES},
        })
    return rows


def strict_separators(cases, positive_class, negative_class):
    out = []
    max_turn = min(len(c["proxy_deltas"]) for c in cases)
    for turn in range(max_turn):
        for proxy in PROXIES:
            a = [c["proxy_deltas"][turn][proxy] for c in cases if c["class"] == positive_class]
            b = [c["proxy_deltas"][turn][proxy] for c in cases if c["class"] == negative_class]
            if not a or not b:
                continue
            relation = None
            if max(a) < min(b):
                relation = f"{positive_class}_below_{negative_class}"
            elif max(b) < min(a):
                relation = f"{positive_class}_above_{negative_class}"
            if relation:
                out.append({
                    "turn": turn,
                    "day": cases[0]["proxy_deltas"][turn]["day"],
                    "proxy": proxy,
                    "relation": relation,
                    positive_class: {"min": min(a), "max": max(a), "values": a},
                    negative_class: {"min": min(b), "max": max(b), "values": b},
                })
        if out:
            first_turn = min(x["turn"] for x in out)
            return [x for x in out if x["turn"] == first_turn]
    return []


def main():
    cases = []
    for seed, seat in FRESH10:
        b = play(baseline.agent, seed, seat)
        c = play(candidate.agent, seed, seat, candidate.reset_experiment)
        acts = candidate.get_activations()
        self_diff = c["score"]["self"] - b["score"]["self"]
        cls = "improved" if self_diff > 0 else ("worsened" if self_diff < 0 else "equal")
        cases.append({
            "seed": seed,
            "seat": seat,
            "class": cls,
            "accident3": seed in (4404, 4407, 4409),
            "activation_count": len(acts),
            "baseline_score": b["score"],
            "candidate_score": c["score"],
            "self_diff": self_diff,
            "margin_diff": c["score"]["margin"] - b["score"]["margin"],
            "baseline_flow_summary": b["flow_summary"],
            "candidate_flow_summary": c["flow_summary"],
            "proxy_deltas": paired_proxy_deltas(b, c),
        })

    improved_vs_worsened = strict_separators(cases, "improved", "worsened")

    reduced = []
    for c in cases:
        if c["class"] == "improved":
            cc = dict(c)
            cc["class"] = "improved"
            reduced.append(cc)
        elif c["accident3"]:
            cc = dict(c)
            cc["class"] = "accident"
            reduced.append(cc)
    improved_vs_accident = strict_separators(reduced, "improved", "accident")

    out = {
        "schema": "kaggriculture.economic-flow-observer.v0",
        "source": {
            "historical_commit": "27cac110515eca257c157904984add017d5ea8bb",
            "historical_run": 35422159593,
            "intervention": "suppress first native BUY_ANIMAL COW 1 once per match",
            "cases": "fresh10 seeds 4402-4411",
        },
        "principle": {
            "observer_only": True,
            "unified_economic_score": False,
            "core_variable_confirmed": False,
            "selection_rule": "earliest strict non-overlap of paired proxy deltas",
        },
        "proxy_definitions": {
            "money": "observed self cash",
            "drawdown": "running peak cash minus current cash",
            "feed_gap": "max(0, unfed farm cows - held WHEAT)",
            "feed_stress": "feed_gap / max(1, unfed farm cows)",
            "outputs": "held MILK+WOOL+EGG+FERTILIZER; weak residence/backlog proxy",
            "output_residence_streak": "consecutive observed calls with outputs > 0",
            "cow_workload": "farm cows / active units",
            "recovery": "calls from first drop below running cash peak until cash regains that peak",
            "monetization_signal": "output inventory falls while cash rises",
        },
        "cases": cases,
        "summary": {
            "improved": sum(c["class"] == "improved" for c in cases),
            "worsened": sum(c["class"] == "worsened" for c in cases),
            "equal": sum(c["class"] == "equal" for c in cases),
            "accident3": sum(c["accident3"] for c in cases),
            "earliest_improved_vs_worsened": improved_vs_worsened,
            "earliest_improved_vs_accident3": improved_vs_accident,
        },
        "boundary": "proxy_observation_only_no_core_theory_promotion_no_candidate_adoption",
        "promote": False,
    }
    Path("cow_economic_flow_observer_v0.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(out["summary"], ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
