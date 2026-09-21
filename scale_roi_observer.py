from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


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


@dataclass(frozen=True)
class LandRecoveryWindow:
    expansion_day: int
    window_days: int
    start_land: int
    end_land: int
    collected_gain: float
    money_gain: float
    daily_collected_gain: float


def _delta(a: ScaleObservation, b: ScaleObservation) -> Dict[str, float]:
    return {
        "LAND": float(b.land - a.land),
        "HAND": float(b.hands - a.hands),
        "ANIMAL": float(b.animals - a.animals),
        "collected": float(b.collected_value - a.collected_value),
    }


def one_unit_returns(observations: Iterable[ScaleObservation], kind: str) -> List[float]:
    """Legacy one-step descriptive return extractor.

    Retained for compatibility, but Scale Chassis v1 does not use this for LAND
    admission because a next-observation return is too short to represent land
    entering production and collection flow.
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


def land_recovery_windows(
    observations: Iterable[ScaleObservation],
    window_days: int = 5,
) -> List[LandRecoveryWindow]:
    """Measure realized post-expansion recovery over a short multi-day window.

    This is descriptive only. It asks what value actually flowed after a +1 LAND
    transition and does not attribute all subsequent gain causally to that land.

    Rules:
    - identify exactly +1 LAND between consecutive daily observations;
    - require LAND to remain at least at the expanded level through the window;
    - measure realized collected-value and money change from the expansion state
      to the last observation within `window_days`;
    - do not require HAND/ANIMAL stability, because those are operating state and
      are not being estimated in this pass.
    """
    if window_days <= 0:
        raise ValueError("window_days must be positive")

    obs = sorted(observations, key=lambda x: x.day)
    windows: List[LandRecoveryWindow] = []
    for index in range(1, len(obs)):
        prev = obs[index - 1]
        cur = obs[index]
        if cur.land - prev.land != 1:
            continue

        target_day = cur.day + window_days
        tail = [row for row in obs[index:] if row.day <= target_day]
        if len(tail) < 2:
            continue
        if any(row.land < cur.land for row in tail):
            continue

        end = tail[-1]
        elapsed = max(1, end.day - cur.day)
        collected_gain = max(0.0, float(end.collected_value - cur.collected_value))
        money_gain = float(end.money - cur.money)
        windows.append(
            LandRecoveryWindow(
                expansion_day=cur.day,
                window_days=elapsed,
                start_land=cur.land,
                end_land=end.land,
                collected_gain=collected_gain,
                money_gain=money_gain,
                daily_collected_gain=collected_gain / elapsed,
            )
        )
    return windows


def estimate_land_window_return(
    observations: Iterable[ScaleObservation],
    unit_cost: float,
    window_days: int = 5,
) -> UnitReturnEstimate:
    windows = land_recovery_windows(observations, window_days=window_days)
    values = [row.daily_collected_gain for row in windows]
    if not values:
        return UnitReturnEstimate("LAND", 0, 0.0, 0.0, None)

    ordered = sorted(values)
    n = len(ordered)
    if n % 2:
        median = ordered[n // 2]
    else:
        median = (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0
    mean = sum(ordered) / n
    payback = None if mean <= 0 or unit_cost <= 0 else unit_cost / mean
    return UnitReturnEstimate("LAND", n, mean, median, payback)


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
    return {
        "LAND": estimate_land_window_return(obs, float(costs["LAND"]), window_days=5),
        "HAND": UnitReturnEstimate("HAND", 0, 0.0, 0.0, None),
        "ANIMAL": UnitReturnEstimate("ANIMAL", 0, 0.0, 0.0, None),
    }
