"""Closed-world X decision layer for Kaggriculture.

X does not try to infer an opponent's hidden reasoning. It stays inside the
observable finite world: self, opponent, market, town and remaining horizon.
Strong Origins remain the baseline. COUNTER is now a component weight rather
than a selectable Origin.
"""

from dataclasses import dataclass
from typing import Dict, Mapping


@dataclass(frozen=True)
class XField:
    day: int
    remaining_days: int
    my_money: float
    opp_money: float
    my_land: int
    opp_land: int
    my_hands: int
    opp_hands: int
    prices: Mapping[str, float]
    my_supply: Mapping[str, int]
    opp_supply: Mapping[str, int]


@dataclass(frozen=True)
class XDecision:
    origin: str
    distortion: float
    confidence: float
    reason: str


JOSEKI = ("BALANCED", "CROP_RUSH", "LIQUID", "ENDGAME")


def _premium(prices: Mapping[str, float], base_prices: Mapping[str, float]) -> float:
    ratios = []
    for item, base in base_prices.items():
        if base > 0:
            ratios.append(float(prices.get(item, base)) / float(base))
    return max(ratios, default=1.0)


def counter_opportunity(field: XField, base_prices: Mapping[str, float]) -> float:
    if field.remaining_days < 11:
        return 0.0
    opp_supply = {crop: max(0, int(field.opp_supply.get(crop, 0))) for crop in base_prices}
    opp_total = sum(opp_supply.values())
    if opp_total <= 0:
        return 0.0
    dominant_crop = max(opp_supply, key=opp_supply.get)
    dominant_share = opp_supply[dominant_crop] / opp_total
    concentration_excess = max(0.0, dominant_share - 0.55)
    if concentration_excess <= 0.0:
        return 0.0

    def price_ratio(crop: str) -> float:
        base = float(base_prices[crop])
        return float(field.prices.get(crop, base)) / base if base > 0 else 1.0

    dominant_ratio = price_ratio(dominant_crop)
    best_alternative_ratio = max((price_ratio(crop) for crop in base_prices if crop != dominant_crop), default=dominant_ratio)
    relative_profit_gap = max(0.0, best_alternative_ratio - dominant_ratio)
    volume_confidence = min(1.0, opp_total / 18.0)
    horizon_factor = min(1.0, max(0, field.remaining_days - 5) / 10.0)
    return concentration_excess * volume_confidence * horizon_factor * (1.0 + 3.0 * relative_profit_gap)


def counter_weight(field: XField, base_prices: Mapping[str, float]) -> float:
    opportunity = counter_opportunity(field, base_prices)
    if opportunity <= 0.16:
        return 0.0
    return min(1.0, (opportunity - 0.16) / 0.40)


def choose_x_origin(field: XField, base_prices: Mapping[str, float]) -> XDecision:
    if field.remaining_days <= 5:
        return XDecision("ENDGAME", 1.0, 1.0, "finite horizon: liquidation boundary")
    money_gap = (field.my_money - field.opp_money) / max(1000.0, field.opp_money)
    premium = _premium(field.prices, base_prices)
    market_distortion = max(0.0, premium - 1.10)
    if field.remaining_days >= 11 and market_distortion >= 0.10:
        return XDecision("CROP_RUSH", market_distortion, min(1.0, 0.50 + market_distortion), "market premium crossed investment threshold")
    if field.day >= 20 and money_gap >= 0.18:
        return XDecision("LIQUID", money_gap, min(1.0, 0.60 + money_gap), "lead crossed capital-preservation threshold")
    return XDecision("BALANCED", 0.0, 0.65, "no Strong-Origin condition cleared threshold")


def counter_crop_weights(field: XField, base_prices: Mapping[str, float], town_demand: Mapping[str, float] | None = None) -> Dict[str, float]:
    town_demand = town_demand or {}
    out: Dict[str, float] = {}
    horizon = max(1, field.remaining_days)
    for crop, base in base_prices.items():
        price_ratio = float(field.prices.get(crop, base)) / float(base)
        demand = max(0.0, float(town_demand.get(crop, 0.0)))
        opp_pressure = max(0, int(field.opp_supply.get(crop, 0)))
        pressure_factor = 1.0 / (1.0 + 0.06 * opp_pressure)
        horizon_factor = min(1.0, horizon / 10.0)
        out[crop] = price_ratio * (1.0 + 0.10 * demand) * pressure_factor * horizon_factor
    return out
