"""Scale Chassis v1 experiment entrypoint.

Observer-coordinate experiment:
1. load/produce v6 baseline observations,
2. estimate one-unit realized return for LAND / HAND / ANIMAL,
3. construct minimal ROI candidates,
4. allow at most one expansion admission,
5. compare paired terminal results.

The environment adapter is intentionally isolated in `load_v6_observations` and
`run_paired_trial` so v6 policy can remain unchanged.
"""

from dataclasses import asdict
import json
from pathlib import Path
from typing import Dict, Iterable, List

from scale_chassis import ScaleCandidate, passes_roi_gate
from scale_roi_observer import KINDS, ScaleObservation, estimate_all


DEFAULT_COSTS = {
    "LAND": 0.0,
    "HAND": 0.0,
    "ANIMAL": 0.0,
}


def load_v6_observations(path: str) -> List[ScaleObservation]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ScaleObservation(**row) for row in raw]


def build_candidates(
    observations: Iterable[ScaleObservation],
    costs: Dict[str, float],
    remaining_days: int,
    current_cash: float,
    minimum_runway: float,
):
    estimates = estimate_all(observations, costs)
    candidates = {}
    for kind in KINDS:
        est = estimates[kind]
        cost = float(costs[kind])
        candidate = ScaleCandidate(
            kind=kind,
            cost=cost,
            expected_daily_return=est.mean_daily_return,
            remaining_days=remaining_days,
            cash_after_purchase=current_cash - cost,
            minimum_runway=minimum_runway,
        )
        candidates[kind] = {
            "estimate": asdict(est),
            "candidate": asdict(candidate),
            "pass": passes_roi_gate(candidate),
        }
    return candidates


def choose_one(candidates):
    passing = []
    for kind, row in candidates.items():
        if not row["pass"]:
            continue
        c = row["candidate"]
        passing.append((float(c["roi"] if "roi" in c else 0.0), kind))

    # dataclass serialization does not include properties; use empirical
    # recovery/cost ratio directly and choose only one candidate.
    ranked = []
    for kind, row in candidates.items():
        if not row["pass"]:
            continue
        c = row["candidate"]
        cost = float(c["cost"])
        recovery = max(0, int(c["remaining_days"])) * max(0.0, float(c["expected_daily_return"]))
        roi = recovery / cost if cost > 0 else 0.0
        ranked.append((roi, kind))
    return max(ranked)[1] if ranked else None


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("observations", help="JSON list of v6 daily ScaleObservation rows")
    parser.add_argument("--land-cost", type=float, required=True)
    parser.add_argument("--hand-cost", type=float, required=True)
    parser.add_argument("--animal-cost", type=float, required=True)
    parser.add_argument("--remaining-days", type=int, required=True)
    parser.add_argument("--cash", type=float, required=True)
    parser.add_argument("--runway", type=float, required=True)
    args = parser.parse_args()

    costs = {
        "LAND": args.land_cost,
        "HAND": args.hand_cost,
        "ANIMAL": args.animal_cost,
    }
    observations = load_v6_observations(args.observations)
    candidates = build_candidates(observations, costs, args.remaining_days, args.cash, args.runway)
    selected = choose_one(candidates)
    print(json.dumps({"candidates": candidates, "selected_one_step": selected}, indent=2))


if __name__ == "__main__":
    main()
