# Flow-chan Abstraction Transmission → Model Candidate v0

Purpose: return to the main line.

Flow-chan does not implement Evaluation, Comparison, Selection, Direction, or Action.
It transmits one abstraction to the model:

> Preserve future choice when commitment is becoming specific and hard to redirect.

The model is responsible for interpreting that abstraction.
For this experiment, the model generated one candidate interpretation:

> Do not convert liquid cash into more crop-specific seed inventory than can be
> turned into production through the currently available near-term planting surface.

This generated interpretation is a hypothesis, not evidence and not a Flow-chan rule.

A/B boundary:
- Control: the same Flow-chan abstraction exists in context, but is not transmitted into the model body.
- Treatment: the abstraction packet is transmitted into the model body.
- All manually implemented Candidate Evaluation / Comparison / Selection /
  Direction machinery is disabled in both arms.

Readout:
1. abstraction received by model?
2. Action changed?
3. terminal self / margin changed?

If Action changes, stop studying the transmission internals and evaluate Battle.
If terminal improves, keep the candidate as evidence for this model interpretation,
not as proof of the abstraction in general.
If terminal worsens, reject this interpretation without rejecting the abstraction itself.
