#!/usr/bin/env python3
"""Find the first Fresh20 Delta Trace Split after the shared Day3 H1 response."""
import json
from collections import Counter, defaultdict
from pathlib import Path

ART_DIR = Path("p12-day3h0-delta-trace-split-artifacts")
OUT = Path("p12_day3h0_delta_trace_split_v0_result.json")


def parse_key(k):
    d, h = k.split(":")
    return (int(d), int(h))


def terminal_sign(x):
    return "POSITIVE" if x > 0 else "NEGATIVE" if x < 0 else "ZERO"


def canonical_signature(sig):
    return json.dumps(sig, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def changed_paths_between(signatures):
    paths = sorted(set().union(*(set(s) for s in signatures)))
    out = {}
    for p in paths:
        values = []
        for s in signatures:
            values.append(s.get(p, "__ZERO_OR_ABSENT__"))
        keys = [json.dumps(v, ensure_ascii=False, sort_keys=True) for v in values]
        if len(set(keys)) > 1:
            out[p] = values
    return out


def main():
    files = sorted(ART_DIR.glob("p12_day3h0_delta_trace_split_v0_*_seat*.json"))
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    if len(rows) != 20:
        raise SystemExit(f"expected 20 case artifacts, got {len(rows)}")

    points = sorted(
        set.intersection(*(set(r["trace"]) for r in rows)),
        key=parse_key,
    )
    if "3:1" not in points:
        raise SystemExit("expected shared Day3 Hour1 observation")

    per_point = []
    first_split = None

    for k in points:
        signatures = [r["trace"][k] for r in rows]
        keys = [canonical_signature(s) for s in signatures]
        unique_keys = list(dict.fromkeys(keys))
        groups = []
        for skey in unique_keys:
            idxs = [i for i, x in enumerate(keys) if x == skey]
            members = []
            signs = Counter()
            for i in idxs:
                r = rows[i]
                effect = r["terminal"]["replacement_effect"]
                sign = terminal_sign(effect)
                signs[sign] += 1
                members.append({
                    "seed": r["seed"],
                    "seat": r["seat"],
                    "terminal_effect": effect,
                    "terminal_sign": sign,
                })
            groups.append({
                "signature": json.loads(skey),
                "case_count": len(idxs),
                "terminal_sign_counts": dict(signs),
                "members": members,
            })

        varying_paths = changed_paths_between(signatures)
        rec = {
            "point": k,
            "signature_count": len(unique_keys),
            "varying_path_count": len(varying_paths),
        }
        per_point.append(rec)

        if k != "3:1" and len(unique_keys) > 1 and first_split is None:
            sign_pure = all(
                sum(1 for n in g["terminal_sign_counts"].values() if n > 0) <= 1
                for g in groups
            )
            all_signs = set()
            for g in groups:
                all_signs.update(
                    sign for sign, n in g["terminal_sign_counts"].items() if n > 0
                )
            clean_separator = sign_pure and len(all_signs) > 1

            # Compact path-wise values by case for only the paths that split.
            path_cases = {}
            for p in varying_paths:
                vals = []
                for r, sig in zip(rows, signatures):
                    vals.append({
                        "seed": r["seed"],
                        "seat": r["seat"],
                        "delta": sig.get(p, 0),
                        "terminal_effect": r["terminal"]["replacement_effect"],
                        "terminal_sign": terminal_sign(r["terminal"]["replacement_effect"]),
                    })
                path_cases[p] = vals

            path_sets = [set(s) for s in signatures]
            structural_split = len({tuple(sorted(x)) for x in path_sets}) > 1

            first_split = {
                "point": k,
                "signature_count": len(unique_keys),
                "case_groups": groups,
                "varying_paths": sorted(varying_paths),
                "varying_path_cases": path_cases,
                "structural_path_set_split": structural_split,
                "terminal_sign_clean_separator": clean_separator,
                "boundary": [
                    "This is the first timestamp where Fresh20 canonical normal-vs-replaced delta signatures are not all identical.",
                    "Split location is selected before terminal sign is inspected.",
                    "terminal_sign_clean_separator only tests whether signature groups at this timestamp are sign-pure; it does not prove causality.",
                ],
            }

    day3h1_keys = {
        canonical_signature(r["trace"]["3:1"])
        for r in rows
    }

    payload = {
        "schema": "kaggriculture.p12-day3h0-delta-trace-split.aggregate.v0",
        "case_count": len(rows),
        "action_changed_count": sum(r["replacement"]["action_changed"] for r in rows),
        "terminal_sign_counts": dict(Counter(
            terminal_sign(r["terminal"]["replacement_effect"]) for r in rows
        )),
        "common_observation_point_count": len(points),
        "day3h1_signature_count": len(day3h1_keys),
        "day3h1_shared_signature": (
            json.loads(next(iter(day3h1_keys))) if len(day3h1_keys) == 1 else None
        ),
        "first_delta_trace_split": first_split,
        "per_point_summary": per_point,
        "boundary": [
            "Delta Trace Split means the first cross-case loss of a shared intervention-delta signature.",
            "It is distinct from within-case temporal re-divergence after full State reconvergence.",
            "Split does not imply terminal separator.",
            "Absolute State differences across seeds are excluded by comparing only canonical normal-vs-replaced deltas.",
            "Seat-dependent farm paths are canonicalized to self/opponent before comparison.",
        ],
    }

    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    fs = first_split
    print("P12_DAY3H0_DELTA_TRACE_SPLIT_RESULT " + json.dumps({
        "case_count": payload["case_count"],
        "day3h1_signature_count": payload["day3h1_signature_count"],
        "first_split_point": None if fs is None else fs["point"],
        "signature_count": None if fs is None else fs["signature_count"],
        "varying_paths": [] if fs is None else fs["varying_paths"],
        "terminal_sign_clean_separator":
            None if fs is None else fs["terminal_sign_clean_separator"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
