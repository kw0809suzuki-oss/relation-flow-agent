# Coarse Transition Effect Trace v0

Observation-only step after Coarse Boundary Guidance v0.

Question:
Among seeds where coarse-boundary candidate changed terminal outcome, what mode/regime
transitions and nearby Action divergences were actually observed?

No transition is labeled causal or beneficial by construction.
No new intervention is applied.

Observed seeds:
7171, 7176, 7177, 7179, 7180.

For each seed:
- rerun current objective-pressure arm and coarse-boundary arm
- align by turn
- record candidate mode/regime transitions
- record first Action divergence and all Action divergences within ±3 turns of candidate transitions
- retain terminal deltas

Purpose:
find the smallest next Battle intervention from observed transition locations.
