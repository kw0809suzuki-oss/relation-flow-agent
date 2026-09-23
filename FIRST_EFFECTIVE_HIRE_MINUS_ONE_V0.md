# First Effective HIRE Minus One v0

BattleTransitionBundle

From:
Mode-to-Action Reachability Path v0.

Change:
At the first turn where:
- coarse reading is continuity,
- current objective-pressure choice is throughput_match,
- current would actually execute at least one HIRE,
suppress exactly one HIRE on that turn.

Fixed:
- Flow-chan guidance
- objective-pressure chooser
- seed/seat/opponent
- seed buying, land, movement, harvest, planting logic
- all later HIRE decisions after the one-shot suppression

Working Hypothesis:
The first effective coarse-vs-current Action difference may be the HIRE -1 transition,
rather than the earlier mode divergence itself.

Expected Evidence:
Keep the hypothesis only if the one-shot intervention reaches Action and produces
a repeatable terminal effect versus current. Drop it if it does not reach Action
or terminal remains neutral/negative.

This is a scripted Battle probe, not a promoted Rule.
