#!/usr/bin/env python3
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import cow_first_purchase_suppress_v0 as candidate
from cash_jump_transition_observer_v0 import CashJumpTransitionObserver

OPPONENT = base.OPPONENT
FRESH10 = [(4402 + i, i % 2) for i in range(10)]
WINDOW = range(190, 201)


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
    observer = CashJumpTransitionObserver()
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


def compact(row):
    return {
        "turn": row["turn"],
        "day": row["day"],
        "money": row["money"],
        "cash_delta": row["cash_delta"],
        "items": row.get("item_totals", {}),
        "cows": row["cows"],
        "farm_cows": row["farm_cows"],
        "feed_need": row["feed_need"],
        "outputs": row["outputs"],
        "market_semantic": row.get("market_semantic", []),
        "farmer_action": row.get("farmer_action"),
        "hand_actions": row.get("hand_actions", []),
    }


def transition(prev_row, row):
    items0 = prev_row.get("item_totals", {})
    items1 = row.get("item_totals", {})
    return {
        "from_turn": prev_row["turn"],
        "to_turn": row["turn"],
        "day": row["day"],
        "money_jump": row["money"] - prev_row["money"],
        "item_delta": {k: items1.get(k,0)-items0.get(k,0) for k in sorted(set(items0)|set(items1))},
        "preceding_market": prev_row.get("market_semantic", []),
        "preceding_farmer": prev_row.get("farmer_action"),
        "preceding_hands": prev_row.get("hand_actions", []),
    }


def paired_transition_delta(bt, ct):
    return {
        "money_jump_delta": ct["money_jump"] - bt["money_jump"],
        "item_delta_diff": {k: ct["item_delta"].get(k,0)-bt["item_delta"].get(k,0) for k in sorted(set(bt["item_delta"])|set(ct["item_delta"]))},
        "baseline_preceding_market": bt["preceding_market"],
        "candidate_preceding_market": ct["preceding_market"],
        "baseline_preceding_farmer": bt["preceding_farmer"],
        "candidate_preceding_farmer": ct["preceding_farmer"],
        "baseline_preceding_hands": bt["preceding_hands"],
        "candidate_preceding_hands": ct["preceding_hands"],
    }


def main():
    cases=[]
    for seed, seat in FRESH10:
        b=play(baseline.agent, seed, seat)
        c=play(candidate.agent, seed, seat, candidate.reset_experiment)
        self_diff=c["score"]["self"]-b["score"]["self"]
        cls="improved" if self_diff>0 else ("worsened" if self_diff<0 else "equal")

        bwin={r["turn"]:r for r in b["rows"] if r["turn"] in WINDOW}
        cwin={r["turn"]:r for r in c["rows"] if r["turn"] in WINDOW}
        transitions={}
        for t in range(191,201):
            if t-1 in bwin and t in bwin and t-1 in cwin and t in cwin:
                bt=transition(bwin[t-1],bwin[t])
                ct=transition(cwin[t-1],cwin[t])
                transitions[str(t)] = {
                    "baseline": bt,
                    "candidate": ct,
                    "paired": paired_transition_delta(bt,ct),
                }

        cases.append({
            "seed":seed,"seat":seat,"class":cls,"accident3":seed in (4404,4407,4409),
            "self_diff":self_diff,
            "margin_diff":c["score"]["margin"]-b["score"]["margin"],
            "baseline_window":[compact(bwin[t]) for t in sorted(bwin)],
            "candidate_window":[compact(cwin[t]) for t in sorted(cwin)],
            "transitions":transitions,
        })

    # Rank transitions by how strongly candidate-vs-baseline money jump differs between classes.
    ranking=[]
    for t in range(191,201):
        imp=[x["transitions"][str(t)]["paired"]["money_jump_delta"] for x in cases if x["class"]=="improved" and str(t) in x["transitions"]]
        wor=[x["transitions"][str(t)]["paired"]["money_jump_delta"] for x in cases if x["class"]=="worsened" and str(t) in x["transitions"]]
        if imp and wor:
            ranking.append({
                "to_turn":t,
                "improved":{"min":min(imp),"max":max(imp),"values":imp},
                "worsened":{"min":min(wor),"max":max(wor),"values":wor},
                "strict_nonoverlap": max(imp)<min(wor) or max(wor)<min(imp),
                "mean_gap": (sum(imp)/len(imp))-(sum(wor)/len(wor)),
            })

    out={
        "schema":"kaggriculture.cash-jump-transition-observer.v0",
        "source":{"historical_commit":"27cac110515eca257c157904984add017d5ea8bb","historical_run":35422159593},
        "window":{"turn_start":190,"turn_end":200,"focus_transition":"197->198"},
        "principle":{"observer_only":True,"causal_claim":False,"candidate_adoption":False},
        "cases":cases,
        "summary":{
            "improved":sum(x["class"]=="improved" for x in cases),
            "worsened":sum(x["class"]=="worsened" for x in cases),
            "transition_money_jump_ranking":ranking,
        },
        "boundary":"transition_observation_only_no_causal_claim_no_candidate_adoption",
        "promote":False,
    }
    Path("cow_cash_jump_transition_v0.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(out["summary"],ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
