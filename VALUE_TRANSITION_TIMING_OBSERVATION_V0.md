# Value Transition Timing Observation v0

Date: 2026-09-28
Branch: experiment/cross-view-timeline-v0-20260928
Source: Value Transition Timing Audit fresh10 v0
Status: Observation only. No policy adoption.

## Parent question

Given the same compact physical MILK state, does moving MILK to the next Return
Stage now versus later reliably improve realized Cash or terminal self?

A = Current D14
B = Seed reopen

The comparison starts at the last compact-MILK-equal live state before the
first compact MILK physical divergence.

## Confirmed

### 1. Earlier stage movement does not imply better terminal self

Observed compact-precursor cases: 9

Early mover:
- terminal better: 3/9
- terminal worse: 6/9
- mean early-mover minus later-arm terminal self: -311.8

Therefore:

**Earlier COW -> Carry transition is not a terminal-strength rule.**

Do not promote “harvest sooner” or “advance Return Stage sooner” as Policy.

### 2. Earlier stage movement usually changes Return-boundary timing

Examples:

seed7351:
- early mover next SELL MILK: D21h22, 5 turns after decision
- later arm: D22h0, 7 turns

seed7354:
- early mover: D20h21, 4 turns
- later arm: D21h0, 7 turns

seed7355:
- early mover: D21h22, 5 turns
- later arm: D22h0, 7 turns

seed7357:
- early mover: D20h0, 4 turns
- later arm: D20h2, 6 turns

seed7359:
- early mover: D21h22, 5 turns
- later arm: D22h0, 7 turns

seed7360:
- early mover: D23h22, 5 turns
- later arm: D24h0, 7 turns

Some cases reach the same SELL boundary timing:
- seed7352: 0 vs 0 turns
- seed7353: 2 vs 2
- seed7356: 0 vs 0

Thus Return-stage timing can move the realized Return boundary, but not always.

### 3. Earlier stage movement does not imply better total post-decision MILK Cash

Across the 9 observed cases:

- early mover MILK Cash better: 5
- early mover MILK Cash worse: 3
- one case equal
- mean early-mover minus later-arm MILK Cash: +403.9

The positive mean is not a stable separator and is heavily case-dependent.

Examples:

seed7355:
- early mover sells first 2 MILK at 7 / 5
- later arm sells first 2 at 19 / 17
- early mover total post-decision MILK Cash is lower by 1516

seed7359:
- early mover first 2 MILK at 135 / 133
- later arm first 2 at 122 / 120
- early mover total post-decision MILK Cash is higher by 3849

seed7351:
- earlier and later first sells both realize price 1
- boundary timing moves, but first-return value does not materially improve

### 4. Decision-time current MILK Market snapshot is usually not the separator

Mean early-mover minus later-arm decision-time:
- MILK market price: +0.11
- MILK market inventory: 0.0

Most cases have identical MILK market price/inventory at the decision turn.

Notable exceptions:
- seed7355: early mover market price is 10 lower
- seed7359: early mover market price is 11 higher and inventory 5 lower

But many cases with different later realized value begin from identical
decision-time MILK market snapshots.

Therefore:

**Current MILK price / inventory snapshot alone is insufficient to decide whether moving the Return Stage now is better.**

### 5. Timing is a transition variable, not yet a value signal

The strongest supported statement is:

Return Stage + Actor Position + Action
-> changes when the Return boundary can be reached.

But:

earlier Return-boundary arrival
does not by itself determine
-> realized MILK Cash sign
-> terminal self sign.

## View

Timing belongs in the model as part of the transition map:

- where value is now
- who can move it
- what action moves it
- how many turns until the next boundary

But Timing should not yet be used as a preference score.

The value of moving now depends on later World evolution and the rest of the
Battle path.

## Important negative result

The following candidate is closed:

> Current Market snapshot + immediate Return-stage timing is sufficient to
> decide whether value should move now.

The fresh10 does not support this.

Many decision points have equal current MILK price/inventory but different
later realized Cash and terminal outcomes.

## Consequence for next-model representation

Keep:
- Return Stage
- Actor Position
- Available / submitted Action
- Time to next Return boundary

Do not yet add:
- “move now” bonus
- “hold” bonus
- fixed harvest-delay rule
- current-price-only harvest gate

World context likely needs temporal information rather than only a point
snapshot if it is to help valuation.

That temporal information is not yet specified or confirmed.

## Current frontier

The next question is narrower than “when should we harvest?”:

> When two live states have the same current physical value and similar current
> Market snapshot, what already-observed history or World trajectory
> distinguishes the later Return value?

Possible observable candidates for a future probe:
- recent MILK price / inventory trajectory
- recent realized SELL flow
- opponent SELL flow
- other sell-ready outputs
- remaining horizon

These remain candidates only.

Do not add them all at once.
