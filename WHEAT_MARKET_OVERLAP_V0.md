# WHEAT Market Overlap v0

BattleTransitionBundle

From:
Item Value Density v0.

Change:
No policy change.
Observe WHEAT SELL and BUY_PRODUCT overlap on the same turn/day during day 10-20.

Fixed:
- current objective_pressure_guidance
- current livestock overlay
- opponent
- battle rules
- no candidate intervention

Working Question:
Is the large WHEAT turnover partly caused by base monetization and livestock feed
procurement issuing opposite market actions on the same turn/day?

Observe:
- SELL WHEAT units / face value
- BUY_PRODUCT WHEAT units / face value
- same-turn overlap
- same-day overlap
- net WHEAT market flow
- next-observation money delta
- whether base_action contained SELL WHEAT
- whether final_action added BUY_PRODUCT WHEAT

Interpretation boundary:
- Market orders are requests, not direct settlement receipts.
- Same-turn opposite orders show policy-layer conflict at the action surface, not
  necessarily realized round-trip loss.
- No efficiency or causality conclusion is made until Battle intervention.
