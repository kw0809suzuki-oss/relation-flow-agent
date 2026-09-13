# V2 vector Relation Flow — 24-case expansion

## Purpose
Check whether the V2 vector-majority Relation Flow effect survives a wider case set without changing the controller.

## Fixed before execution
- Controller: unchanged `whole_flow_control_agent_v2.py`
- Relation axes: money / capacity / public production
- Relation decision: 2-of-3 axis majority
- Movement decision: 2-of-3 axis majority
- Action mapping: unchanged from V1/V2 (`push=0.04`, `maintain=0.04`, `stop=0.02`, `switch=0.00`)
- Opponent: same pinned Seyamalam v21 revision
- Existing 12 cases: retained exactly
- New cases: next 12 unseen consecutive seeds, 3252–3263, alternating seats 0/1
- No result-dependent tuning during this run

## Cases
Existing:
`(3202,0),(3206,0),(3215,1),(3218,0),(3222,0),(3227,1),(3231,1),(3240,0),(3243,1),(3246,0),(3250,0),(3251,1)`

Added:
`(3252,0),(3253,1),(3254,0),(3255,1),(3256,0),(3257,1),(3258,0),(3259,1),(3260,0),(3261,1),(3262,0),(3263,1)`

## Evaluation
Primary:
- mean margin delta
- improved / worsened / equal
- largest worsening
- candidate wins vs baseline wins

Secondary:
- action-difference cases
- total action differences

## Decision rule
- Continue: positive tendency survives expansion without materially worse downside
- Cut: mean advantage disappears or downside materially worsens
- Probe: mixed result remains and a new design unit is needed

This expansion tests the same V2 design on more cases. It is not a new controller version.