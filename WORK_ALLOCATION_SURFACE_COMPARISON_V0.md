# Work Allocation Surface Comparison v0

Date: 2026-09-28
Branch: experiment/cross-view-timeline-v0-20260928
Source: Work Allocation Surface Compare fresh10 v0
Status: Observation only. No policy adoption.

## Parent question

At the last compact-MILK-equal turn immediately before the first MILK physical
stage divergence, does the broad visible Work Allocation Surface separate
SELF_IMPROVED from SELF_WORSE Seed-reopen cases?

A = Current D14
B = Seed reopen

## Sample

10 fixed cases:
- 7 SELF_IMPROVED
- 3 SELF_WORSE

One improved case, seed7358, has no compact MILK physical precursor before its
first MILK SELL boundary difference and is excluded from the last-equal
surface comparison.

Observed comparison set:
- SELF_IMPROVED: 6
- SELF_WORSE: 3

## Confirmed

### 1. B increases crop workload in both outcome groups

Mean B-A at the last compact-MILK-equal turn:

SELF_IMPROVED:
- plant tiles: +4.83
- harvestable crop count: +3.00
- harvestable crop yield: +5.17
- water-needed plant count: +4.50

SELF_WORSE:
- plant tiles: +6.00
- harvestable crop count: +2.00
- harvestable crop yield: +2.33
- water-needed plant count: +4.00

Therefore:
**more crop work under B is a general Seed-reopen path effect, not a terminal-sign separator in this sample.**

### 2. Cash is lower under B in both groups at the comparison boundary

Mean B-A Cash:

- SELF_IMPROVED: -447.3
- SELF_WORSE: -358.7

This does not separate the sign of terminal self.

### 3. Hands / animal workload do not provide a stable separator

SELF_IMPROVED:
- hands count mean delta: 0
- care-needed animals: -0.33
- feed-needed animals: -0.33

SELF_WORSE:
- hands count mean delta: +0.33
- care-needed animals: +0.33
- feed-needed animals: 0

The differences are small and case-dependent.
No stable separator is established.

### 4. Submitted action composition is heterogeneous in both groups

Examples:

SELF_IMPROVED:
- seed7351: B has +5 PLANT and -1 HARVEST
- seed7353: B has +4 PLANT and +1 HARVEST
- seed7354: B has +3 HARVEST
- seed7356: B has -1 HARVEST

SELF_WORSE:
- seed7357: B has +1 HARVEST
- seed7359: B has -1 HARVEST and -4 WATER
- seed7360: B has -1 HARVEST and +4 WATER

Thus:
**PLANT / WATER / HARVEST action-count direction does not separate improved from worsened cases.**

### 5. Immediate MILK stage transition remains mechanically explained by actor position + action

Although the broad Work Allocation Surface does not classify terminal sign,
the local transition remains direct:

- when one arm has an actor standing on a harvestable COW and submits HARVEST,
  that arm moves visible MILK from COW yield to actor Carry on the next state;
- the other arm often has the corresponding actor elsewhere or submitting
  another action.

This direct boundary was already observed in 9/9 compact-precursor cases.

Examples:

seed7351, SELF_IMPROVED:
- A hand stands on harvestable COW [2,3] and HARVESTs
- B corresponding work surface has no actor on that COW; actors are on CARE /
  PLANT path
- next MILK stage differs

seed7357, SELF_WORSE:
- B hand stands on harvestable COW [1,4] and HARVESTs
- A does not
- next MILK stage differs

Both directions occur in both terminal outcome groups.

## Judge

### Close

Close this candidate:

> Broad Work Allocation pressure is a terminal-sign separator for Seed reopen.

The fresh10 does not support it.

Do not rescue it by inventing a weighted pressure score from PLANT / WATER /
CARE / HARVEST counts.

### Keep

Keep this narrower representation role:

> Actor position + submitted action + Return-stage position are sufficient to
> describe the immediate observed MILK stage transition.

This is a transition-state representation, not a strength rule.

## Consequence for the next strong model

Do not add a generic Work Allocation score yet.

Retain only externally grounded state components:
- Return-stage position
- actor positions
- actor carried inventory
- harvestable output at the actor's tile / target surface
- submitted / candidate action
- World context at the later Return boundary

The next model may use these to represent **where work can move value next**,
but Battle must still determine whether that movement is strategically good.

## Current frontier

The remaining unresolved question is no longer:

> Is crop workload stealing workers from MILK?

That broad explanation is unsupported as a terminal separator.

The sharper question is:

> Given two states with similar physical value, what live State tells us whether
> moving a Return bundle to the next stage now is better than leaving it where it is?

That question points back to:
- Return stage
- remaining horizon
- current / near-future market context
- competing realizable outputs

No policy is adopted here.
