# Scale Chassis v1

## Objective

Move terminal performance out of the v6 ~49k band toward the ~130k strong-opponent band.

Do not optimize ownership counts. Optimize recoverable operating capacity.

## Confirmed observation

The v10 ownership expansion experiment increased Land / Hands / Animals but terminal self fell from 45,683 to 10,790, with 10/10 worsening.

Therefore:

> ownership expansion != operating-body expansion

Define body size as:

> operating capacity that can still flow value into terminal

## Chassis boundary

v6 policy remains fixed.

The external chassis may only decide whether to admit one additional unit of Land / Hand / Animal.

```text
v6 policy
-> cash runway check
-> one-unit ROI check
-> optional one-step expansion
-> v6 FarmBrain operation
-> production
-> collection
-> terminal
```

No fixed target counts are allowed in v1.

## Minimal measured ROI

For each candidate expansion type, derive only from v6 observations:

```text
investment cost
-> measured operating increment
-> measured recovered value
-> payback days
```

Gate question:

> If one unit is bought now, can its measured return recover its cost before terminal while preserving cash runway?

The initial gate in `scale_chassis.py` intentionally contains no strategic forecast beyond this recoverability test.

## First experiment

1. Record v6 baseline observations needed to estimate one-unit daily return for Land / Hand / Animal.
2. Do not change v6 policy while estimating those returns.
3. Admit at most one expansion step through the ROI gate.
4. Run a fresh paired comparison.
5. Judge only at terminal first: self / margin / win.

## Decision boundary

The model is not considered successful for a few hundred points of improvement.

- movement into roughly 70k-90k: meaningful forward movement
- roughly 105k: competition-range marker (80% of 132k)

If one-step gated expansion does not move the score band, do not deepen the ROI model automatically. Re-evaluate the Scale Chassis hypothesis first.

## Observer coordinate

> Leave the microscope. Put the object on the table. Return to the observer coordinate.

Local Bundle analysis is reopened only if it changes the terminal decision.
