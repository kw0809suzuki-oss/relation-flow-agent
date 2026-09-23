# Crop Maintenance Protection v0

From:
Crop Demand Execution Gap v0.

Change:
On day 5-12 only, when the Strong Origin base action requests WATER / PLANT /
HARVEST for a unit slot and livestock overlay changes that slot, restore the exact
base action for that slot.

Fixed:
- COW targets
- HIRE behavior
- market behavior
- all other livestock routing
- objective_pressure_guidance
- opponent and battle rules

Working Hypothesis:
Livestock overlay contributes to the capacity plateau by starving crop maintenance
execution. Protecting only already-requested crop work should preserve crop surface
without removing livestock.

Expected Evidence:
Keep only if the intervention reaches the intended slots and produces a coherent
chain:
crop surface up -> production tiles up -> day12 money up -> terminal self up at a
scale meaningful relative to the ~100k residual.

Primary evaluation:
- baseline absolute mean self
- candidate absolute mean self
- delta
- opponent residual
- day12 crop tiles / production tiles / money

Boundary:
If crop retention improves but terminal remains near-neutral, maintenance starvation
is real but not the main source of the terminal gap.
