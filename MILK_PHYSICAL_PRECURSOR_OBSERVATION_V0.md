# MILK Physical Precursor Observation v0

Date: 2026-09-28
Branch: experiment/cross-view-timeline-v0-20260928
Source: MILK Physical Precursor Audit fresh10 v0
Status: Observation only. No policy adoption.

## Parent question

After D14 Seed reopen changes the first realized MILK Return boundary, does the
difference begin in MILK quantity, physical pipeline position, or market-only
timing?

## Confirmed

### 1. A physical MILK precursor exists before the first realized SELL difference in 9/10 cases

Fresh10:
- 9 cases: a compact physical MILK State difference appears before the first realized SELL MILK boundary difference
- 1 case, seed7358: no compact physical MILK difference appears before that SELL boundary

The physical View includes:
- COW count / COW yield
- carried MILK
- shed MILK
- total physical MILK

### 2. In all 9 precursor cases, total physical MILK is exactly equal at the first difference

9/9:
- A physical_milk_total == B physical_milk_total

The first difference is a representation / pipeline-stage shift, not a quantity difference.

Examples:

seed7351:
- A: COW yield 0 / Carry 2 / Shed 0
- B: COW yield 2 / Carry 0 / Shed 0
- total = 2 vs 2

seed7353:
- A: COW yield 8 / Carry 3 / Shed 0
- B: COW yield 5 / Carry 6 / Shed 0
- total = 11 vs 11

seed7357:
- A: COW yield 1 / Carry 0 / Shed 0
- B: COW yield 0 / Carry 1 / Shed 0
- total = 1 vs 1

### 3. The physical stage shift appears shortly before the SELL boundary difference

For the 9 precursor cases, first physical difference -> first realized SELL difference:

- 7351: 4 turns
- 7352: 4
- 7353: 2
- 7354: 3
- 7355: 4
- 7356: 2
- 7357: 3
- 7359: 4
- 7360: 4

Observed range: 2–4 turns.

This is chronology only, not proof of causality.

### 4. First realized SELL boundary classifications

Across 10 cases:

- SELL-ready shed availability differs: 8/10
- equal SELL-ready stock but SELL timing/request differs: 1/10
- equal compact physical MILK state; market/price differs: 1/10

Improved group:
- SELL-ready availability differs: 5
- SELL timing/request differs with equal ready stock: 1
- market/price differs with equal physical state: 1

Worsened group:
- SELL-ready availability differs: 3/3

Therefore SELL-ready availability difference is common, but it does not
separate improved from worsened outcomes by itself.

### 5. seed7358 is a useful counterexample

seed7358:
- terminal self improves by +3215
- first realized MILK SELL boundary differs at D22 h0
- no compact physical MILK difference is observed before that boundary
- boundary classification: PRICE_MARKET_STATE_DIFFERS_WITH_EQUAL_READY_STOCK

This proves that a Return-boundary value difference can appear even when the
tracked physical MILK pipeline is equal up to that point.

## View

The smallest supported representation is not:

MILK amount -> Cash

It is:

MILK amount
+ pipeline stage
+ Return boundary World state
-> realized Cash

The same physical quantity can occupy different stages:

COW yield -> Carry -> Shed / SELL-ready -> SELL

and those stage positions can change which market state the output encounters.

## What is not confirmed

Do not promote:
- later MILK stage is always better
- earlier harvest is always better
- Seed reopen causes worker contention
- stage delay causes lower/higher price
- a 2–4 turn shift is an optimal or causal threshold

Improved and worsened cases both contain similar stage displacement patterns.

## Consequence for next-model representation

This strengthens a candidate State field:

**Return-stage position**

For an existing output bundle, preserve separately:
- still on productive asset
- harvested / carried
- shed / SELL-ready
- realized / sold
- turns since stage entry

This is more informative than total output quantity alone.

## Next Probe

At the exact transition that creates the first physical MILK difference,
compare A/B unit actions.

Question:

**Did the first stage displacement come from a different HARVEST choice on an
otherwise equal MILK physical state?**

Observe:
- last equal timestamp
- actor positions
- actor inventories
- unit action submitted
- whether actor stood on a COW with yield > 0
- A/B action multiset

Stop at the first action/state separator.
