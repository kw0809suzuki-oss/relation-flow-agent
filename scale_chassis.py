from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ScaleCandidate:
    kind: str
    cost: float
    expected_daily_return: float
    remaining_days: int
    cash_after_purchase: float
    minimum_runway: float

    @property
    def expected_recovery(self) -> float:
        return max(0, self.remaining_days) * max(0.0, self.expected_daily_return)

    @property
    def roi(self) -> float:
        if self.cost <= 0:
            return 0.0
        return self.expected_recovery / self.cost

    @property
    def payback_days(self) -> Optional[float]:
        if self.expected_daily_return <= 0:
            return None
        return self.cost / self.expected_daily_return


def passes_roi_gate(candidate: ScaleCandidate) -> bool:
    """Minimal external Scale Chassis gate.

    This does not predict an optimal farm size. It only asks whether one
    additional unit is recoverable before terminal without violating cash
    runway.
    """
    if candidate.cost <= 0 or candidate.remaining_days <= 0:
        return False
    if candidate.cash_after_purchase < candidate.minimum_runway:
        return False
    if candidate.expected_daily_return <= 0:
        return False

    payback = candidate.payback_days
    if payback is None or payback > candidate.remaining_days:
        return False

    return candidate.expected_recovery >= candidate.cost
