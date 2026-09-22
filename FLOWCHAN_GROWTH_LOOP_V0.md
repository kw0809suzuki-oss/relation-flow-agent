# Flow-chan Growth Loop v0

Purpose: improve Battle strength, not complete Flow-chan internals.

Loop:
1. Flow-chan gives one additional view or question.
2. Model interprets it and decides for itself.
3. Enable only one new downstream capability.
4. Run paired Battle on the fixed seed/seat frame.
5. Read only the minimum boundary:
   - current layer received / changed
   - next layer changed
   - Action changed
   - terminal self / margin
6. If Battle changes, evaluate strength.
7. If it does not reach the next layer, teach only the next missing movement.

Rules:
- Flow-chan does not select the answer.
- No scalar score or fixed weight unless independently justified later.
- Do not add multiple missing layers in one experiment.
- Do not investigate an internal difference unless it can change the next Battle decision.
- Battle is the parent objective; internal instrumentation is only a return path to Battle.
