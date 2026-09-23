# Money Path Ledger v0

BattleTransitionBundle

From:
Output Revenue Monetization v0.

Change:
No policy change.
Observe day 10-15 at turn granularity and reconcile visible money movement against
the exact market orders requested on the prior turn.

Fixed:
- current objective_pressure_guidance
- current livestock overlay
- opponent
- battle rules
- no candidate intervention

Working Hypothesis:
Self is requesting large nominal SELL value, but either those sells are not fully
materializing into cash or the realized cash is being immediately absorbed by
reinvestment / maintenance.

Expected Evidence:
Separate the two cases:
1. nominal SELL is not followed by matching inventory release / money movement;
2. SELL activity coincides with positive cash movement, but same-day purchases /
   expansion / hiring absorb most of it.

Observe for each turn in day 10-15:
- money before / next-observation money after / delta
- exact market orders
- nominal SELL face value
- nominal priced BUY_PRODUCT / BUY_SEED / BUY_ANIMAL face value
- HIRE / BUY_LAND counts
- private stock before / after
- requested sold units and observed stock release proxy
- residual money movement after priced market order face values

Boundary:
The environment does not expose a direct settlement receipt here.
Stock release and order-value reconciliation are accounting proxies, not proof that
a specific order filled or that a specific cost caused the money delta.
