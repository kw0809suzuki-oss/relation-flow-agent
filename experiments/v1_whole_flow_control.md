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
