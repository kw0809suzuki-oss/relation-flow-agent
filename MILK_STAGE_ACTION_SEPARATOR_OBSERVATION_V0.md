# MILK Stage Action Separator Observation v0

Date: 2026-09-28
Branch: experiment/cross-view-timeline-v0-20260928
Source: MILK Stage Action Separator fresh10 v0
Status: Observation only. No policy adoption.

## Parent question

At the exact transition that creates the first physical MILK stage difference,
does A/B submit a different HARVEST action on an already harvestable COW?

## Confirmed

### 1. All 9 cases with a compact physical MILK precursor have a direct HARVEST-action separator

There are 10 fresh10 cases.

- 9/10 have a compact physical MILK precursor before the first realized SELL MILK boundary difference.
- 1/10, seed7358, has no compact physical precursor.

For all 9 precursor cases, the immediately preceding compact-MILK-equal turn
contains a difference in harvestable-COW HARVEST action count:

- SELF_IMPROVED:
  - A more harvestable-COW HARVEST: 5
  - B more harvestable-COW HARVEST: 1
  - no compact precursor: 1

- SELF_WORSE:
  - A more harvestable-COW HARVEST: 2
  - B more harvestable-COW HARVEST: 1

Thus, in 9/9 precursor cases, the first observed MILK stage displacement is
directly associated with a different unit-action transition at a harvestable COW.

### 2. Direction of earlier/later COW HARVEST does not separate terminal improvement

Both outcome groups contain both directions.

Examples:

seed7351, SELF_IMPROVED:
- last equal D21h17
- A has a harvestable-COW HARVEST
- B does not
- first physical MILK difference D21h18
- first SELL difference D21h22

seed7353, SELF_IMPROVED:
- last equal D20h11
- B has more harvestable-COW HARVEST
- first physical difference D20h12
- first SELL difference D20h14

seed7357, SELF_WORSE:
- last equal D19h20
- B has more harvestable-COW HARVEST
- first physical difference D19h21
- first SELL difference D20h0

seed7359 / 7360, SELF_WORSE:
- A has more harvestable-COW HARVEST
- terminal self still worsens under B

Therefore:
**earlier COW HARVEST is not sufficient to classify the B terminal effect.**

### 3. The competing unit-action surface often differs broadly

At the last compact-MILK-equal turn, the other arm often uses actors for other work.

Examples:

seed7351:
- A ops: CARE 2 / HARVEST 1 / SOUTH 5
- B ops: CARE 3 / PLANT 5

seed7354:
- A: CARE 1 / COLLECT_FERTILIZER 1 / HARVEST 1 / SOUTH 4
- B: CARE 1 / HARVEST 4 / WEST 2

seed7359:
- A: CARE 2 / HARVEST 1 / WATER 4
- B: CARE 3 / EAST 4

seed7360:
- A: HARVEST 1 / NORTH 1 / SOUTH 3 / WEST 1
- B: CARE 3 / WATER 4

This is an observed action-allocation difference.
It does NOT yet prove worker contention or that crop work displaced MILK work.

### 4. Combined Battle trace now reaches this chain

For 9/10 cases:

D14 Seed-filter difference
-> later unit-action / position difference at harvestable COW
-> equal-total MILK shifts between COW and Carry/Shed stages
-> 2–4 turns later first realized SELL MILK boundary differs

Previous probes separately established:
- B changes post-D14 Plant / Harvest and terminal self.
- first MILK physical difference preserves total physical MILK in 9/9 precursor cases.
- first SELL boundary often changes realized MILK Cash / price.

This chain is chronological and externally observed.
It is not yet a causal proof that the Seed change causes the terminal result through MILK.

## View

The strongest new representation candidate is:

**Work Allocation × Return Stage**

A resource bundle is not adequately represented only by quantity.

The model may need to know:
- output still on productive asset
- output currently being carried
- output in shed / SELL-ready
- actor positions
- current competing work
- turns to Return boundary

This is a stronger statement than “track MILK price” or “harvest earlier”.

## What is not confirmed

Do not promote:
- Seed reopen causes worker contention.
- Crop work steals workers from COWs.
- COW HARVEST should be prioritized.
- Earlier MILK harvest is stronger.
- SELL delay of 2–4 turns is bad.
- MILK is the dominant mechanism of the terminal result.

## Next boundary

The next upstream question would be:

**Why did the actor/action surface differ at the last compact-MILK-equal turn?**

Possible observable candidates:
- actor positions
- number/location of active crop jobs
- number/location of harvestable COWs
- available hands
- immediate work queue implied by state

But this is a new question. The present probe stops at the first unit-action separator.
