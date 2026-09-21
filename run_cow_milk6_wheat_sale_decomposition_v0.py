#!/usr/bin/env python3
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import cow_first_purchase_suppress_v0 as candidate
from milk6_cashback_decomposition_observer_v0 import Milk6CashbackDecompositionObserver

OPPONENT = base.OPPONENT
FRESH10 = [(4402 + i, i % 2) for i in range(10)]
FROM_TURN = 197
TO_TURN = 198


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
    observer = Milk6CashbackDecompositionObserver()
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


def normalize_sell(a):
    if not isinstance(a, (list, tuple)) or len(a) < 2 or a[0] != "SELL":
        return None
    item = a[1] if len(a) > 1 else None
    qty = a[2] if len(a) > 2 else None
    try:
        qty = int(qty) if qty is not None else None
    except Exception:
        pass
    return {"raw": list(a), "item": item, "qty": qty}


def one_transition(play_result):
    rows = {r["turn"]: r for r in play_result["rows"]}
    a = rows[FROM_TURN]
    b = rows[TO_TURN]
    items0 = a.get("item_totals", {})
    items1 = b.get("item_totals", {})
    item_delta = {
        k: items1.get(k, 0) - items0.get(k, 0)
        for k in sorted(set(items0) | set(items1))
    }
    market = list(a.get("raw_market", []) or [])
    sells = [x for x in (normalize_sell(m) for m in market) if x is not None]
    spends = [list(m) for m in market if isinstance(m,(list,tuple)) and m and (m[0].startswith("BUY_") or m[0] == "HIRE")]

    sold_by_item = {}
    for s in sells:
        if isinstance(s["qty"], int):
            sold_by_item[s["item"]] = sold_by_item.get(s["item"], 0) + s["qty"]

    money_jump = float(b["money"] - a["money"])
    milk_drop = max(0, -int(item_delta.get("MILK", 0)))
    wheat_drop = max(0, -int(item_delta.get("WHEAT", 0)))

    return {
        "money_before": a["money"],
        "money_after": b["money"],
        "money_jump": money_jump,
        "item_before": items0,
        "item_after": items1,
        "item_delta": item_delta,
        "raw_market": market,
        "sells": sells,
        "spends": spends,
        "sold_by_item_from_action": sold_by_item,
        "milk_drop": milk_drop,
        "wheat_drop": wheat_drop,
        "observed_sale_mix": {
            "milk_only": milk_drop > 0 and wheat_drop == 0,
            "milk_plus_wheat": milk_drop > 0 and wheat_drop > 0,
            "wheat_only": wheat_drop > 0 and milk_drop == 0,
        },
        "net_cash_per_milk_if_no_wheat_drop": (
            money_jump / milk_drop if milk_drop > 0 and wheat_drop == 0 else None
        ),
        "preceding_farmer": a.get("farmer_action"),
        "preceding_hands": a.get("hand_actions", []),
    }


def main():
    cases = []
    for seed, seat in FRESH10:
        b = play(baseline.agent, seed, seat)
        c = play(candidate.agent, seed, seat, candidate.reset_experiment)
        self_diff = c["score"]["self"] - b["score"]["self"]
        cls = "improved" if self_diff > 0 else ("worsened" if self_diff < 0 else "equal")
        bt = one_transition(b)
        ct = one_transition(c)
        cases.append({
            "seed": seed,
            "seat": seat,
            "class": cls,
            "accident3": seed in (4404, 4407, 4409),
            "self_diff": self_diff,
            "margin_diff": c["score"]["margin"] - b["score"]["margin"],
            "baseline": bt,
            "candidate": ct,
            "paired": {
                "money_jump_delta": ct["money_jump"] - bt["money_jump"],
                "milk_drop_delta": ct["milk_drop"] - bt["milk_drop"],
                "wheat_drop_delta": ct["wheat_drop"] - bt["wheat_drop"],
                "candidate_sold_by_item_from_action": ct["sold_by_item_from_action"],
                "baseline_sold_by_item_from_action": bt["sold_by_item_from_action"],
            },
        })

    def subset(pred):
        return [x for x in cases if pred(x)]

    improved = subset(lambda x: x["class"]=="improved")
    worsened = subset(lambda x: x["class"]=="worsened")
    accident = subset(lambda x: x["accident3"])

    def summarize(group):
        return {
            "count": len(group),
            "candidate_mix": {
                "milk_only": sum(x["candidate"]["observed_sale_mix"]["milk_only"] for x in group),
                "milk_plus_wheat": sum(x["candidate"]["observed_sale_mix"]["milk_plus_wheat"] for x in group),
                "wheat_only": sum(x["candidate"]["observed_sale_mix"]["wheat_only"] for x in group),
            },
            "candidate_wheat_drop_values": [x["candidate"]["wheat_drop"] for x in group],
            "candidate_money_jump_values": [x["candidate"]["money_jump"] for x in group],
            "candidate_sell_actions": [x["candidate"]["sells"] for x in group],
            "candidate_spends": [x["candidate"]["spends"] for x in group],
            "pure_milk_net_cash_per_milk": [
                x["candidate"]["net_cash_per_milk_if_no_wheat_drop"]
                for x in group
                if x["candidate"]["net_cash_per_milk_if_no_wheat_drop"] is not None
            ],
        }

    out = {
        "schema": "kaggriculture.milk6-wheat-sale-decomposition.v0",
        "source": {
            "historical_commit": "27cac110515eca257c157904984add017d5ea8bb",
            "historical_run": 35422159593,
            "transition": "197->198",
        },
        "principle": {
            "observer_only": True,
            "confirmed_input": "accident3 had lower realized cash-back on same MILK6 drop",
            "goal": "separate MILK and WHEAT contribution in the transition",
            "causal_claim": False,
        },
        "cases": cases,
        "summary": {
            "improved": summarize(improved),
            "worsened": summarize(worsened),
            "accident3": summarize(accident),
            "all_candidate_milk_drop_6": all(x["candidate"]["milk_drop"] == 6 for x in cases),
        },
        "boundary": "sale_mix_observation_only_no_price_causal_claim_no_candidate_adoption",
        "promote": False,
    }

    Path("cow_milk6_wheat_sale_decomposition_v0.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(out["summary"], ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
