# V1 Whole Relation Flow Control — CUT

## Question

Can a live whole-match Relation Flow controller improve terminal score while preserving the existing Native Origin direction and action candidates?

## Runtime boundary

```text
live match observation
→ Relation (money / capacity / public production)
→ one-day Flow movement
→ maintain / push / stop / switch
→ gate magnitude only
→ existing agent action
→ terminal evaluation
```

The controller does **not** receive seed, paired difference, terminal reward, or future state at runtime.

## 12-case result

| Metric | Result |
|---|---:|
| mean margin delta | -944.67 |
| wins | 0/12 → 0/12 |
| improved / worsened / equal | 4 / 2 / 6 |
| action-difference cases | 6/12 |
| total action differences | 2,233 |
| largest improvement | +3,854 |
| largest worsening | -17,149 |

These values were checked against the successful V1 Run artifact from the private research repository.

## Consistency note

V1 describes its Flow horizon as `24 agent observations`. The implementation uses `deque(maxlen=DAY_CALLS + 1)` and reads `history[0]`; after warmup this produces an effective comparison distance of 25 observations. The recorded V1 result belongs to that implementation and is therefore retained unchanged rather than silently corrected after the fact.

A true 24-observation horizon, if tested, must be treated as a new experiment rather than a reinterpretation of V1.

## Observation

The action path exists:

```text
whole-match Flow recognition
→ gate magnitude change
→ action change
→ terminal change
```

But V1 Relation representation × V1 action mapping did not improve score.

## Decision

**CUT V1 mapping.**

- no production adoption
- no local-cause excavation
- preserve the whole-Flow-control design
- redesign Relation Flow representation / mapping only if it can change the next score-improvement decision
