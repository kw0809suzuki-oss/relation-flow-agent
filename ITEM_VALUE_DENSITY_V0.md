# Item Value Density v0

BattleTransitionBundle

From:
Value Source Re-entry v0.

Change:
No policy change.
Observe self item-level monetization and item availability/materialization on day 10-20.

Fixed:
- current objective_pressure_guidance
- current livestock overlay
- opponent
- battle rules
- no candidate intervention

Working Question:
Is self's WHEAT-heavy sell mix mainly a sell-selection problem
(high-value stock exists but is not sold), or a production-composition problem
(high-value output is scarcely available/materialized)?

Observe per item / day:
- requested SELL units
- SELL face value
- face value per sold unit
- share of total SELL units
- share of total SELL face value
- private stock at day start / day end
- BUY_PRODUCT units
- materialized_units_proxy = end_stock - start_stock + sold_units - bought_product_units

Interpretation boundary:
- SELL is an order-side proxy, not a settlement receipt.
- private stock is availability context, not proof that every unit was sellable at that moment.
- materialized_units_proxy is accounting-derived and may include concurrent consumption / placement effects.
- no Candidate is selected from this observer alone.
