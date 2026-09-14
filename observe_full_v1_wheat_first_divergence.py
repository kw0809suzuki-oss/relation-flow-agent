#!/usr/bin/env python3
"""Shadow-only observer: find first WHEAT market inventory divergence before turn 120.

Compares baseline vs Full v1 on the five previously worsened seeds.
No policy behavior is changed. Captures the first turn where shared WHEAT market
inventory differs, plus previous/current self and opponent actions and market state.
"""

import copy
import importlib.util
import json
from pathlib import Path

from kaggle_environments import make

import strong_origin_g5_roi as baseline_agent
import full_strong_origin_v1 as candidate_agent

OPPONENT_PATH = "opponents/seyamalam_v21.py"
CASES = ((3514, 0), (3528, 0), (3530, 0), (3554, 0), (3561, 1))
MAX_TURN = 120


def load_opponent():
    spec = importlib.util.spec_from_file_location("seyamalam_v21_wheat_shadow", OPPONENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent


def play(seed, seat, self_module):
    self_module.reset_telemetry()
    opponent_fn = load_opponent()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    self_rows, opp_rows = [], []
    self_turn = 0
    opp_turn = 0

    def snap(obs, action, who, turn):
        m = obs.get("market", {})
        return {
            "turn": turn,
            "day": obs.get("day"),
            "hour": obs.get("hour"),
            "who": who,
            "wheat_inventory": copy.deepcopy(m.get("inventory", {}).get("WHEAT")),
            "wheat_price": copy.deepcopy(m.get("prices", {}).get("WHEAT")),
            "market_inventory": copy.deepcopy(m.get("inventory", {})),
            "market_prices": copy.deepcopy(m.get("prices", {})),
            "action": copy.deepcopy(action),
        }

    def self_wrapped(obs):
        nonlocal self_turn
        action = self_module.agent(obs)
        if self_turn <= MAX_TURN:
            self_rows.append(snap(obs, action, "self", self_turn))
        self_turn += 1
        return action

    def opp_wrapped(obs):
        nonlocal opp_turn
        action = opponent_fn(obs)
        if opp_turn <= MAX_TURN:
            opp_rows.append(snap(obs, action, "opponent", opp_turn))
        opp_turn += 1
        return action

    players = [opp_wrapped, opp_wrapped]
    players[seat] = self_wrapped
    env.run(players)
    return {"self": self_rows, "opponent": opp_rows}


def bt(rows):
    return {x["turn"]: x for x in rows}


def first_divergence(base_rows, cand_rows):
    b, c = bt(base_rows), bt(cand_rows)
    common = sorted(set(b) & set(c))
    for t in common:
        if b[t]["wheat_inventory"] != c[t]["wheat_inventory"]:
            return t
    return None


def context(rows, t):
    m = bt(rows)
    out = {}
    for k in (t - 1, t, t + 1):
        if k in m:
            out[str(k)] = m[k]
    return out


def main():
    cases = []
    for seed, seat in CASES:
        base = play(seed, seat, baseline_agent)
        cand = play(seed, seat, candidate_agent)
        # shared market should be identical from both player observations at a turn;
        # use self trace as the canonical aligned stream, opponent retained for action context.
        t = first_divergence(base["self"], cand["self"])
        row = {
            "seed": seed,
            "seat": seat,
            "first_wheat_inventory_divergence_turn": t,
            "baseline_self_context": context(base["self"], t) if t is not None else None,
            "candidate_self_context": context(cand["self"], t) if t is not None else None,
            "baseline_opponent_context": context(base["opponent"], t) if t is not None else None,
            "candidate_opponent_context": context(cand["opponent"], t) if t is not None else None,
        }
        cases.append(row)

    result = {
        "schema": "kaggriculture.full-v1-wheat-first-divergence.v1",
        "question": "where does shared WHEAT market inventory first diverge between baseline and Full v1 before turn 120?",
        "cases": cases,
        "observer_only": True,
        "agent_mutated": False,
    }
    Path("full_v1_wheat_first_divergence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    compact = []
    for row in cases:
        t = row["first_wheat_inventory_divergence_turn"]
        b = row["baseline_self_context"].get(str(t), {}) if t is not None else {}
        c = row["candidate_self_context"].get(str(t), {}) if t is not None else {}
        compact.append({
            "seed": row["seed"],
            "turn": t,
            "baseline_inv": b.get("wheat_inventory"),
            "candidate_inv": c.get("wheat_inventory"),
            "baseline_price": b.get("wheat_price"),
            "candidate_price": c.get("wheat_price"),
        })
    print("WHEAT_FIRST_DIVERGENCE " + json.dumps(compact, separators=(",", ":")))


if __name__ == "__main__":
    main()
