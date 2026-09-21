"""Economic Flow Observer v0.

Observer-only sidecar for Kaggriculture.
No action/strategy instruction is produced.

Local proxies only:
- cash / drawdown
- feed gap
- output inventory as a weak residence/backlog proxy
- cow workload per unit
- monetization signal (output release + positive cash delta)
- cash recovery episodes

These are proxies, not a unified Economic Flow score.
"""

class EconomicFlowObserver:
    def __init__(self):
        self.rows = []
        self.peak_cash = None
        self.drawdown_ref = None
        self.drawdown_start = None
        self.recovery_times = []
        self.output_streak = 0
        self.max_output_streak = 0

    @staticmethod
    def _state(obs):
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        shed = private.get("shed", {}) or {}
        inventories = private.get("inventories", []) or []

        def total(item):
            return int(shed.get(item, 0) or 0) + sum(int(inv.get(item, 0) or 0) for inv in inventories)

        farm_cows = 0
        feed_need = 0
        for row in me.get("tiles", []):
            for tile in row:
                if isinstance(tile, dict) and tile.get("animal") == "COW":
                    farm_cows += 1
                    if not tile.get("fed_today", False):
                        feed_need += 1

        cows = total("COW") + farm_cows
        wheat = total("WHEAT")
        outputs = sum(total(k) for k in ("MILK", "WOOL", "EGG", "FERTILIZER"))
        return {
            "day": int(obs.get("day", 0) or 0),
            "money": float(me.get("money", 0) or 0),
            "units": 1 + len(me.get("hands", []) or []),
            "cows": cows,
            "farm_cows": farm_cows,
            "wheat": wheat,
            "feed_need": feed_need,
            "outputs": outputs,
            "land": len(me.get("unlocked_quadrants", []) or []),
        }

    def observe(self, obs):
        s = self._state(obs)
        turn = len(self.rows)
        prev = self.rows[-1] if self.rows else None

        money = s["money"]
        if self.peak_cash is None:
            self.peak_cash = money
        if money > self.peak_cash:
            self.peak_cash = money

        drawdown = max(0.0, self.peak_cash - money)
        if drawdown > 0 and self.drawdown_start is None:
            self.drawdown_start = turn
            self.drawdown_ref = self.peak_cash
        elif self.drawdown_start is not None and money >= float(self.drawdown_ref):
            self.recovery_times.append(turn - self.drawdown_start)
            self.drawdown_start = None
            self.drawdown_ref = None

        feed_gap = max(0, s["feed_need"] - s["wheat"])
        feed_stress = 0.0 if s["feed_need"] <= 0 else feed_gap / max(1, s["feed_need"])
        cow_workload = s["farm_cows"] / max(1, s["units"])

        if s["outputs"] > 0:
            self.output_streak += 1
            self.max_output_streak = max(self.max_output_streak, self.output_streak)
        else:
            self.output_streak = 0

        cash_delta = 0.0 if prev is None else money - prev["money"]
        output_delta = 0 if prev is None else s["outputs"] - prev["outputs"]
        monetization = bool(prev is not None and output_delta < 0 and cash_delta > 0)

        row = {
            "turn": turn,
            **s,
            "cash_delta": cash_delta,
            "drawdown": drawdown,
            "feed_gap": feed_gap,
            "feed_stress": round(feed_stress, 6),
            "cow_workload": round(cow_workload, 6),
            "output_residence_streak": self.output_streak,
            "monetization_signal": monetization,
        }
        self.rows.append(row)
        return row

    def summary(self):
        rows = self.rows
        unresolved_age = 0 if self.drawdown_start is None else len(rows) - self.drawdown_start
        return {
            "turns": len(rows),
            "min_cash": min((r["money"] for r in rows), default=None),
            "max_drawdown": max((r["drawdown"] for r in rows), default=0.0),
            "feed_stress_turns": sum(r["feed_gap"] > 0 for r in rows),
            "feed_gap_area": sum(r["feed_gap"] for r in rows),
            "max_feed_gap": max((r["feed_gap"] for r in rows), default=0),
            "output_inventory_area": sum(r["outputs"] for r in rows),
            "max_output_inventory": max((r["outputs"] for r in rows), default=0),
            "max_output_residence_streak": self.max_output_streak,
            "monetization_events": sum(r["monetization_signal"] for r in rows),
            "positive_cash_return": sum(max(0.0, r["cash_delta"]) for r in rows),
            "recovery_episode_count": len(self.recovery_times),
            "mean_recovery_calls": (
                sum(self.recovery_times) / len(self.recovery_times)
                if self.recovery_times else None
            ),
            "max_recovery_calls": max(self.recovery_times) if self.recovery_times else None,
            "unresolved_drawdown": self.drawdown_start is not None,
            "unresolved_drawdown_age": unresolved_age,
        }
