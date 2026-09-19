#!/usr/bin/env python3
"""Option Reachability Observer v0 — outside-view sidecar.

Question:
After a comparable SEED/COW decision, what immediate market transformations
remain externally reachable from the next observed game state, and which
market transformation is realized next?

No intervention. No internal candidate/gate inspection.
"""

import json
import os
import statistics
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import g17_agent as combat

OPPONENT = base.OPPONENT
OPPONENT_LABEL = "Seyamalam v21"
CASES = [(5101 + i, i % 2) for i in range(10)]
OUTPUT = Path("option_reachability_observer_fresh10_v0.json")

SEED_COST = 10.0
COW_COST = 400.0
LAND_PRICES = {1: 1000.0, 2: 2000.0, 3: 4000.0}


def configure_current():
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
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def total_private(obs, item):
    private = obs.get("private", {})
    shed = private.get("shed", {}) or {}
    inventories = private.get("inventories", []) or []
    return float(shed.get(item, 0) or 0) + sum(float((inv or {}).get(item, 0) or 0) for inv in inventories)


def reachable_market_transforms(obs):
    me = obs["farms"][obs["player"]]
    money = float(me.get("money", 0) or 0)
    land_count = max(1, len(me.get("unlocked_quadrants", [])))
    out = set()

    if money >= SEED_COST:
        out.add("BUY_SEED")
    if money >= COW_COST:
        out.add("BUY_COW")

    next_land = LAND_PRICES.get(land_count)
    if next_land is not None and money >= next_land:
        out.add("BUY_LAND")

    saleable = sum(total_private(obs, item) for item in ("WHEAT", "MILK", "WOOL", "EGG", "FERTILIZER"))
    if saleable > 0:
        out.add("SELL")

    return out


def classify_market_transform(action):
    market = (action or {}).get("market", []) or []
    kinds = []
    for order in market:
        if not order:
            continue
        op = order[0]
        if op == "BUY_SEED":
            kinds.append("BUY_SEED")
        elif op == "BUY_ANIMAL" and len(order) > 1 and order[1] == "COW":
            kinds.append("BUY_COW")
        elif op == "BUY_LAND":
            kinds.append("BUY_LAND")
        elif op == "SELL":
            kinds.append("SELL")
        elif op == "HIRE":
            kinds.append("HIRE")
        elif op.startswith("BUY_"):
            kinds.append(op)
    # keep only one class when unambiguous; mixed bundles are a separate observation
    uniq = sorted(set(kinds))
    if len(uniq) == 1:
        return uniq[0]
    if len(uniq) > 1:
        return "MIXED:" + "+".join(uniq)
    return None


def comparable_actual(action):
    t = classify_market_transform(action)
    return t if t in ("BUY_SEED", "BUY_COW") else None


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1-seat])
    margin = own - opp
    return {
        "terminal_self": own,
        "terminal_opponent": opp,
        "margin": margin,
        "win_loss": "win" if margin > 0 else "loss" if margin < 0 else "draw",
    }


def play(seed, seat, battle_id):
    configure_current()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    rows = []
    pending = []
    turn = 0

    def observed(obs):
        nonlocal turn
        current_reachable = reachable_market_transforms(obs)

        # The current observation is the first post-action state for all pending
        # decisions from the immediately previous turn.
        for row in pending:
            if row.get("reachable_after") is None:
                after = set(current_reachable)
                before = set(row["reachable_before"])
                row["reachable_after"] = sorted(after)
                row["opened"] = sorted(after - before)
                row["closed"] = sorted(before - after)
                row["preserved"] = sorted(before & after)
                row["option_count_delta"] = len(after) - len(before)
        pending.clear()

        action = combat.agent(obs)
        market_transform = classify_market_transform(action)

        # Fill the next realized market transformation for earlier comparable rows.
        if market_transform is not None:
            for row in rows:
                if row["next_realized_market_transform"] is None and row["turn"] < turn:
                    row["next_realized_market_transform"] = market_transform
                    row["turns_to_next_realized"] = turn - row["turn"]

        actual = comparable_actual(action)
        if actual is not None:
            row = {
                "battle_id": battle_id,
                "decision_id": f"{battle_id}-D{turn:03d}",
                "turn": turn,
                "day": int(obs.get("day", 0)),
                "actual_action": actual,
                "reachable_before": sorted(current_reachable),
                "reachable_after": None,
                "opened": None,
                "closed": None,
                "preserved": None,
                "option_count_delta": None,
                "next_realized_market_transform": None,
                "turns_to_next_realized": None,
            }
            rows.append(row)
            pending.append(row)

        turn += 1
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)

    terminal = score([state.reward for state in env.state], seat)

    valid = [r for r in rows if r["reachable_after"] is not None]
    connected = [
        r for r in valid
        if r["next_realized_market_transform"] is not None
        and r["next_realized_market_transform"] in set(r["reachable_after"])
    ]
    closed_any = [r for r in valid if r["closed"]]
    opened_any = [r for r in valid if r["opened"]]

    return {
        "battle_id": battle_id,
        "seed": seed,
        "seat": seat,
        "opponent": OPPONENT_LABEL,
        **terminal,
        "comparable_decisions": len(valid),
        "connected_to_next_realized": len(connected),
        "connection_rate": len(connected) / len(valid) if valid else None,
        "opened_any_count": len(opened_any),
        "closed_any_count": len(closed_any),
        "mean_option_count_delta": (
            sum(r["option_count_delta"] for r in valid) / len(valid)
            if valid else None
        ),
        "decisions": rows,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }


def mean_or_none(values):
    xs = [v for v in values if v is not None]
    return sum(xs) / len(xs) if xs else None


def main():
    battles = [
        play(seed, seat, f"B{i+1:02d}")
        for i, (seed, seat) in enumerate(CASES)
    ]

    ordered = sorted(battles, key=lambda x: x["terminal_self"])
    low, high = ordered[:5], ordered[5:]

    summary = {
        "battle_count": len(battles),
        "mean_terminal_self": mean_or_none([b["terminal_self"] for b in battles]),
        "mean_connection_rate": mean_or_none([b["connection_rate"] for b in battles]),
        "high_terminal_half_connection_rate": mean_or_none([b["connection_rate"] for b in high]),
        "low_terminal_half_connection_rate": mean_or_none([b["connection_rate"] for b in low]),
        "high_terminal_half_option_delta": mean_or_none([b["mean_option_count_delta"] for b in high]),
        "low_terminal_half_option_delta": mean_or_none([b["mean_option_count_delta"] for b in low]),
        "total_comparable_decisions": sum(b["comparable_decisions"] for b in battles),
        "total_opened_any": sum(b["opened_any_count"] for b in battles),
        "total_closed_any": sum(b["closed_any_count"] for b in battles),
        "boundary": "Reachable means only immediate external market-transform availability from game state; more options is not assumed better.",
    }

    payload = {
        "schema": "kaggriculture.option-reachability-observer.v0",
        "combat_model_frozen": True,
        "intervention": "none",
        "comparable_decisions": ["BUY_SEED", "BUY_COW"],
        "reachable_transform_scope": ["BUY_SEED", "BUY_COW", "BUY_LAND", "SELL"],
        "question": "Do stronger battles preserve connection from a value-changing action to the next realized market transformation?",
        "battles": battles,
        "summary": summary,
    }

    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    compact = [{
        "battle_id": b["battle_id"],
        "seed": b["seed"],
        "seat": b["seat"],
        "terminal_self": b["terminal_self"],
        "margin": b["margin"],
        "comparable_decisions": b["comparable_decisions"],
        "connection_rate": b["connection_rate"],
        "opened_any_count": b["opened_any_count"],
        "closed_any_count": b["closed_any_count"],
        "mean_option_count_delta": b["mean_option_count_delta"],
    } for b in battles]

    print("OPTION_REACHABILITY_BATTLES " + json.dumps(compact, separators=(",", ":")))
    print("OPTION_REACHABILITY_SUMMARY " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
