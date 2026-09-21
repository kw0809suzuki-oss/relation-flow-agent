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
        "score": {
            "self": rewards[seat],
            "opp": rewards[1-seat],
            "margin": rewards[seat] - rewards[1-seat],
        },
        "rows": observer.rows,
    }


def classify_market(actions):
    kinds = []
    sells = []
    spends = []
    for a in actions or []:
        if not isinstance(a, (list, tuple)) or not a:
            continue
        kind = a[0]
        kinds.append(kind)
        if kind == "SELL":
            sells.append(list(a))
        elif kind.startswith("BUY_") or kind == "HIRE":
            spends.append(list(a))
    if sells and not spends:
        mode = "sell_only"
    elif sells and spends:
        mode = "sell_plus_spend"
    elif spends and not sells:
        mode = "spend_only"
    else:
        mode = "other_or_none"
    return {"mode": mode, "kinds": kinds, "sells": sells, "spends": spends}


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
    market_class = classify_market(market)
    milk_sold_proxy = max(0, -int(item_delta.get("MILK", 0)))
    money_jump = float(b["money"] - a["money"])
    return {
        "money_before": a["money"],
        "money_after": b["money"],
        "money_jump": money_jump,
        "item_delta": item_delta,
        "milk_sold_proxy": milk_sold_proxy,
        "net_cash_per_milk": (money_jump / milk_sold_proxy) if milk_sold_proxy else None,
        "preceding_market_raw": market,
        "market_class": market_class,
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
                "milk_sold_delta": ct["milk_sold_proxy"] - bt["milk_sold_proxy"],
                "candidate_net_cash_per_milk": ct["net_cash_per_milk"],
                "baseline_net_cash_per_milk": bt["net_cash_per_milk"],
                "candidate_market_mode": ct["market_class"]["mode"],
                "baseline_market_mode": bt["market_class"]["mode"],
            },
        })

    def rows_for(label):
        return [x for x in cases if x["class"] == label]

    improved = rows_for("improved")
    worsened = rows_for("worsened")
    accident = [x for x in cases if x["accident3"]]

    def summarize(group):
        vals = [x["candidate"]["net_cash_per_milk"] for x in group if x["candidate"]["net_cash_per_milk"] is not None]
        jumps = [x["candidate"]["money_jump"] for x in group]
        modes = {}
        for x in group:
            m = x["candidate"]["market_class"]["mode"]
            modes[m] = modes.get(m, 0) + 1
        return {
            "count": len(group),
            "candidate_money_jump": {
                "min": min(jumps) if jumps else None,
                "max": max(jumps) if jumps else None,
                "values": jumps,
            },
            "candidate_net_cash_per_milk": {
                "min": min(vals) if vals else None,
                "max": max(vals) if vals else None,
                "values": vals,
            },
            "candidate_market_modes": modes,
        }

    out = {
        "schema": "kaggriculture.milk6-cashback-decomposition.v0",
        "source": {
            "historical_commit": "27cac110515eca257c157904984add017d5ea8bb",
            "historical_run": 35422159593,
            "transition": "197->198",
        },
        "principle": {
            "observer_only": True,
            "gross_sale_not_inferred_if_concurrent_spend": True,
            "net_cash_per_milk_is_proxy": True,
            "causal_claim": False,
        },
        "cases": cases,
        "summary": {
            "improved": summarize(improved),
            "worsened": summarize(worsened),
            "accident3": summarize(accident),
            "all_candidate_sell_only": all(
                x["candidate"]["market_class"]["mode"] == "sell_only" for x in cases
            ),
            "all_candidate_milk_drop_6": all(
                x["candidate"]["milk_sold_proxy"] == 6 for x in cases
            ),
        },
        "boundary": "decomposition_observation_only_no_price_causal_claim_no_candidate_adoption",
        "promote": False,
    }
    Path("cow_milk6_cashback_decomposition_v0.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(out["summary"], ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
