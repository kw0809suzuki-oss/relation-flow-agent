# MILK Raw Market History Presence Observation v0

Date: 2026-09-28
Branch: experiment/cross-view-timeline-v0-20260928
Source: MILK Raw Market History Presence Probe fresh10 v0
Status: Observation only. No policy adoption.

## Parent question

When A/B have the same current MILK market snapshot at the last compact-MILK-
equal decision point, does the immediately preceding live MILK market history
already contain a difference that the current snapshot hides?

Fixed test condition:
- previous 6 completed turns
- raw MILK price only
- raw MILK market inventory only
- no trend, slope, persistence score, moving average, or fitted feature

## Confirmed

### 1. Seven compact-precursor cases have exact-equal current MILK market snapshot

Observed compact-precursor cases: 9.

Exact-equal current MILK price and inventory:
- seed7351
- seed7352
- seed7353
- seed7354
- seed7356
- seed7357
- seed7360

Current snapshot differs:
- seed7355
- seed7359

seed7358 has no compact physical MILK precursor and is outside this comparison.

### 2. For all 7 current-snapshot-equal cases, the previous 6-turn raw market history is also exactly equal

Primary result:

- current snapshot exact equal cases: 7
- identical previous-6-turn raw price/inventory history: 7/7
- different previous-6-turn raw price/inventory history: 0/7

There is no hidden A/B MILK market difference in this fixed short history window
for the cases where the current snapshot is equal.

This holds across both terminal directions:

SELF_IMPROVED:
- 7351
- 7352
- 7353
- 7354
- 7356

SELF_WORSE:
- 7357
- 7360

Thus the absence of a short-history difference is not specific to one terminal
outcome group.

### 3. The two cases with different current snapshot also have different recent history

seed7355:
- current A: price 9 / inventory 10072
- current B: price 19 / inventory 10067
- previous 6-turn history already differs

seed7359:
- current A: price 135 / inventory 10012
- current B: price 124 / inventory 10017
- previous 6-turn history already differs

These cases do not provide evidence that history adds information beyond the
current snapshot, because the current snapshot itself already differs.

## Judge

### Close this tested candidate

Close:

> A short recent MILK market trajectory contains a hidden A/B difference when
> the current MILK market snapshot is equal.

Under the fixed previous-6-turn raw-history test, World returned 0/7.

Do not rescue this result by creating:
- price trend labels
- inventory trend labels
- slope
- persistence duration
- moving averages
- weighted trajectory scores

There is no raw A/B difference in the tested window to compress.

### Do not overgeneralize

This result does NOT prove:
- all possible longer market histories are always identical
- market history can never matter in Kaggriculture
- future market evolution is irrelevant

It proves only that the tested short live history does not supply the missing
A/B separator in these seven matched current-snapshot cases.

## Consequence

The planned second probe:

> If recent history differs, does that difference correspond to later Return Cash?

is NOT run.

Its prerequisite failed: there are zero matched-current cases with a different
6-turn raw history.

## Updated frontier

For the matched-current cases, the later Return-value divergence is not already
visible in:
- current MILK price
- current MILK inventory
- previous 6 turns of raw MILK price
- previous 6 turns of raw MILK inventory

Yet the later Return boundary / Cash can still differ.

Therefore the next useful question moves forward from the decision boundary:

> What is the first externally observed post-decision World event that makes
> the later MILK Return paths diverge?

This is a new question and should not be answered by inventing pre-decision
features.

Possible surfaces must be taken from the actual post-decision Battle trace,
one boundary at a time.
