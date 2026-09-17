#!/usr/bin/env python3
"""Matched seed-4119 money trajectory ledger for baseline v6 vs MILK Hold v1.

Accounting observer only: records each pre-action money state, chosen action, and
next-observation money delta. Positive/negative deltas are descriptive net money
movement, not causal inflow/outflow attribution.
"""
import json
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import milk_low_price_hold_v1 as hold

SEED = 4119
SEAT = 1  # fresh20 uses alternating seat: (4119-4102)%2 == 1
OPPONENT = base.OPPONENT


def _money(obs):
    p = int(obs["player"])
    return float(obs["farms"][p].get("money", 0.0))


def _safe_action(action):
    try:
        json.dumps(action)
        return action
    except TypeError:
        return repr(action)


def play(label, agent_fn, reset=None):
    base._configure_baseline()
    if reset:
        reset()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    trace = []
    turn = 0

    def observed(obs):
        nonlocal turn
        money = _money(obs)
        action = agent_fn(obs)
        trace.append({
            "turn": turn,
            "day": int(obs.get("day", 0)),
            "money_before_action": money,
            "action": _safe_action(action),
        })
        turn += 1
        return action

    players = [OPPONENT, OPPONENT]
    players[SEAT] = observed
    env.run(players)
    rewards = [float(s.reward) for s in env.state]

    # Exact observable net movement between consecutive decision observations.
    for i, row in enumerate(trace):
        if i + 1 < len(trace):
            delta = trace[i + 1]["money_before_action"] - row["money_before_action"]
            row["next_money"] = trace[i + 1]["money_before_action"]
            row["net_money_delta"] = delta
            row["positive_net"] = max(0.0, delta)
            row["negative_net"] = max(0.0, -delta)
        else:
            row["next_money"] = None
            row["net_money_delta"] = None
            row["positive_net"] = None
            row["negative_net"] = None

    return {
        "label": label,
        "terminal_self": rewards[SEAT],
        "terminal_opponent": rewards[1-SEAT],
        "trace": trace,
    }


def main():
    b = play("baseline", baseline.agent)
    h = play("hold", hold.agent, hold.reset_experiment)
    n = min(len(b["trace"]), len(h["trace"]))
    rows = []
    first_action_diff = None
    for i in range(n):
        br, hr = b["trace"][i], h["trace"][i]
        action_diff = br["action"] != hr["action"]
        if action_diff and first_action_diff is None:
            first_action_diff = i
        rows.append({
            "turn": i,
            "day_baseline": br["day"],
            "day_hold": hr["day"],
            "baseline_money": br["money_before_action"],
            "hold_money": hr["money_before_action"],
            "money_diff": hr["money_before_action"] - br["money_before_action"],
            "baseline_net_delta": br["net_money_delta"],
            "hold_net_delta": hr["net_money_delta"],
            "net_delta_diff": None if br["net_money_delta"] is None or hr["net_money_delta"] is None else hr["net_money_delta"] - br["net_money_delta"],
            "action_diff": action_diff,
            "baseline_action": br["action"] if action_diff else None,
            "hold_action": hr["action"] if action_diff else None,
        })

    start = first_action_diff if first_action_diff is not None else 0
    focused = rows[start:]
    payload = {
        "schema": "kaggriculture.seed4119-money-ledger.v1",
        "seed": SEED,
        "seat": SEAT,
        "observer_note": "net_money_delta is exact change between consecutive observed decision states; it is net movement, not decomposed causal inflow/outflow",
        "first_action_diff_turn": first_action_diff,
        "hold_activation_count": hold.get_hold_count(),
        "baseline_terminal_self": b["terminal_self"],
        "hold_terminal_self": h["terminal_self"],
        "terminal_self_diff": h["terminal_self"] - b["terminal_self"],
        "ledger_from_first_action_diff": focused,
        "full_baseline_trace": b["trace"],
        "full_hold_trace": h["trace"],
    }
    with open("seed4119_money_ledger.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("SEED4119_MONEY_LEDGER " + json.dumps({
        "first_action_diff_turn": first_action_diff,
        "hold_activation_count": hold.get_hold_count(),
        "baseline_terminal_self": b["terminal_self"],
        "hold_terminal_self": h["terminal_self"],
        "terminal_self_diff": payload["terminal_self_diff"],
        "ledger_rows": len(focused),
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
