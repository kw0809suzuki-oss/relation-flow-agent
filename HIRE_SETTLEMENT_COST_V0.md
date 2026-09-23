# HIRE Settlement Cost v0

BattleTransitionBundle

From:
Money Path Ledger v0.

Change:
No policy change.
Observe HIRE requests and whether hands actually increase on the next observation.

Fixed:
- current objective_pressure_guidance
- current livestock overlay
- opponent
- battle rules
- no candidate intervention

Working Hypothesis:
A material part of the stable unexplained cash drain may occur when HIRE requests
actually settle, rather than whenever HIRE is merely requested.

Expected Evidence:
Keep this direction if next-observation hands +1 (or more) events align with a
repeatable negative money residual after subtracting priced SELL/BUY market flows,
while HIRE-request turns with no hand increase do not show the same residual.

Observe:
- HIRE requested on current turn
- next-observation hands delta
- money before/after
- priced SELL face
- priced BUY face
- residual after priced market face
- whether a HIRE settlement proxy occurred (hands_delta > 0)

Boundary:
hands_delta > 0 is a settlement proxy, not proof that one specific HIRE order caused
the increase. Multiple hand gains can occur; no assumed HIRE price is injected.
