#!/usr/bin/env python3
"""Run one real Kaggriculture comparison and project it through Judgment Frame."""

import json
from pathlib import Path

from judgment_trace_bridge import cycles_from_trace
from run_whole_flow_control_v2 import play


SEED = 3202
SEAT = 0


def serialize_cycle(cycle):
    return {
        "observe": {
            "known": list(cycle.observe.known),
            "missing": list(cycle.observe.missing),
        },
        "frame": {
            "question": cycle.frame.question,
            "directions": list(cycle.frame.directions),
            "candidates": list(cycle.frame.candidates),
        },
        "choose": {
            "intent": cycle.choose.intent.value,
            "selected": cycle.choose.selected,
            "reason": cycle.choose.reason,
        },
        "act": {
            "selected": cycle.act.selected,
            "executed": cycle.act.executed,
            "note": cycle.act.note,
        },
        "learn": {
            "outcome": cycle.learn.outcome,
            "abstraction": cycle.learn.abstraction,
            "return_signal": cycle.learn.return_signal,
            "adoption": cycle.learn.adoption,
        },
    }


def main():
    baseline = play(SEED, SEAT, False)
    candidate = play(SEED, SEAT, True)
    margin_delta = candidate["score"]["margin"] - baseline["score"]["margin"]
    terminal = f"margin_delta={margin_delta:+.0f}"

    trace = {"whole_flow": candidate["flow_trace"]}
    cycles = cycles_from_trace(trace, terminal_outcome=terminal)

    result = {
        "schema": "kaggriculture.judgment-frame-probe.v1",
        "seed": SEED,
        "seat": SEAT,
        "baseline_score": baseline["score"],
        "candidate_score": candidate["score"],
        "terminal_margin_delta": margin_delta,
        "judgment_cycle_count": len(cycles),
        "principle_checks": {
            "choice_execution_separated": all(
                (not c.act.executed) or (c.choose.selected == c.act.selected)
                for c in cycles
            ),
            "experience_auto_adopted": any(c.learn.adoption != "candidate_only" for c in cycles),
        },
        "cycles": [serialize_cycle(c) for c in cycles],
    }
    Path("judgment_probe_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "terminal_margin_delta": margin_delta,
        "judgment_cycle_count": len(cycles),
        "principle_checks": result["principle_checks"],
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
