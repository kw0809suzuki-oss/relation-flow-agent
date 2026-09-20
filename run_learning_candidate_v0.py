#!/usr/bin/env python3
"""Smoke verification for Learning Candidate v0 using already-observed failure shapes."""

import json
from pathlib import Path

from learning_candidate_v0 import build_learning_packet

OUT = Path("learning_candidate_v0.json")

CASES = {
    "day16_duplicate": {
        "decision_contract": {
            "judgment": "selected",
            "candidate": "increase work capacity",
        },
        "execution_state": "duplicate",
        "observation_state": "not_observed",
        "outcome_state": "unresolved",
        "expected_observable_change": "independent HIRE difference",
        "actual_observable_change": None,
        "evidence": ["native already emitted HIRE; intervention created no independent action difference"],
        "uncertainty": ["Judgment Claim remains unevaluated"],
    },
    "day24_seed_single_shot": {
        "decision_contract": {
            "judgment": "selected",
            "candidate": "hold all expansion on one Day24 call",
        },
        "execution_state": "executed",
        "observation_state": "observed_diff",
        "outcome_state": "unresolved",
        "expected_observable_change": "remove one expansion purchase",
        "actual_observable_change": "BUY_SEED WHEAT 8 removed",
        "evidence": ["single-shot scope valid", "terminal self and margin unchanged"],
        "uncertainty": ["local action difference did not resolve the higher-level closure claim"],
    },
    "day8_flow_capacity": {
        "decision_contract": {
            "judgment": "selected",
            "candidate": "increase work capacity",
        },
        "execution_state": "executed",
        "observation_state": "observed_diff",
        "outcome_state": "improved",
        "expected_observable_change": "visible backlog improves or grows more slowly",
        "actual_observable_change": "visible backlog delta -3; harvestable delta -5",
        "evidence": ["single-shot scope valid", "self +1488", "margin +3305"],
        "uncertainty": ["hands delta next day was 0", "mechanism is not established"],
    },
}


def main():
    packets = {name: build_learning_packet(record) for name, record in CASES.items()}

    payload = {
        "schema": "kaggriculture.learning-candidate-smoke.v0",
        "cases": packets,
        "boundary_check": {
            "all_status_proposed": all(
                p["learning_candidate"]["status"] == "proposed"
                for p in packets.values()
            ),
            "all_auto_adopt_false": all(
                p["learning_candidate"]["auto_adopt"] is False
                for p in packets.values()
            ),
            "all_guide_update_blocked": all(
                p["learning_candidate"]["judgment_guide_update_allowed"] is False
                for p in packets.values()
            ),
        },
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("LEARNING_CANDIDATE_V0 " + json.dumps({
        "targets": {
            name: packet["learning_candidate"]["update_target_candidates"]
            for name, packet in packets.items()
        },
        "boundary_check": payload["boundary_check"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
