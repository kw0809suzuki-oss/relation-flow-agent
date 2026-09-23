# Crop Loss Overlay Rewrite v0

BattleTransitionBundle

From:
Cash to Capacity Conversion v0.

Change:
No policy change.
Observe only day 5-12 turns immediately before a next-day crop tile decrease.

Fixed:
- current objective_pressure_guidance
- livestock overlay logic
- opponent
- seeds 7211-7220
- no candidate intervention

Working Hypothesis:
Livestock overlay may convert added labor into livestock maintenance by replacing
crop-oriented base actions, causing capacity substitution rather than net expansion.

Expected Evidence:
Keep this hypothesis only if crop-loss windows repeatedly contain overlay rewrites
from crop-maintenance/growth base actions into livestock actions.
Revise or drop it if crop-loss windows do not show that pattern.

Observe:
- base_action from Strong Origin before livestock overlay
- final action after livestock overlay
- which unit slots changed
- action class before/after
- next-day crop tile delta
- current cows / hands / crop tiles / production tiles

Boundary:
Temporal adjacency is not causal proof.
