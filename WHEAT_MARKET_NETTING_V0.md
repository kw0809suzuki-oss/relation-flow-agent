# WHEAT Market Netting v0

BattleTransitionBundle

From:
WHEAT Market Overlap v0.

Change:
On day 10-20 only, when final Action contains both:
- SELL WHEAT S
- BUY_PRODUCT WHEAT B

replace them by the net order only:
- if S>B: SELL WHEAT (S-B)
- if B>S: BUY_PRODUCT WHEAT (B-S)
- if S=B: no WHEAT market order

Fixed:
- net WHEAT market units per turn
- all non-WHEAT market orders
- crop policy
- livestock targets / feed target
- unit actions
- opponent
- objective_pressure_guidance

Working Hypothesis:
Same-turn opposite WHEAT gross orders are economically harmful enough that removing
only the gross overlap improves terminal self while preserving net WHEAT market flow.

Expected Evidence:
Paired fresh10. Record:
- baseline absolute mean self
- candidate absolute mean self
- delta
- paired improve / worse / tie
- modified turns / overlap units removed

Interpretation:
This tests Battle value of the overlap itself. It does not require proving which
policy layer produced each side of the conflict.
