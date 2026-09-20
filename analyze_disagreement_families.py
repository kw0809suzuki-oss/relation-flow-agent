#!/usr/bin/env python3
"""Cluster dual-lens disagreement points into compact candidate families."""

import json
import sys
from collections import defaultdict
from pathlib import Path


AXES = ("money", "capacity", "production")


def mean(values):
    return sum(values) / len(values) if values else None


def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "dual_lens_candidate_observation.json")
    data = json.loads(source.read_text())

    groups = defaultdict(list)
    for p in data.get("candidate_generation_points", []):
        key = f"{p['combat_judgment']}->{p['economic_judgment']}"
        groups[key].append(p)

    families = {}
    for key, points in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        relation_means = {
            axis: mean([
                float(p["state"]["relation_axes"][axis])
                for p in points
                if p["state"].get("relation_axes") and axis in p["state"]["relation_axes"]
            ])
            for axis in AXES
        }
        movement_means = {
            axis: mean([
                float(p["state"]["axis_movements"][axis])
                for p in points
                if p["state"].get("axis_movements") and axis in p["state"]["axis_movements"]
            ])
            for axis in AXES
        }
        reasons = defaultdict(int)
        for p in points:
            reasons[p.get("economic_reason", "unknown")] += 1

        families[key] = {
            "count": len(points),
            "share_of_disagreements": len(points) / max(1, data.get("disagreement_count", 0)),
            "relation_axis_mean": relation_means,
            "movement_axis_mean": movement_means,
            "economic_reason_counts": dict(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
            "representative_points": points[:5],
            "status": "candidate_family",
            "probe_priority": "frequency_only_not_value",
            "promote": False,
        }

    out = {
        "schema": "kaggriculture.dual-lens-disagreement-families.v1",
        "source_schema": data.get("schema"),
        "battle": {"seed": data.get("seed"), "seat": data.get("seat")},
        "family_count": len(families),
        "families": families,
        "boundary": "family_compression_only_no_rule_promotion",
    }

    Path("dual_lens_disagreement_families.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({
        "family_count": len(families),
        "families": {
            k: {
                "count": v["count"],
                "share": v["share_of_disagreements"],
                "relation_axis_mean": v["relation_axis_mean"],
                "movement_axis_mean": v["movement_axis_mean"],
                "economic_reason_counts": v["economic_reason_counts"],
            } for k, v in families.items()
        },
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
