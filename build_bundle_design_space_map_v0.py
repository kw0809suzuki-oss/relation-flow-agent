#!/usr/bin/env python3
"""Build an external Battle design-space evidence map from existing runs only.

No new battles. No policy adoption.
The goal is to place already-observed evidence on four external axes:
Expansion / Closure / Timing / Option.
"""

import json
from pathlib import Path

OUT_JSON = Path("bundle_design_space_map_v0.json")
OUT_MD = Path("BUNDLE_DESIGN_SPACE_MAP_V0.md")

evidence = [
    {
        "id": "E0",
        "axis": ["baseline"],
        "source": "G17 Economic Observer fresh10 v0",
        "run_id": 35437378831,
        "kind": "observation",
        "fact": {
            "battle_count": 10,
            "mean_terminal_self": 24861.8,
            "wins": 0,
            "losses": 10,
            "mean_alignment_rate": 0.47584044997053987,
            "high_terminal_half_alignment": 0.40645130258033485,
            "low_terminal_half_alignment": 0.5452295973607449,
        },
        "bounded_read": "Isolated SEED/COW economic alignment did not positively separate terminal performance in this fresh10.",
    },
    {
        "id": "E1",
        "axis": ["option"],
        "source": "Option Reachability Observer fresh10 v0",
        "run_id": 35439434015,
        "kind": "observation",
        "fact": {
            "battle_count": 10,
            "mean_terminal_self": 24861.8,
            "mean_connection_rate": 0.733838383838384,
            "high_terminal_half_connection_rate": 0.7087878787878787,
            "low_terminal_half_connection_rate": 0.758888888888889,
            "total_comparable_decisions": 87,
            "total_opened_any": 0,
            "total_closed_any": 13,
        },
        "bounded_read": "Immediate external option continuity, as measured here, did not positively separate high-terminal battles.",
    },
    {
        "id": "E2",
        "axis": ["expansion"],
        "source": "LAND First Purchase Suppress v0",
        "run_id": 35428886457,
        "kind": "intervention",
        "fact": {
            "known13": {"activated": 13, "improved": 6, "worsened": 7, "mean_self_diff": -5201.23},
            "fresh10": {"activated": 10, "improved": 5, "worsened": 5, "mean_self_diff": 2082.8},
        },
        "bounded_read": "LAND is terminal-relevant, but suppression direction is unstable. Expansion capacity matters, but no monotone good/bad direction is established.",
    },
    {
        "id": "E3",
        "axis": ["timing", "expansion"],
        "source": "LAND Direction Prestate v0",
        "run_id": 35429792465,
        "kind": "observation",
        "fact": {
            "fresh10": {"improved": 5, "worsened": 5},
            "day_pattern": "improved all Day5; worsened Day5x3 + Day8x2",
            "separator": "no clean robust prestate separator",
        },
        "bounded_read": "Coarse purchase timing/prestate did not cleanly explain LAND direction.",
    },
    {
        "id": "E4",
        "axis": ["expansion"],
        "source": "WHEAT3 suppression",
        "run_id": 35413687627,
        "kind": "intervention",
        "fact": {
            "known13_activation": 6,
            "fresh30_activation": 4,
            "terminal_equal_cases": 43,
            "land_timing_changed": 0,
        },
        "bounded_read": "A local isolated seed purchase difference can be causally real yet terminal-neutral.",
    },
]

axes = {
    "Expansion": {
        "status": "PARTIALLY COVERED",
        "evidence_ids": ["E2", "E3", "E4"],
        "what_is_known": "Capacity/investment choices can reach terminal, but direction is unstable; isolated purchase suppression can also be terminal-neutral.",
        "missing": "A coarse external rule for when continued expansion should stop.",
    },
    "Closure": {
        "status": "OPEN",
        "evidence_ids": [],
        "what_is_known": "Terminal money is the objective, but existing listed interventions do not directly test liquidation/closure timing as a policy direction.",
        "missing": "Direct Battle evidence for earlier/later conversion of productive/inventory value into terminal cash.",
    },
    "Timing": {
        "status": "PARTIALLY COVERED",
        "evidence_ids": ["E3"],
        "what_is_known": "Simple LAND prestate/day timing does not cleanly separate direction.",
        "missing": "A broader remaining-time-aware switch test spanning multiple action types.",
    },
    "Option": {
        "status": "PARTIALLY COVERED",
        "evidence_ids": ["E0", "E1"],
        "what_is_known": "Neither isolated ROI alignment nor immediate next-option connection positively separated high terminal in fresh10.",
        "missing": "Longer-horizon transformation preservation, if worth testing, must be tested without turning reachability into a new internal theory.",
    },
}

variants = [
    {
        "model": "M0 Current",
        "axis": "baseline",
        "need_new_battle": True,
        "reason": "Control condition for any new bundle.",
    },
    {
        "model": "M1 Expansion-heavy",
        "axis": "Expansion",
        "need_new_battle": False,
        "reason": "Existing LAND/COW/WHEAT evidence already shows expansion-side effects are terminal-relevant but direction-unstable; defer until paired with a switch/closure contrast.",
    },
    {
        "model": "M2 Early Closure",
        "axis": "Closure",
        "need_new_battle": True,
        "reason": "Direct evidence gap.",
    },
    {
        "model": "M3 Late Closure",
        "axis": "Closure+Timing",
        "need_new_battle": True,
        "reason": "Needed as contrast against Early Closure.",
    },
    {
        "model": "M4 Time-weighted",
        "axis": "Timing",
        "need_new_battle": True,
        "reason": "Current evidence only covers narrow LAND timing; remaining-time weighting is still open.",
    },
    {
        "model": "M5 Option-preserving",
        "axis": "Option",
        "need_new_battle": False,
        "reason": "Immediate option-preservation proxy did not separate terminal; do not expand this direction yet.",
    },
    {
        "model": "M6 Recovery-first",
        "axis": "Closure+Timing",
        "need_new_battle": True,
        "reason": "Directly tests terminal recoverability without requiring detailed ROI ranking.",
    },
    {
        "model": "M7 Switch",
        "axis": "Expansion+Closure+Timing",
        "need_new_battle": True,
        "reason": "Tests the central time-direction hypothesis with one explicit switch rather than many local rules.",
    },
]

payload = {
    "schema": "kaggriculture.bundle-design-space-map.v0",
    "principle": "Reuse existing Battle evidence first; generate new battles only for uncovered external directions.",
    "hypothesis_boundary": [
        "Expansion is not assumed good.",
        "Closure is not assumed good.",
        "More options are not assumed good.",
        "A switch is not assumed to exist at a universal day.",
        "Only Battle may promote a variant."
    ],
    "evidence": evidence,
    "axes": axes,
    "variant_plan": variants,
    "next_bundle": {
        "models": ["M0 Current", "M2 Early Closure", "M3 Late Closure", "M4 Time-weighted", "M6 Recovery-first", "M7 Switch"],
        "first_stage": "6 models × same fresh5 = 30 Battles",
        "why_not_8": "M1 Expansion-heavy and M5 Option-preserving already have enough nearby evidence to avoid spending first-stage battles there.",
        "readout": ["terminal_self", "win_loss", "margin", "terminal_unrecovered_value", "expansion_to_closure_switch_position"],
        "no_internal_trace": True,
    }
}

OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Bundle Design Space Map v0",
    "",
    "> Existing evidence first. New Battle only where the external design space is still open.",
    "",
    "## Axis map",
    "",
    "| Axis | Status | Existing read | Missing |",
    "|---|---|---|---|",
]
for name, x in axes.items():
    lines.append(f"| {name} | {x['status']} | {x['what_is_known']} | {x['missing']} |")

lines += ["", "## Variant decision", "", "| Model | Axis | New Battle? | Reason |", "|---|---|---:|---|"]
for v in variants:
    lines.append(f"| {v['model']} | {v['axis']} | {'YES' if v['need_new_battle'] else 'NO'} | {v['reason']} |")

lines += [
    "",
    "## First bundle",
    "",
    "**M0 / M2 / M3 / M4 / M6 / M7 × same fresh5 = 30 Battles**",
    "",
    "M1 Expansion-heavy and M5 Option-preserving are held out in the first bundle because existing Battle evidence already covers nearby directions enough to avoid spending runs there.",
    "",
    "This map does not adopt a policy. It only selects where new Battle evidence is worth buying.",
]
OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("BUNDLE_DESIGN_SPACE_MAP " + json.dumps(payload["next_bundle"], ensure_ascii=False, separators=(",", ":")))
