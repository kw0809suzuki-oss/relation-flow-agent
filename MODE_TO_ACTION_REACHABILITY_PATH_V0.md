# Mode to Action Reachability Path v0

Observation-only step.

Confirmed from the previous Battle:
- first_continuity_slack_once triggered once in 10/10 cases
- Action changed turns = 0
- terminal diff = 0

Interpretive boundary:
the first continuity/slack entry is treated only as the first observed flow divergence marker.
It is not promoted as the source of value.

Question:
In the coarse candidate, after current vs coarse mode first diverges, what actually happens
turn by turn until the first Action divergence?

Observe the shortest path:
mode divergence
-> intermediate same-Action turns
-> first Action divergence
-> immediate downstream State change marker

No intervention is applied.
No distance, transition, or field is labeled causal.

Seeds:
7171, 7176, 7177, 7179, 7180
These are reused because coarse vs current produced terminal differences there.
