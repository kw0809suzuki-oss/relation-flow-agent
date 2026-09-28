# MILK Return Boundary Observation v0

Date: 2026-09-28  
Branch: experiment/cross-view-timeline-v0-20260928  
Source run: MILK Return Boundary Audit fresh10 v0  
Status: Observation only. No policy adoption.

## Parent question

After reopening D14 Seed purchases, why did terminal self improve in 7 cases and worsen in 3?

This note isolates the realized MILK Return boundary only.

## Confirmed

### 1. MILK quantity does not separate improved from worsened cases

Post-D14 A->B MILK unit delta:

SELF_IMPROVED 7:
- mean +0.57 units

SELF_WORSE 3:
- mean +1.00 units

Examples:
- seed7357 worsened despite +7 MILK units
- seed7360 worsened despite +1 MILK unit
- seed7358 improved despite -6 MILK units

Therefore realized MILK quantity alone does not explain the sign of terminal self delta.

### 2. Realized MILK Cash differs strongly by group in this fresh10

SELF_IMPROVED 7:
- mean MILK Cash delta: +822.7
- positive: 4
- negative: 2
- zero: 1

SELF_WORSE 3:
- mean MILK Cash delta: -1,954.0
- negative: 3/3

This is an observed association in the tested fresh10, not a causal rule.

### 3. Average realized MILK unit price is negative in all three worsened cases

SELF_IMPROVED 7:
- mean delta average realized MILK price: +4.76
- positive cases: 4
- negative cases: 3

SELF_WORSE 3:
- mean delta average realized MILK price: -13.71
- negative cases: 3/3

Again, price sign is not sufficient for improvement because some improved cases also have lower average realized MILK price.

### 4. Price/timing effect dominates the worsened-group MILK Cash loss

Exact decomposition:
B MILK Cash - A MILK Cash
= quantity effect at A average price
+ price effect on B realized units

Group means:

SELF_IMPROVED:
- quantity effect: +217.8
- price effect: +604.9
- total MILK Cash delta: +822.7

SELF_WORSE:
- quantity effect: -154.6
- price effect: -1,799.4
- total MILK Cash delta: -1,954.0

Within this fresh10, the large worsened-group MILK loss is mainly associated with realized price/timing, not count.

### 5. First MILK Return boundary differences are timestamp / market-state differences

Examples:

seed7358, SELF_IMPROVED:
- first differing MILK boundary D22 h0
- A sells 2 MILK at 11, 9
- B sells 2 MILK at 24, 22
- B market inventory before those commits is lower than A

seed7359, SELF_WORSE:
- first differing MILK boundary D21 h22
- A sells 2 MILK at 135, 133
- B has no MILK sale at that timestamp

seed7360, SELF_WORSE:
- first differing MILK boundary D23 h22
- A sells 2 MILK at 133, 131
- B has no MILK sale at that timestamp

seed7357, SELF_WORSE:
- first differing MILK boundary D20 h0
- B sells 1 MILK at price 1
- A does not sell MILK at that timestamp

These are direct realized-market observations.

## View

Seed reopening does more than add crops.

It changes the Battle path enough that an existing non-Seed Return lane, MILK, reaches different market states and different sale timestamps.

The smallest supported View is:

Seed Filter change
→ Battle path changes
→ MILK Return boundary changes
→ realized MILK Cash changes

The arrows above are chronological / representational connection, not proven causal attribution.

## What is NOT confirmed

Do not promote:
- “MILK price determines whether Seed reopen is good”
- “sell MILK only at high price”
- “Market caused the terminal delta”
- “MILK is the main strength mechanism”
- “Seed reopening should be gated by current MILK price”

Improved cases 7352 / 7353 / 7356 show that terminal self can improve even when average realized MILK price does not improve.

## Consequence for next-model representation

This observation strengthens, but does not yet prove, the need for World context at Return boundaries.

A future live representation should be able to expose:
- current product price
- current market inventory
- product stock ready to sell
- recent realized price / return
- time to terminal
- same-turn market bundle

Reason:
the same or similar quantity of physical output can realize materially different Cash depending on when it crosses the market boundary.

This is stronger than adding Market context merely because Farm-only state was insufficient.

## Next high-information Probe

Do not add a MILK policy yet.

Compare A/B on the exact first MILK-boundary divergence and ask:

**What upstream State difference made the MILK bundle cross the market boundary at a different timestamp?**

Trace one step upstream only:
- MILK stock availability
- HARVEST timestamp
- Carry / Shed arrival
- market bundle timing

Stop once World identifies the first physical separator.

This tests whether the price difference is:
1. a downstream consequence of different MILK availability timing, or
2. mainly a market-state/timing difference despite similar availability.

