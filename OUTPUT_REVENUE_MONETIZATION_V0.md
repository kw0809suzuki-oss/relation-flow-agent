# Output Revenue Monetization v0

BattleTransitionBundle

From:
Crop Maintenance Protection v0 rejection.

Change:
No policy change.
Move observation from occupied surface to actual value flow during day 5-15.

Fixed:
- current objective_pressure_guidance
- current livestock overlay
- opponent
- battle rules
- no candidate intervention

Working Hypothesis:
The large terminal gap may lie not in occupied surface, but in how quickly and how
densely owned assets become harvested/stored outputs, sales, and cash.

Expected Evidence:
Keep this direction if day 5-15 shows a repeatable separation between:
harvest/output formation -> sellable stock -> SELL flow -> cash return.
Revise it if current already converts outputs to cash at a comparable pace and scale.

Observe:
- exact self total private stock by item (shed + all inventories)
- exact self SELL / BUY_PRODUCT market orders and contemporaneous market prices
- exact self HARVEST action count
- day-level gross sell face value
- day-level stock change
- balance-derived materialized units:
  end_stock - start_stock + sold_units - bought_product_units
- self and opponent day-end money

Boundary:
Balance-derived materialized units are an accounting proxy, not direct causal
attribution to HARVEST. Gross sell face value is order-value at observed prices,
not isolated net cashflow.
