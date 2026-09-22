#!/usr/bin/env python3
"""Model Candidate Selection Priority Probe v0.

A/B:
- Control: Lens + Candidate Evaluation + Candidate Comparison.
- Treatment: same + model-side selection priority.

The treatment does not add a scalar score, fixed weights, or total ranking.
It only lets the model prioritize a nondominated candidate when the comparison
contains directional dominance, preserving the native candidate order.

The selected candidate is applied on next reentry only if the same candidate is
still present. Application reorders BUY_SEED candidates; it does not delete,
resize, or invent market orders.
"""

import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OPPONENT = base.OPPONENT
OUT = Path(f"model_candidate_selection_priority_v0_{SEED}.json")

def configure(selection=False):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"
    os.environ["OUTER_MEANING_OPTION_PRESERVATION_DAY"] = "14"
    os.environ["ORIGIN_EVALUATION_LENS"] = "1"
    os.environ["ORIGIN_MODEL_CANDIDATE_EVALUATION"] = "1"
    os.environ["ORIGIN_MODEL_CANDIDATE_COMPARISON"] = "1"
    os.environ["ORIGIN_MODEL_CANDIDATE_SELECTION"] = "1" if selection else "0"
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe", {}) or {}).get("body", {}) or {}).get("snapshots", []) or [])

def play(selection=False):
    configure(selection)
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[SEAT] = combat.agent
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    out = []
    for s in snapshots(combat.get_trace()):
        if int(s.get("day", 0) or 0) < 14:
            continue
        internal = dict(s.get("origin_internal", {}) or {})
        integ = dict(s.get("origin_integration_current", {}) or {})
        applied = dict(s.get("applied_origin_integration", {}) or {})
        out.append({
            "turn": s.get("turn"),
            "day": s.get("day"),
            "targets": internal.get("targets"),
            "best_crop": internal.get("best_crop"),
            "native_market": internal.get("market"),
            "final_action": s.get("action"),
            "candidate_comparison": integ.get("candidate_comparison"),
            "candidate_selection": integ.get("candidate_selection"),
            "applied_candidate_selection": applied.get("candidate_selection"),
        })
    return {
        "self": rewards[SEAT],
        "opponent": rewards[1-SEAT],
        "margin": rewards[SEAT] - rewards[1-SEAT],
        "snapshots": out,
    }

def main():
    c = play(False)
    t = play(True)
    by_turn = {x["turn"]: x for x in c["snapshots"]}

    selection_generated = 0
    applied_selection_context = 0
    selection_changed = 0
    target_changed = 0
    action_changed = 0
    examples = []

    for y in t["snapshots"]:
        x = by_turn.get(y["turn"])
        if not x:
            continue
        if y.get("candidate_selection"):
            selection_generated += 1
            if len(examples) < 8:
                examples.append({
                    "turn": y.get("turn"),
                    "day": y.get("day"),
                    "selection": y.get("candidate_selection"),
                    "applied_next_context": bool(y.get("applied_candidate_selection")),
                    "action_changed_vs_control": x.get("final_action") != y.get("final_action"),
                })
        if y.get("applied_candidate_selection"):
            applied_selection_context += 1
        if x.get("candidate_selection") != y.get("candidate_selection"):
            selection_changed += 1
        if x.get("targets") != y.get("targets") or x.get("best_crop") != y.get("best_crop"):
            target_changed += 1
        if x.get("final_action") != y.get("final_action"):
            action_changed += 1

    payload = {
        "schema": "kaggriculture.model-candidate-selection-priority.v0",
        "seed": SEED,
        "seat": SEAT,
        "selection_generated_turns": selection_generated,
        "applied_selection_context_turns": applied_selection_context,
        "candidate_selection_changed_turns": selection_changed,
        "target_changed_turns": target_changed,
        "action_changed_turns": action_changed,
        "terminal_self_diff": t["self"] - c["self"],
        "terminal_margin_diff": t["margin"] - c["margin"],
        "selection_examples": examples,
        "boundary": [
            "Flow-chan still supplies abstraction and evaluation lens only.",
            "Candidate evaluation, comparison, and selection priority are model-side.",
            "No scalar score, fixed weights, total ranking, candidate deletion, quantity rewrite, or new market order is introduced.",
            "Selection is emitted only when pairwise dominance exists.",
            "Application occurs on next reentry only when the selected BUY_SEED candidate is still present.",
            "Battle outcome, not internal reachability alone, determines whether this direction is useful."
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("MODEL_CANDIDATE_SELECTION_PRIORITY_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

if __name__ == "__main__":
    main()
