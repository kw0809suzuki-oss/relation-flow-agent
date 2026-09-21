"""Cash Jump Transition Observer v0.

Focused observer for the COW suppression fresh10 transition window.
Observer only. No control changes.

Captures:
- per-item inventory
- cash jump
- action immediately preceding each state transition
- small turn window around known cash separators
"""

from economic_flow_upstream_observer_v01 import EconomicFlowUpstreamObserver


ITEMS = ("MILK", "WOOL", "EGG", "FERTILIZER", "WHEAT", "COW")


class CashJumpTransitionObserver(EconomicFlowUpstreamObserver):
    @staticmethod
    def _totals(obs):
        private = obs["private"]
        shed = private.get("shed", {}) or {}
        inventories = private.get("inventories", []) or []
        def total(item):
            return int(shed.get(item, 0) or 0) + sum(int(inv.get(item, 0) or 0) for inv in inventories)
        return {item: total(item) for item in ITEMS}

    def observe(self, obs):
        row = super().observe(obs)
        row["item_totals"] = self._totals(obs)
        return row
