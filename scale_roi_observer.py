from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


KINDS = ("LAND", "HAND", "ANIMAL")


@dataclass(frozen=True)
class ScaleObservation:
    day: int
    money: float
    land: int
    hands: int
    animals: int
    produced_value: float
    collected_value: float


@dataclass(frozen=True)
class UnitReturnEstimate:
    kind: str
    samples: int
    mean_daily_return: float
    median_daily_return: float
    mean_payback_days: Optional[float]


def _delta(a: ScaleObservation, b: ScaleObservation) -> Dict[str, float]:
    return {
        "LAND": float(b.land - a.land),
        "HAND": float(b.hands - a.hands),
        "ANIMAL": float(b.animals - a.animals),
        "collected": float(b.collected_value - a.collected_value),
    }


def one_unit_returns(observations: Iterable[ScaleObservation], kind: str) -> List[float]:
    """Extract empirical next-day collection gain around one-unit expansions.

    This is intentionally conservative and descriptive only:
    - requires exactly +1 unit of the selected kind between consecutive days
    - rejects intervals where another scale kind also changes
    - measures only realized collected-value delta on the following observation

    It does not claim causality; it supplies the external ROI gate with a
    v6-only empirical return estimate.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown kind: {kind}")

    obs = sorted(observations, key=lambda x: x.day)
    returns: List[float] = []
    for prev, cur in zip(obs, obs[1:]):
        d = _delta(prev, cur)
        if d[kind] != 1.0:
            continue
        if any(d[k] != 0.0 for k in KINDS if k != kind):
            continue
        returns.append(max(0.0, d["collected"]))
    return returns


def estimate_unit_return(
    observations: Iterable[ScaleObservation],
    kind: str,
    unit_cost: float,
) -> UnitReturnEstimate:
    values = one_unit_returns(observations, kind)
    if not values:
        return UnitReturnEstimate(kind, 0, 0.0, 0.0, None)

    ordered = sorted(values)
    n = len(ordered)
    if n % 2:
        median = ordered[n // 2]
    else:
        median = (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0
    mean = sum(ordered) / n
    payback = None if mean <= 0 or unit_cost <= 0 else unit_cost / mean
    return UnitReturnEstimate(kind, n, mean, median, payback)


def estimate_all(
    observations: Iterable[ScaleObservation],
    costs: Dict[str, float],
) -> Dict[str, UnitReturnEstimate]:
    obs = list(observations)
    return {kind: estimate_unit_return(obs, kind, float(costs[kind])) for kind in KINDS}
