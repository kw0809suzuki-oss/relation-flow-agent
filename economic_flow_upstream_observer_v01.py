"""Economic Flow Upstream Observer v0.1.

Observer-only extension focused on the pre-cash-separator window.
Adds raw state and cumulative action-flow counters.
No unified score and no action/strategy instruction.
"""

from economic_flow_observer_v0 import EconomicFlowObserver


MARKET_KEYS = (
    "BUY_ANIMAL_COW",
    "BUY_PRODUCT_COW",
    "BUY_SEED_WHEAT",
    "BUY_PRODUCT_WHEAT",
    "BUY_LAND",
    "HIRE",
    "SELL",
)
UNIT_KEYS = ("MOVE", "WORK", "PASS", "OTHER")


class EconomicFlowUpstreamObserver(EconomicFlowObserver):
    def __init__(self):
        super().__init__()
        self.market_counts = {k: 0 for k in MARKET_KEYS}
        self.unit_counts = {k: 0 for k in UNIT_KEYS}

    @staticmethod
    def _market_key(a):
        if not a:
            return None
        kind = a[0]
        item = a[1] if len(a) > 1 else None
        if kind == "BUY_ANIMAL" and item == "COW":
            return "BUY_ANIMAL_COW"
        if kind == "BUY_PRODUCT" and item == "COW":
            return "BUY_PRODUCT_COW"
        if kind == "BUY_SEED" and item == "WHEAT":
            return "BUY_SEED_WHEAT"
        if kind == "BUY_PRODUCT" and item == "WHEAT":
            return "BUY_PRODUCT_WHEAT"
        if kind == "BUY_LAND":
            return "BUY_LAND"
        if kind == "HIRE":
            return "HIRE"
        if kind == "SELL":
            return "SELL"
        return None

    @staticmethod
    def _unit_key(a):
        if not a:
            return "OTHER"
        kind = a[0]
        if kind in ("NORTH","SOUTH","EAST","WEST"):
            return "MOVE"
        if kind in ("DIG","PLANT","WATER","HARVEST","FEED","CARE","DROP","PICKUP","PLACE","BUILD_PASTURE","COLLECT_FERTILIZER"):
            return "WORK"
        if kind == "PASS":
            return "PASS"
        return "OTHER"

    def observe_action(self, action):
        if not self.rows:
            return
        if not isinstance(action, dict):
            return

        for a in list(action.get("market", []) or []):
            k = self._market_key(a)
            if k:
                self.market_counts[k] += 1

        unit_actions = []
        farmer = action.get("farmer")
        if farmer:
            unit_actions.append(farmer)
        unit_actions.extend(list(action.get("hands", []) or []))
        for a in unit_actions:
            self.unit_counts[self._unit_key(a)] += 1

        row = self.rows[-1]
        row["market_semantic"] = [self._market_key(a) or (a[0] if a else "NONE") for a in list(action.get("market", []) or [])]
        row["farmer_action"] = action.get("farmer")
        row["hand_actions"] = list(action.get("hands", []) or [])
        for k, v in self.market_counts.items():
            row["cum_" + k] = v
        for k, v in self.unit_counts.items():
            row["cum_unit_" + k] = v
