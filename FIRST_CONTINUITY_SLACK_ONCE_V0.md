# First Continuity Slack Once v0

BattleTransitionBundle step:
Battle2 observation -> working hypothesis -> minimal intervention -> Battle3.

Observed:
Across the five terminal-difference seeds from Coarse Boundary Guidance v0,
the first common Action divergence occurred at entry into continuity/slack.

Working hypothesis:
Reproducing only that first divergence may preserve part of the coarse candidate's value.

Minimal intervention:
- Flow-chan guidance unchanged.
- Detect the same temporary continuity condition used by the coarse candidate.
- On the first continuity entry only, apply throughput_with_slack for one turn.
- After that single turn, return to current objective_pressure_guidance.
- No persistent regime control. No hysteresis. No further slack forcing.

This is a Battle probe, not a promoted Rule.
Primary evaluation: terminal self / margin.
