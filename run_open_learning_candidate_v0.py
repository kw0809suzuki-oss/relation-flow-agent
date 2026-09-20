#!/usr/bin/env python3
"""Verification for Open Learning Candidate v0 using temporal_realization evidence."""

import json
from pathlib import Path

from open_learning_candidate_v0 import build_open_learning_candidate

OUT = Path("open_learning_candidate_v0.json")

EVIDENCE = [
    {
        "stage": "new",
        "case": "seed-6201",
        "observation": "unknown Battle produced a time-to-value realization candidate",
    },
    {
        "stage": "reappeared",
        "case": "seed-6202/6203",
        "observation": "same unresolved end-horizon seed pattern appeared in fresh unknown Battles",
    },
    {
        "stage": "tested",
        "case": "seed-6201",
        "observation": "Day24 WHEAT-seed ablation reduced terminal seed by 6 and increased self money by 60",
    },
    {
        "stage": "replicated",
        "case": "seed-6202",
        "observation": "Day24 WHEAT-seed ablation reduced terminal seed by 2 and increased self money by 20; planted/harvestable unchanged",
    },
    {
        "stage": "replicated",
        "case": "seed-6203",
        "observation": "Day24 WHEAT-seed ablation reduced terminal seed by 3 and increased self money by 30; planted/harvestable unchanged",
    },
]


def main():
    candidate = build_open_learning_candidate("temporal_realization", EVIDENCE)

    checks = {
        "maturity_replicated": candidate["maturity"] == "replicated",
        "adoption_still_proposed": candidate["adoption"] == "proposed",
        "not_formal_taxonomy": candidate["formal_taxonomy_member"] is False,
        "taxonomy_auto_promotion_blocked": candidate["auto_promote_taxonomy"] is False,
        "guide_update_blocked": candidate["auto_update_judgment_guide"] is False,
        "history_retained": len(candidate["evidence_history"]) == 5,
    }

    payload = {
        "candidate": candidate,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("OPEN_LEARNING_CANDIDATE_V0 " + json.dumps({
        "candidate": candidate["candidate"],
        "maturity": candidate["maturity"],
        "adoption": candidate["adoption"],
        "formal_taxonomy_member": candidate["formal_taxonomy_member"],
        "checks": checks,
        "all_checks_pass": payload["all_checks_pass"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
