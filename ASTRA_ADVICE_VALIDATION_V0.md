# Astra Advice Validation v0

Date: 2026-09-28
Branch: experiment/cross-view-timeline-v0-20260928
Status: evidence review only; no policy adoption

## Parent objective

Official Battleで勝てるモデルを作る。

This review checks the Astra-app advice against existing Battle evidence and public Kaggriculture rules.

## Executive result

The advice is directionally strong, but two boundaries must be tightened before implementation:

1. terminal_reachable currently means reachability to the public Output/Harvest boundary, not Cash Return.
2. durable payback is retrospective and cannot be used directly as a live decision feature without future leakage.

Therefore the next model may safely move from “what assets exist” toward “where current resources sit in a return flow under the remaining horizon,” but v0 should remain conservative about Cash-return prediction.

# 1. Capital State

Astra proposal: Cash, payback status, cumulative Return, maintenance cost / operating burden, net surplus, and separation of recovered capital from still-operating capital.

## Supported

Existing evidence supports carrying current Cash, initial Cash, cumulative realized market Cash events when exact logger is available, realized operating spend, surplus after observed operating spend, and historical payback touches.

Strong replay observation:
- 8 saved strong player-instances all fall below initial Cash 3,000
- all first establish a durable >=3,000 path at Day10 h10

Fresh10 Phase-A:
- opponent reaches >=3,000 by Day11 or Day12 in 10/10
- self has no durable >=3,000 path by Day12 in 10/10
- one self case touches >=3,000 and falls below again

## Correction

durable_payback_reached is a retrospective Judge because durability requires future observations.

Live-safe fields:
- cash_now
- cash_above_initial_now
- ever_touched_initial_cash_again
- first_recovery_timestamp_if_past
- turns_since_first_recovery
- cumulative_realized_sell_cash
- cumulative_productive_spend
- recent_operating_spend

Retrospective-only:
- durable_payback_timestamp
- remained_above_initial_after_timestamp

## Not yet supported

A generic future maintenance cost is not yet a single externally confirmed quantity. Use observed operating spend or explicitly public-rule unavoidable costs only.

# 2. Return Pipeline

Astra proposal: bucket resources by distance to Return and carry expected Return / maintenance.

## Strongly supported at Output boundary

Existing observers already decompose assets into READY / REACHABLE / NOT_REACHABLE.

Day20 fixed-five:
- committed residual opponent minus self: 46,432.2
- ready residual: 7,079.6
- reachable residual: 39,352.6
- not-reachable residual: 0
- reachable share: 84.75%

The implementation explicitly states: REACHABLE = public Asset -> Output/Harvest boundary reachable by terminal under stated survival / WATER / FEED / timely-harvest assumptions. It is NOT Cash-return reachability.

## Public rules confirm crop-specific horizons

Official Kaggriculture source at commit b2405492c8403f6649f9317290f215e0290a2425:
- WHEAT: first_yield_day 2, max_yield_day 4
- CARROT: first_yield_day 2, max_yield_day 3
- TOMATO: first_yield_day 8
- STRAWBERRY: first_yield_day 10
- MELON: first_yield_day 10, max_yield_day 12
- GOOSE: first_yield_day 4
- SHEEP: first_yield_day 6
- COW: first_yield_day 8

This supports a horizon-aware representation.

## Correction

Do not call this expected Return in v0.

Use:
- output_reachable_under_public_rules
- first_output_distance
- max_yield_distance
- current_output_units
- current_price_mark (valuation only)
- ready / reachable / not_reachable

Cash Return requires additional Harvest -> Carry -> DROP -> SELL lineage.

# 3. Conversion State

Astra proposal: LAND / ANIMAL / SEED / HIRE should not be treated as one class.

## Supported

Saved strong replay 8 player-instances show different successful-conversion stopping windows:
- LAND: last around Day8–9
- ANIMAL: last around Day9–12
- SEED: continues to Day26–27
- HIRE: continues to Day29

After Day14:
- LAND: 0 observed successful conversions
- ANIMAL: 0
- SEED: substantial continued activity
- HIRE: substantial continued activity

Current Body still applies one global D14 suppression to BUY_LAND / BUY_SEED / BUY_ANIMAL / BUY_PRODUCT COW.

## Strong late-crop observation

Across the saved strong replays:
- 833 crops activated from Day20 onward
- 828 later formed Output
- 831 reached Harvest
- Day27 cohort: 42 activated / 40 Output / 40 Harvest
- Day28: 1 activation / no later Output

Observed late crop types in the sample: WHEAT and CARROT.

## Safe candidate

Not: late Seed returns Cash before terminal.

Safe current wording: late short-cycle Seed can still reach Output/Harvest before terminal.

The Cash leg remains a separate lineage question.

# 4. World Context

Astra proposal: Market / Market inventory / Town / Opponent context must be input.

## What is mechanically closed

The prior coarse Phase-A trajectory signature is insufficient.

Seeds 8801 and 8806:
- same tested trajectory signature
- different terminal-best candidate direction

Their Day4 / Day8 farm-side checkpoints are nearly identical in Cash, land, productive count, crop composition, and animal composition.

Observed external differences include market prices, market inventory, and town unlocks.

Example Day4:
- STRAWBERRY price 137 vs 147
- inventory differs
- PIZZA_SHOP vs ICE_CREAM_SHOP context

Example Day8:
- STRAWBERRY 158 vs 172
- MILK 214 vs 221
- inventory differs
- town composition differs

## Correct Judge

Closed: the tested Farm/trajectory representation is insufficient.

Not closed:
- Market caused the different terminal-best direction
- Town caused it
- any single external field is necessary or sufficient

Therefore v0 should include World context as candidate information, then test whether it resolves previously contradictory cases.

Opponent context is live-safe if taken from current/past observations. Future/durable opponent payback is not live-safe.

# 5. Difference Durability

Astra proposal: represent difference by persistence, not only current magnitude.

## Supported

Vadim vs DSM compact Cross-View geometry includes transient difference, full re-convergence, short flicker, and a long non-empty run through terminal.

The first transient difference reaches Carry -> Cash -> Seed -> Plant -> Yield and then the compact Difference View returns to empty.

Direct observation: Productive difference does not imply durable residual.

## Safe live fields

- current_difference
- difference_age
- domains_seen_since_difference_open
- previous_reconvergence_count
- representation_shift_history_so_far

Retrospective-only:
- this difference survives to terminal
- final durable residual classification

# 6. Does the proposed feature set already explain terminal?

No.

Current evidence shows strong discrimination, not yet explanation.

### Payback
Strong/current timing differs strongly in existing samples.

### Operating burden
Day4->8 fixed10:
- self gross SELL 5,808.7
- opponent 5,445.4
- self operating spend 4,433.4
- opponent 2,029.8
- self operating share 76.3%
- opponent 37.3%
- opponent surplus, productive spend, and actual production are ahead in 10/10

This separates the paths but does not establish causal sufficiency.

### Terminal reachability
Day20 fixed-five shows a large reachable committed-production residual. The five-case pattern is suggestive but is not an independent predictive test.

Judge: useful discriminator candidate, not yet terminal explanation.

# 7. Correction to the proposed four-way Battle comparison

Astra suggested roughly: current D14 / full Closure / short-cycle reopen / Return-maximization.

This mixes multiple mechanisms too early.

A cleaner first isolation is:

A. Current D14
- existing adopted body

B. Seed Reopen — unconditioned observation arm
- preserve LAND/ANIMAL D14 closure
- restore suppressed BUY_SEED orders only
- used as an ablation, not a candidate for adoption

C. Seed Reopen — Output-reachable gated
- preserve LAND/ANIMAL closure
- restore only BUY_SEED orders whose crop can reach the public Output boundary before terminal under public-rule horizon logic

Compare A / B / C on identical seeds and seats.

Why:
- B tests whether Seed suppression itself matters
- C tests whether the horizon filter adds value beyond simple Seed reopening
- LAND / ANIMAL remain unchanged, so the causal surface is narrower

Do not add a broad Return-maximization arm yet. It changes too many decisions and would make attribution weak.

# 8. Critical implementation boundary for arm C

Do not use a fixed rule such as WHEAT/CARROT are always allowed after Day14.

Use public-rule horizon calculation from current timestamp.

For v0, the claim can only be: crop can reach Output boundary before terminal under explicit public-rule timing assumptions.

Do not label it Cash recoverable, profitable, or terminal-positive until Harvest / transport / SELL / Cash evidence is closed.

# 9. Next-model State v0

Split live State from retrospective Judge.

## Live World
- current market prices
- current market inventory
- current town unlocks
- opponent current external state
- remaining turns

## Live Capital
- cash
- initial_cash
- current above/below initial
- past first recovery timestamp
- cumulative realized SELL Cash
- recent operating spend
- surplus after observed operating spend

## Live Pipeline
For each physical asset/cohort:
- asset class
- origin day
- quantity / yield
- first-output distance
- max-yield distance
- output reachable by terminal
- current-price mark (valuation only)

## Live Conversion candidates
For each requested conversion:
- class: LAND / ANIMAL / SEED / HIRE
- cost
- public-rule output horizon where definable
- output-reachable flag where definable
- remaining turns

## Live Difference history
- current compact difference
- age
- domains reached
- past re-convergence count
- representation-shift history

## Retrospective Judge
- durable payback boundary
- terminal residual
- cycle closure to Cash
- terminal result
- feature-to-terminal correspondence

# Final validation

## Adopt as representation direction
- World context available to the model
- horizon-aware productive pipeline
- conversion classes separated
- past Difference durability/history
- capital-return history rather than Cash alone

## Keep as candidate, not fact
- payback timing as control target
- overlap as strength
- Market/Town as causal variables
- operating burden as causal driver

## Correct before implementation
- terminal reachable -> currently Output/Harvest reachable, not Cash-return reachable
- durable payback -> retrospective Judge, not live input
- expected Return -> current-price valuation / rule-derived horizon until predictive evidence exists
- four-arm broad comparison -> first use narrow A/B/C Seed isolation
