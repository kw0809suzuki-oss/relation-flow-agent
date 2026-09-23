# Crop Demand Execution Gap v0

BattleTransitionBundle

From:
Crop Loss Overlay Rewrite v0.

Change:
No policy change.
Observe the unique day5-12 turns that precede a next-day crop-surface decrease.

Fixed:
- current objective_pressure_guidance
- current livestock overlay
- opponent
- seeds 7211-7220
- no candidate intervention

Working Hypothesis:
Base policy is requesting crop maintenance/growth work, but livestock overlay reduces
the executed crop work by diverting unit slots into livestock routing/maintenance.

Expected Evidence:
Keep this hypothesis if crop-loss precursor turns show a repeatable positive gap:
base WATER/HARVEST/PLANT demand > actual WATER/HARVEST/PLANT execution,
with the missing executions corresponding to overlay-changed unit slots.

Important separation:
crop loss != crop maintenance failure.
This observer only measures requested-vs-executed crop work and the following crop
surface change. It does not infer why a crop tile disappeared.

Counting:
Each turn is counted once per seed even if multiple crop-loss windows would overlap.
