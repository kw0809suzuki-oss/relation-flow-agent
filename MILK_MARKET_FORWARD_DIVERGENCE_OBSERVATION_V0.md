# MILK Market Forward Divergence Observation v0

Date: 2026-09-28
Branch: experiment/cross-view-timeline-v0-20260928
Source: MILK Market Forward Divergence Probe fresh10 v0
Status: Observation only. No policy adoption.

## Parent question

For cases where A/B share:
- the same current MILK market price/inventory, and
- the same previous 6-turn raw MILK price/inventory history

does the MILK market itself diverge before the first realized SELL MILK
boundary difference?

## Primary set

7 matched cases:
- 7351
- 7352
- 7353
- 7354
- 7356
- 7357
- 7360

Excluded:
- 7355 / 7359: current MILK market snapshot already differs at the decision point
- 7358: no compact physical MILK precursor

## Confirmed

### 1. MILK pre-market state does not diverge before the first SELL difference

Across all 7 matched cases:

- pre-market MILK price/inventory diverges before first SELL difference: 0/7
- pre-market MILK price/inventory first diverges at first SELL difference: 0/7
- pre-market MILK price/inventory remains equal through first SELL difference: 7/7

Therefore the tested MILK market path does not supply an earlier separator
between the decision point and the first realized MILK Return boundary.

### 2. The first MILK market-event difference is the SELL boundary itself

Across all 7 matched cases:

- MILK market event differs before first SELL difference: 0/7
- MILK market event first differs at first SELL difference: 7/7

Examples:

seed7351:
- decision D21h17
- physical MILK stage differs D21h18
- MILK market remains equal
- D21h22: A sells MILK, B does not

seed7353:
- decision D20h11
- physical MILK stage differs D20h12
- MILK market remains equal
- D20h14: B sells MILK, A does not

seed7357:
- decision D19h20
- physical MILK stage differs D19h21
- MILK market remains equal
- D20h0: B sells MILK, A does not

seed7360:
- decision D23h17
- physical MILK stage differs D23h18
- MILK market remains equal
- D23h22: A-side MILK market execution differs; B has no matching MILK sale

### 3. Post-market MILK state often diverges only because the SELL event diverged

At the first SELL-difference timestamp:

- post-market MILK state diverges: 5/7
- post-market MILK state remains equal through that boundary: 2/7

In the 5 cases, the divergence occurs after different MILK market execution in
that same boundary.

Thus, for the primary matched set, observed MILK market divergence is a
downstream consequence of different realized MILK market execution at the
Return boundary, not an observed pre-existing MILK-market precursor.

## Judge

### Close for the matched-current/history cases

Close this tested explanation:

> A hidden MILK market divergence appears after the decision but before SELL,
> and that divergence determines which Return path is valuable.

World returned 0/7 pre-SELL MILK market divergence.

Also keep closed:
- current MILK snapshot as sufficient Value Signal
- previous 6-turn raw MILK history as hidden separator
- simple “move earlier” preference

### Keep the boundary distinction

The supported ordering for these 7 cases is:

same current MILK market
+ same short MILK market history
-> physical Return-stage divergence
-> MILK market remains equal
-> realized SELL MILK execution diverges
-> MILK market may diverge after that SELL

This is chronology, not full causal proof.

## Important boundary

Do not generalize this to all cases.

seed7355 and seed7359 already have different MILK market snapshot at the
decision point. They remain a separate class where World context is already
different before the local Return-stage decision.

The present result applies only to the 7 matched-current/history cases.

## Consequence for next-model representation

For the matched set, the missing Value Signal should not be searched for in
hidden short MILK market trajectory.

The unresolved difference sits in the Return path between:

physical stage
-> SELL-ready availability / bundle
-> realized SELL execution

The next useful representation should therefore preserve:
- Return Stage
- actor position / available transition
- amount becoming SELL-ready
- time to SELL boundary
- same-turn realized SELL bundle

without turning those fields into a preference rule yet.

## Current frontier

The next question is:

> Between the first physical MILK stage divergence and the first SELL boundary
> difference, what exact Return-path boundary first differs in a way that is
> specific to MILK availability or SELL readiness?

This asks about the Return pipeline itself, not Market forecasting.
