# Phase A Instruction Variants v0

Purpose:
Test whether instruction structure changes the model's ability to choose the
growth direction that later yields the highest terminal self.

All variants receive the same blind WR-02 World State at Day4 and Day8.
Available normalized outputs:
- HOLD
- SURFACE
- THROUGHPUT
- ENGINE

The later four-arm Battle result is sealed until predictions are committed.

## V0 — Direction Picker (control)

Objective: raise terminal self.

Read the current observable World State and choose one growth direction:
HOLD, SURFACE, THROUGHPUT, or ENGINE.

Choose the direction that best fits the strongest current constraint.
Do not use future information.

Output:
- choice
- observable evidence
- confidence

## V1 — Growth Continuation

Objective: raise terminal self.

During Phase A, do not optimize a component in isolation. Keep growth connected.

Read the current observable World State and decide what the returned value
should become next so that a new productive state is established and can create
the next Return.

Do not begin by choosing LAND, workers, or production commitment as a category.
First decide what conversion would keep the growth chain moving. Then normalize
the first required growth emphasis to one of:
HOLD, SURFACE, THROUGHPUT, ENGINE.

Output:
- choice
- next_growth_conversion
- observable evidence
- expected next productive state
- confidence

## V2 — Completion Contract

Objective: raise terminal self.

A purchase or investment is not growth by itself. Count growth only when the
investment can become an observable productive state that is capable of
producing the next Return.

From the current observable World State:
1. identify the next productive state worth completing;
2. choose the growth direction that can complete that state with the fewest
   missing links;
3. state the observable completion condition;
4. if no direction has a credible completion path now, choose HOLD.

Normalize the choice to:
HOLD, SURFACE, THROUGHPUT, ENGINE.

Output:
- choice
- target_productive_state
- missing_links
- completion_condition
- confidence

## V3 — World Gap Bridge

Objective: raise terminal self.

Use the World as the reference plane. Compare self and opponent at the same
observable State.

Identify the next growth conversion that the opponent has already established,
or is positioned to establish, while self has not. Do not copy the opponent's
specific crop, product, or action merely because it appears in the trace.
Reproduce the missing function: connect current value to the next productive
state.

Choose the minimum growth direction needed to close that World-side connection,
then normalize it to:
HOLD, SURFACE, THROUGHPUT, ENGINE.

Output:
- choice
- observed_world_gap
- missing_conversion
- observable evidence
- confidence

## Evaluation

For fresh seeds 8701–8710:
1. capture WR-02 Day4 / Day8 World State only;
2. commit all four instruction predictions before candidate Battles;
3. run HOLD / Surface / Throughput / Engine on the same seed/seat;
4. label the terminal-self winner;
5. compare exact-choice accuracy and terminal regret.

Terminal regret for an instruction on each case:
best terminal self among four arms - terminal self of the predicted arm.

This is an instruction-screening experiment, not an adoption gate.
