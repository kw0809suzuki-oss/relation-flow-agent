#!/usr/bin/env python3
"""Turn-level money transition observer around the Day9 -> Day10 boundary.

Observer only. Preserves pre-action state, chosen market action, and next observed
money so AI Desk can compare the arrows rather than compressed daily states.
"""
import json
from pathlib import Path

from kaggle_environments import make
import export_scale_baseline_v1 as base

TARGET_SEEDS = {3206, 3222, 3240, 3251, 3202, 3227, 3246, 3231}


def main():
    rows = []
    for seed, seat in [(s, seat) for s, seat in base.DEFAULT_CASES if s in TARGET_SEEDS]:
        base._configure_baseline()
        env = make("kaggriculture", configuration={"seed": seed}, debug=False)
        pending = None
        case_rows = []

        def observed(obs):
            nonlocal pending
            player = int(obs.get("player", seat))
            farm = (obs.get("farms", []) or [])[player]
            now = {
                "seed": seed,
                "seat": seat,
                "day": int(obs.get("day", 0)),
                "hour": int(obs.get("hour", 0)),
                "money": float(farm.get("money", 0) or 0),
            }
            if pending is not None:
                pending["next_day"] = now["day"]
                pending["next_hour"] = now["hour"]
                pending["money_next"] = now["money"]
                pending["money_delta"] = now["money"] - pending["money_before"]
                case_rows.append(pending)
                pending = None

            action = base.v6.agent(obs)
            if now["day"] in (9, 10):
                pending = {
                    **now,
                    "money_before": now["money"],
                    "market_action": action.get("market", []) if isinstance(action, dict) else [],
                    "farmer_action": action.get("farmer") if isinstance(action, dict) else None,
                    "hands_actions": action.get("hands", []) if isinstance(action, dict) else [],
                }
            return action

        players = [base.OPPONENT, base.OPPONENT]
        players[seat] = observed
        env.run(players)
        rows.extend(case_rows)

    payload = {
        "coordinate": "AI Desk -> Day9/10 turn-level money arrows",
        "policy_mutated": False,
        "purpose": "locate which observed Action -> next State transitions generate the Day9-to-Day10 money divergence without daily compression",
        "boundary": "money_delta is observational across one environment step; it is not by itself causal attribution to a listed action because opponent/town/environment processing also occurs in the step",
        "rows": rows,
    }
    Path("money_transition_v1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("MONEY_TRANSITION_V1 rows=" + str(len(rows)))


if __name__ == "__main__":
    main()
