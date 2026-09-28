# Strong Model Feature Candidates v0

Status: Battle-side design material only.  
This document does not adopt a policy.

Parent objective:

> Official Battleで勝てるモデルを作る。

Selection rule for this note:

- Prefer World-returned differences.
- Separate observed fact from interpretation.
- Do not promote implementation or a descriptive correlation into a Battle rule.
- Keep candidates that improve representation even before they become control rules.

---

## Candidate 01 — Durable Capital Payback State

### Observed

Saved strong replays, 4 episodes / 8 player-instances:

- every instance falls below the initial Cash 3,000,
- every instance makes its first durable return to Cash >= 3,000 at exactly Day10 h10,
- every instance remains above 3,000 after that point.

At Day10 h10 every instance has MELON SELL request(s), but exact realized Cash composition differs by player. Therefore the common fact is the durable Cash recovery boundary, not “MELON is optimal”.

Fresh10 Phase-A trajectory data:

- opponent reaches Cash >= 3,000 by Day11 or Day12 in 10/10 cases,
- self does not establish a durable >=3,000 position by Day12 in 10/10 cases,
- one self case touches >=3,000 on Day9 but falls below again,
- Day12 Cash mean: self 1,956.0 / opponent 6,755.5.

### Candidate representation

- initial_cash
- cash
- cash_recovered_vs_initial
- durable_payback_reached
- turns_since_payback
- last_below_initial_cash

### Boundary

Payback timing is not yet an optimization target.
The exact strong Replay synchronization may be specific to those episodes.

---

## Candidate 02 — Action-Class Closure / Remaining-Horizon Compatibility

### Observed

Strong replay 8 player-instances:

Last successful conversion windows:

- LAND: Day8–9
- ANIMAL: Day9–12
- SEED: Day26–27
- HIRE: Day29

After Day14:

- LAND conversions: 0 in all 8
- ANIMAL conversions: 0 in all 8
- SEED conversions: 20–54 per instance
- HIRE conversions: 30–32 per instance

After Day20:

- SEED conversions: 11–35 per instance
- HIRE conversions: 18–20 per instance

Current Body code still suppresses BUY_LAND / BUY_SEED / BUY_ANIMAL from Day14 onward.

### Late physical lineage check

Across the same 8 strong player-instances:

- crops newly activated from Day20 onward: 833
- observed later Output: 828
- HARVEST reached: 831
- Day27 plant cohort: 42 activated / 40 Output / 40 HARVEST
- Day28: only 1 activation / no Output / no HARVEST

Late crop types observed:
- WHEAT
- CARROT

No MELON / STRAWBERRY late cohort in this 4-replay sample.

### Candidate representation

Do not represent closure as a single global day.

Represent:

- remaining_turns
- conversion_class
- asset/crop physical lineage
- observed/known time-to-output
- terminal_reachability
- action_still_recoverable_before_terminal

### Interpretation only

The observed ordering is compatible with a payback-horizon interpretation:
longer structural conversions close earlier; short production inputs continue later.

This explanation is not yet a confirmed Battle rule.

---

## Candidate 03 — Return Allocation State

### Observed: fixed fresh10 Day4→8

Gross SELL Cash:
- self 5,808.7
- opponent 5,445.4

Opponent sells slightly less gross Cash.

Operating spend:
- self 4,433.4
- opponent 2,029.8

Operating share of SELL:
- self 76.3%
- opponent 37.3%

Surplus after operating:
- self 1,375.3
- opponent 3,415.6
- opponent ahead in 10/10

Productive spend:
- self 1,552
- opponent 3,364
- opponent ahead in 10/10

Actual production:
- self 17.8
- opponent 33.0
- opponent ahead in 10/10

The WHEAT lane after operating is nearly equal:
- self +439.1
- opponent +424.0

The surplus difference is almost entirely non-WHEAT realization.

### Candidate representation

Return should not be represented as SELL volume alone.

Represent a return pulse as:

- realized_sell_cash
- operating_spend
- surplus_after_operating
- productive_conversion_spend
- unallocated_cash
- return_to_conversion_delay

### Boundary

Cash is fungible.
Do not causally pair arbitrary SELL and spend without a physical/necessity witness.

---

## Candidate 04 — Maturity Ladder / Overlapping Cohorts

### Observed: fixed fresh10

Day4→8 existing cohort:
- self non-WHEAT production 16.3
- opponent 46.0
- opponent ahead 10/10

Day8 future value from the same existing cohort:
- self potential units 50
- opponent 107
- opponent ahead 10/10

New Day4→8 cohort:
- observed production by Day8: self 0 / opponent 0
- Day8 future units: self 28.4 / opponent 65.1
- opponent ahead 10/10

Return-time position of the Day8 new cohort:
- self: 4.6 assets / 28.4 future units, all first production after Day12
- opponent: 3 assets / 19 units scheduled within 2–3 days
- opponent: another 8.9 assets / 46.1 units after Day12

### Candidate representation

Replace raw productive-asset count with a time-distributed pipeline:

- ready_now
- next_return_0_1_day
- next_return_2_3_days
- next_return_later
- future_units_by_horizon
- cohort_origin_day
- open cohort count
- cohort overlap

### Interpretation only

The opponent simultaneously holds:
- a returning mature cohort,
- a near-return cohort,
- a future cohort.

This is an observed State structure, not proof that overlap itself causes the terminal result.

---

## Candidate 05 — Terminal Reachability, not Blanket Late Closure

### Observed: Day20 fixed-five cohort

Existing committed production mark:
- self 8,811.4
- opponent 55,243.6
- residual 46,432.2

Residual decomposition:
- ready residual 7,079.6
- reachable residual 39,352.6
- not-reachable residual 0

84.75% of the committed-production residual is in the reachable bucket.

Both sides:
- not-reachable mark = 0

### Candidate representation

For every productive commitment, carry:

- terminal_reachable
- remaining_time_to_output
- remaining_time_to_harvest
- remaining_time_to_return, when proven
- ready / reachable / not_reachable

### Boundary

This does not prove that every reachable asset should be built.
It rejects a representation that treats all late investment as equivalent.

---

## Candidate 06 — World Context Must Be in State

### Mechanical insufficiency result

The prior Phase-A trajectory signature used:
- unlocked changes
- productive count changes
- worker changes
- Cash-delta signs
- productive-gap sequence

Seeds 8801 and 8806 had the same trajectory signature, but different terminal-best candidate directions:

- 8801: surface_first
- 8806: hold

At Day4 and Day8, their self/opponent farm checkpoints are nearly identical in:
- Cash
- land
- productive counts
- crop composition
- animal composition

But external World state differs.

Examples:

Day4:
- STRAWBERRY price 137 vs 147
- market inventory differs
- town unlock PIZZA_SHOP vs ICE_CREAM_SHOP

Day8:
- STRAWBERRY 158 vs 172
- MILK 214 vs 221
- market inventory differs
- town unlock composition differs

### Candidate representation

A Battle state cannot be Farm-only.

Include:
- market prices
- market inventory
- town/unlocked shops
- opponent state
- remaining terminal horizon

### Boundary

The external World differences are observed candidates for the missing information.
They are not proven causes of the different best directions.

---

## Candidate 07 — Difference Durability

### Observed: Vadim vs DSM saved strong replay

Compact Difference geometry:

- equal 28 turns
- non-empty 25
- equal 76
- non-empty 3
- equal 1
- non-empty 1
- equal 1
- non-empty 585 through terminal

The first transient difference reaches:
- Carry
- Cash
- Seed
- Plant
- Yield

and then fully re-converges in the compact View.

### Candidate representation

Do not react to “difference exists” alone.

Carry:
- difference_age
- domains_reached
- reconvergence_count
- persistence
- representation_shift_history
- durable_residual_candidate

### Observation

Productive difference does not imply durable residual.

### Boundary

Compact View equality is not full hidden-state identity.

---

## Candidate 08 — Build-to-Realize Phase Shift

### Observed: fixed-five later path

Largest late observable residual growth after Day18:
- Day20→24 mean +11,940.2

During Day20→24:
- Cash residual grows strongly in all five
- cumulative realized-SELL residual grows strongly
- committed-production residual contracts strongly

Observed shape:
productive marks are being converted/unwound while Cash residual grows.

Strong raw replays also continue only short late crop lineages and then collapse plant/pipeline state near terminal.

### Candidate representation

Include:
- remaining_turns
- reachable productive value
- realized Cash
- committed-but-unrealized value
- pipeline liquidation progress
- Build / Realize as a descriptive phase label only

### Boundary

Do not use a fixed day as the phase switch without Battle evidence.

---

# What the next model should not use as a sufficient state

The following have already shown insufficiency or dangerous over-compression:

- gross SELL volume alone
- total productive asset count alone
- a single global Closure day
- Farm-only state
- one current Difference snapshot
- “productive difference exists”
- coarse trajectory signature alone
- implementation success as evidence

---

# Minimal next-model state candidate

## World
- Market prices
- Market inventory
- Town unlocks
- Opponent external state
- Remaining turns

## Capital
- Cash
- initial-Cash payback status
- realized return
- operating burden
- surplus after operating
- return-to-next-conversion delay

## Productive Pipeline
- active assets by class
- cohort origin
- maturity / next-return buckets
- terminal reachability
- ready / reachable / not-reachable
- open cohort / cycle count

## Difference / Residual
- current Difference
- age / persistence
- reconvergence history
- representation-shift history

## Output

Do not make v0 output “the winning action”.

First output:
- current Battle state in the above representation
- available productive conversions
- conversions whose return is still reachable
- observed pressure / missing capacity
- candidate action set

Then Battle decides whether this representation contains useful winning information.

---

# Current strongest implementation mismatch to test

Current Body:
- global Day14 suppression includes BUY_SEED

Strong replay observation:
- no late LAND/ANIMAL after Day14,
- substantial SEED/HIRE continues,
- Day20–27 new crops overwhelmingly reach Output/HARVEST before terminal.

Therefore the smallest high-information Battle candidate is not:
“remove D14”.

It is:

> keep structural-capital closure, but restore only terminal-reachable short-cycle productive input under explicit reachability conditions.

This remains a Candidate until Battle.
