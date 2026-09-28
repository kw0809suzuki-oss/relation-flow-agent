# Cross-View Timeline v0 — Implementation Plan

## Objective

Build one observation-only representation that can place a full Kaggriculture replay on a common 30-day / 720-turn coordinate system.

The implementation must preserve the project boundary:

Battle = Evidence.
View = an interpretation-oriented projection.
Judge = a judgment on that View.

v0 must not promote a hypothesis into a Battle fact.

## Parent question

30日間ずっと、投入した資源をCashへ戻す運転を続けたら、本当に稼げるのか。

The first implementation does not answer this question.
It only produces a reusable external observation surface for later comparisons.

## Existing components to reuse

The repository already contains separate observers for:

- State transition / growth:
  - run_state_transition_growth_audit_v0.py
- Difference propagation:
  - difference_propagation_observer_v0.py
- Return-required seed lineage:
  - run_return_melon_lineage_v0.py
- Generated-return LAND lineage:
  - run_generated_return_land_production_lineage_v0.py
- Exact market Cash logging and return-input bridges:
  - run_sb01_exact_cash_flow_v0.py
  - run_first_return_enabled_productive_input_v0.py
  - run_first_generated_return_input_bridge_v0.py

Cross-View Timeline v0 is a thin joining layer. It does not replace these observers.

## v0 architecture

Raw Replay
→ normalized turn coordinate
→ State summary
→ Transition delta
→ direct physical witnesses
→ Difference View

Later overlays:

existing conservative Lineage
→ Cycle Open / Conversion / Output / Return / Close overlay

Then:

Cycle boundary × Difference View
→ Cross-View Observation

## Phase A — Raw 720-turn Timeline

Input:
- official replay JSON

For every step:
- step_index
- day
- hour
- player0 state summary
- player1 state summary
- stored action
- before → after transition delta

State summary:
- Cash
- hands
- unlocked land
- plant count / composition
- animal count / composition
- seed stock
- unplaced animal stock
- shed products
- carried products
- current yield
- physical crop/animal lineage keys

Physical lineage keys:
- crop:<crop>:<x>,<y>:d<planted_day>
- animal:<animal>:<x>,<y>:d<placed_day>

## Phase B — Direct witness extraction

v0 may emit only events directly supported by action + state change.

Allowed examples:
- BUY_LAND request + land count increase
  → productive_conversion / LAND
- HIRE request + hands increase
  → productive_conversion / HIRE
- BUY_ANIMAL request + animal state increase
  → productive_conversion / ANIMAL
- BUY_SEED request + net seed stock increase
  → productive_conversion / SEED
  Boundary: same-turn PLANT can hide a successful purchase.
- new crop/animal tile
  → productive_state_activated
- same physical tile yield increases
  → output_formed
- HARVEST request + same tile output decreases/disappears
  → harvest_boundary

Not allowed in v0:
- SELL request = executed sale
- Cash delta = a particular SELL amount
- nearby event = causal lineage
- Cycle ID inferred from temporal proximity

## Phase C — Difference View

At each timestamp, compare the two players on the same normalized fields.

Orientation is always explicit:
player1_minus_player0

Output:
- scalar deltas
- composition deltas
- view_difference_empty

Important boundary:
view_difference_empty means equality only in this compact observation View.
It is not a declaration of full State Re-convergence.

## Phase D — Conservative Lineage Overlay

Do not reconstruct every Cycle from scratch.

Reuse already-proven lineage observers where possible:
- Return Cash → MELON seed → exact tile → production
- Generated Return → LAND → newly unlocked coordinates → plant → production
- future exact Animal lineage observer

Overlay records contain:
- cycle_id
- player
- open timestamp
- conversion timestamp
- physical lineage keys
- output timestamps
- close timestamp if directly proven
- evidence source
- unresolved boundary

## Phase E — Cross-View Observation

Only after a conservative Cycle overlay exists:

At Cycle Open / Conversion / Output / Close timestamps,
attach the Difference View from the same timestamp.

Examples of allowed output:
- Cycle Close observed; Difference View remains non-empty.
- Cycle Open occurred while another proven Cycle remained open.
- Return boundary composition differs across players.

Do not turn these observations into a strength claim.

## Phase F — Strong vs Current comparison

Run the exact same extractor on:
1. strong replay(s)
2. Current Body replay(s)

Compare only externally measured series:
- proven open cycle count
- proven overlap duration
- return-to-next-conversion delay
- Cycle boundary Difference snapshots
- terminal self / margin

Do not assume “more is better”.
World comparison decides whether a metric matters.

## Acceptance for v0

1. Parses a 720-step official replay without policy mutation.
2. Uses action-at-step-s as the witness for observation s-1 → s.
3. Produces stable physical lineage keys.
4. Never labels a SELL request as execution by itself.
5. Does not emit causal or strength claims.
6. Same code runs on strong and Current replays.
7. Unit tests cover:
   - LAND conversion witness
   - ANIMAL conversion witness
   - SELL request non-promotion
   - explicit Difference orientation

## First implementation boundary

Implement only Phase A–C now.

Phase D–F remain next work.
