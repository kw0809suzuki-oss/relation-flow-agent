# MILK Return Path Boundary Observation v0

Date: 2026-09-28
Branch: experiment/cross-view-timeline-v0-20260928
Source: MILK Return Path Boundary Audit fresh10 v0
Status: Observation only. No policy adoption.

## Parent question

For the 7 cases where A/B share:
- the same current MILK market snapshot, and
- the same previous 6-turn raw MILK market history,

what exact MILK Return-path boundary first differs after the already-known
COW -> Carry physical stage divergence?

Observed downstream boundaries:
- MILK-carrying DROP action
- Shed / SELL-ready MILK
- SELL MILK request
- successful SELL MILK execution

## Primary set

7 matched cases:
- 7351
- 7352
- 7353
- 7354
- 7356
- 7357
- 7360

Terminal B-A:
- improved: 7351, 7352, 7353, 7354, 7356
- worsened: 7357, 7360

## Confirmed

### 1. SELL-ready Shed is the common first downstream Return boundary

After the first compact physical MILK divergence:

- SELL_READY_SHED differs in 7/7
- MILK_DROP_ACTION differs in 6/7
- SELL_REQUEST differs in 7/7
- EXECUTED_SELL differs in 7/7

Earliest downstream boundary:
- 6/7: MILK_DROP_ACTION + SELL_READY_SHED on the same turn
- 1/7: SELL_READY_SHED + SELL_REQUEST + EXECUTED_SELL on the same turn

Thus the only boundary present as the earliest downstream Return-path
difference in all 7 cases is:

**Carry -> Shed / SELL-ready**

### 2. Six cases pass through explicit DROP

Examples:

seed7351:
- first physical MILK difference: D21h18
- D21h21: A hand carries MILK2 and submits DROP
- D21h21: SELL-ready A2 / B0
- D21h22: A requests SELL MILK2
- D21h22: A successfully sells MILK2

seed7353:
- first physical difference: D20h12
- D20h13: B hand carries MILK3 and submits DROP
- D20h13: SELL-ready A3 / B6
- D20h14: B requests additional SELL MILK3
- D20h14: B successfully sells MILK3

seed7360:
- first physical difference: D23h18
- D23h21: A farmer carries MILK2 and submits DROP
- D23h21: SELL-ready A2 / B0
- D23h22: A requests SELL MILK2
- D23h22: A successfully sells MILK2

In these 6 cases, the explicit MILK-carrying DROP action and the SELL-ready
difference appear together.

### 3. seed7357 reaches the same boundary through the public end-of-day rule

seed7357:
- first physical difference: D19h21
- no explicit MILK DROP action difference is observed
- D20h0: SELL-ready A0 / B1
- D20h0: B requests SELL MILK1
- D20h0: B successfully sells MILK1

Public Kaggriculture rule:
at end of day, every actor inventory is automatically dropped into the Shed
(up to Shed capacity) by _drop_inventories_to_shed.

Therefore seed7357 is not a different Return boundary.
It reaches the same Carry -> Shed / SELL-ready boundary through automatic
end-of-day transfer instead of an explicit DROP action.

### 4. SELL-ready availability connects directly to SELL request and execution in all 7

For every matched case, the arm with the additional SELL-ready MILK at the
first boundary later produces the corresponding SELL request difference and
successful SELL execution difference.

Typical timing:
- 6 cases: SELL request / execution occurs one turn after the SELL-ready difference
- seed7357: SELL-ready / request / execution occur in the same D20h0 turn

This establishes the observed physical Return sequence:

COW yield
-> Carry
-> Shed / SELL-ready
-> SELL request
-> successful SELL
-> Cash

for this matched set.

## Judge

### Keep as a Return-path representation

Keep:

**SELL-ready availability is a concrete Return boundary between physical output
and executable market Return.**

The model can distinguish:
- output still on productive asset
- carried output
- sell-ready Shed output
- requested sale
- realized sale / Cash

This is externally grounded by public rules and Battle traces.

### Do NOT promote it to a strength rule

The same Return-path structure appears in both terminal directions.

Matched set:
- terminal improved under B: 5
- terminal worsened under B: 2

Also, the arm that reaches SELL-ready / SELL first is not consistently the arm
with the better terminal result.

Examples:
- seed7351: A reaches/sells MILK first, but B terminal self is +455 higher
- seed7352: A reaches/sells first, but B terminal self is +1153 higher
- seed7353: B reaches/sells additional MILK first, and B is +942 higher
- seed7357: B reaches/sells first, but B is -567 lower
- seed7360: A reaches/sells first, and B is -845 lower

Therefore:

**Return-path completion describes value movement to Cash, but does not by
itself determine Battle value.**

## Updated representation

The strongest externally supported MILK Return representation is now:

Quantity
-> productive-asset stage
-> Carry stage
-> SELL-ready Shed stage
-> SELL request
-> realized SELL
-> Cash

with:
- Actor Position / Action describing local stage movement
- public end-of-day auto-drop as an alternate Carry -> Shed transition
- Market state observed at the realized SELL boundary

No preference score is attached to these stages.

## What is closed

Do not use:
- generic Work Pressure as a terminal separator
- earlier HARVEST as a strength rule
- earlier Return-stage movement as a strength rule
- current MILK market snapshot as sufficient Value Signal
- previous 6-turn MILK market history as a hidden separator
- pre-SELL hidden MILK market divergence in the matched 7 cases

## Current frontier

The physical Return path to Cash is now substantially observed.

The next unresolved question is no longer:

> Can this value reach Cash?

For these MILK cases, the path can be described through to executed SELL.

The remaining Battle question is:

> What happens after the Cash arrives, and why does an earlier / larger local
> Return sometimes coexist with a worse terminal result?

That question should be treated separately from Return-path mechanics.

Do not infer that Cash arrival caused later productive spending without a new
Battle-grounded test.
