# Macro Strength Gap Re-entry v0

BattleTransitionBundle

From:
Recent local Bundles around mode -> Action -> terminal.

Change:
No policy change. Observation scale changes from local Current-vs-Candidate differences
to the whole Battle objective distance.

Fixed:
- current objective_pressure_guidance
- opponent
- battle rules
- fresh paired-style seat alternation
- no candidate intervention

Working Hypothesis:
The dominant missing structure is not a local divergence but the large persistent
self-vs-opponent strength gap. The useful next battlefield should be located where
that gap first becomes large and remains large.

Expected Evidence:
Keep this direction if a coarse Battle-wide view identifies a repeatable phase where
visible self-vs-opponent gaps expand to a scale comparable with the terminal residual.
Drop or revise it if no stable large-scale separation appears.

Scale Check:
Always report:
- baseline absolute mean terminal self
- opponent absolute mean terminal self
- mean terminal residual (opponent - self)
- local recent effect size / residual when available

Observation:
Record visible comparable state every turn, then aggregate to day-end:
- money
- hands
- unlocked land
- visible planted crop tiles
- visible animal tiles
- occupied visible production tiles

Purpose:
Find the first large, persistent gap. Do not explain it yet.
