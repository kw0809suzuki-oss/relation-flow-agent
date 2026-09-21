"""MILK6 Cash-back Decomposition Observer v0.

Focused on the 197->198 transition in historical COW suppression fresh10.
Observer-only: captures exact raw market actions and per-item inventory changes.
No causal promotion and no control change.
"""

from cash_jump_transition_observer_v0 import CashJumpTransitionObserver


class Milk6CashbackDecompositionObserver(CashJumpTransitionObserver):
    def observe_action(self, action):
        super().observe_action(action)
        if not self.rows or not isinstance(action, dict):
            return
        self.rows[-1]["raw_market"] = list(action.get("market", []) or [])
