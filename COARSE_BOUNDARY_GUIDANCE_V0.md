# Coarse Boundary Guidance v0

Working hypothesis, not a conclusion:
> Runtime mode may be better treated as persistent inside a broad State regime and reconsidered only when a coarse boundary is crossed.

Flow-chan guidance is unchanged.

Model-side proxy regimes:
- competitive -> throughput_match
- continuity -> throughput_with_slack
- endgame -> native

The regime label is a temporary operationalization for Battle testing. It is not promoted to a Rule.

Continuity boundary uses only coarse structural conditions:
- cash buffer <= max(250, 25% of reserve), or
- feed obligation gap >= max(2, cow count)

Endgame boundary:
- remaining_days <= 5

Candidate keeps its selected mode while the regime label is unchanged.

Primary evaluation:
paired Battle terminal self money and margin on fresh seeds.
Secondary observation:
mode/regime transition counts.

No automatic adoption.
