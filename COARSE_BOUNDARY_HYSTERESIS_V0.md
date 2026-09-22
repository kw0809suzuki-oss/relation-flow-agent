# Coarse Boundary Hysteresis v0

BattleTransitionBundle step:
Battle1 observation -> working hypothesis -> minimal intervention -> Battle2.

Observation from Battle1:
coarse-boundary candidate improved mean self/margin vs current objective-pressure guidance,
but boundary changes were frequent.

Working hypothesis:
some of those boundary changes are chatter. Requiring a proposed non-endgame
regime to persist briefly before switching may preserve useful direction.

Minimal intervention:
- keep the same regime definitions and same Flow-chan guidance
- require 3 consecutive turns before switching between competitive/continuity
- endgame switch remains immediate

This is a probe, not a promoted Rule.
Primary decision: Battle terminal self / margin.
