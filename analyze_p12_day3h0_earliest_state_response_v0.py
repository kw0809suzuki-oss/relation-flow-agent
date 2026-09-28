#!/usr/bin/env python3
"""Aggregate earliest State responses to the Day3 H0 action replacement."""
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path("p12_day3h0_earliest_state_response_v0_result.json")


def terminal_group(effect):
    # This groups only for descriptive follow-up; it never chooses earliest response.
    if effect > 0:
        return "replacement_raises_terminal"
    if effect < 0:
        return "replacement_lowers_terminal"
    return "no_terminal_response"


def main():
    files = sorted(glob.glob(
        "p12-day3h0-earliest-state-response-artifacts/*.json"
    ))
    rows = [json.loads(Path(p).read_text(encoding="utf-8")) for p in files]
    if len(rows) != 20:
        raise SystemExit(f"expected 20 results, got {len(rows)}")

    earliest_counter = Counter()
    path_counter = Counter()
    point_path_counter = Counter()
    cases = []

    for r in rows:
        e = r["scan"]["earliest_difference"]
        if e is None:
            point = None
            paths = []
        else:
            point = f'{e["day"]}:{e["hour"]}'
            paths = [d["path"] for d in e["differences"]]
            earliest_counter[point] += 1
            path_counter.update(paths)
            for p in paths:
                point_path_counter[(point, p)] += 1

        cases.append({
            "seed": r["seed"],
            "seat": r["seat"],
            "replacement_terminal_effect": r["terminal"]["replacement_effect"],
            "terminal_effect_group": terminal_group(r["terminal"]["replacement_effect"]),
            "earliest_point": point,
            "earliest_difference_count": 0 if e is None else e["difference_count"],
            "earliest_paths": paths,
            "earliest_differences": [] if e is None else e["differences"],
            "first_full_state_reconvergence_after_difference":
                r["scan"]["first_full_state_reconvergence_after_difference"],
            "changed_observation_point_count":
                r["scan"]["changed_observation_point_count"],
        })

    ordered_points = sorted(
        earliest_counter.items(),
        key=lambda kv: tuple(map(int, kv[0].split(":")))
    )

    first_global_point = ordered_points[0][0] if ordered_points else None
    cases_at_first_global = [
        c for c in cases if c["earliest_point"] == first_global_point
    ]

    paths_at_first_global = Counter()
    for c in cases_at_first_global:
        paths_at_first_global.update(c["earliest_paths"])

    payload = {
        "schema": "kaggriculture.p12-day3h0-earliest-state-response.aggregate.v0",
        "case_count": len(cases),
        "action_changed_count": sum(
            1 for r in rows if r["replacement"]["action_changed"]
        ),
        "terminal_response_count": sum(
            1 for r in rows if r["terminal"]["replacement_effect"] != 0
        ),
        "earliest_point_distribution": dict(ordered_points),
        "first_global_response_point": first_global_point,
        "cases_at_first_global_response_point": len(cases_at_first_global),
        "paths_at_first_global_response_point": dict(
            paths_at_first_global.most_common()
        ),
        "most_common_earliest_paths_all_cases": dict(path_counter.most_common()),
        "cases": cases,
        "boundary": [
            "Earliest response is computed independently inside each same-seed normal-vs-replaced pair.",
            "Terminal effect grouping is descriptive only and does not select the earliest field.",
            "A frequent earliest field is intervention-sensitive, not automatically a sufficient mechanism.",
            "If earliest paths differ by case, do not collapse them into one causal story without a new discriminating probe.",
        ],
    }

    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("P12_DAY3H0_EARLIEST_STATE_RESPONSE_RESULT " + json.dumps({
        "case_count": payload["case_count"],
        "action_changed_count": payload["action_changed_count"],
        "terminal_response_count": payload["terminal_response_count"],
        "earliest_point_distribution": payload["earliest_point_distribution"],
        "first_global_response_point": payload["first_global_response_point"],
        "paths_at_first_global_response_point":
            payload["paths_at_first_global_response_point"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
