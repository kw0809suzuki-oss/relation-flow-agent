# State Interpretation Shadow Probe v0

Purpose:
> slack=0 を修正する前に、同じStateに対してModelがslack相当の圧力を識別・比較できるかを、Battle経路から独立して観測する。

This probe does NOT ask the model to reproduce hidden reasoning.
It measures a fresh interpretation response to a saved State.

Interview input:
- saved State
- Flow-chan Guidance
- available modes: throughput_match / throughput_with_slack / native
- actual Battle choice is withheld

Interview output schema:
- perceived_pressures
- primary_pressure
- mode_fit
- preferred_mode
- evidence_from_state
- why_not_other_modes
- switch_conditions

Sampling is mechanical and thin:
- one match-selected State
- one native-selected State
- one low-liquidity State
per seed when available.

The actual Battle choice is stored separately for later comparison.
