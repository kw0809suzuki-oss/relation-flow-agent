"""Trace-only bridge from Relation Flow battle events into judgment_frame.

This module does not change agent actions. It translates an already observed
whole-flow event into the compressed five-organ judgment vocabulary so the
mainline can inspect judgment separately from execution.
"""

from typing import Mapping, Optional, Sequence

from judgment_frame import (
    Act,
    Choose,
    Frame,
    Intent,
    JudgmentCycle,
    Learn,
    Observe,
)


def _known_from_event(event: Mapping) -> tuple[str, ...]:
    axes = event.get("relation_axes") or {}
    known = [f"relation.{name}={float(value):.6f}" for name, value in sorted(axes.items())]
    if event.get("mode") is not None:
        known.append(f"mode={event['mode']}")
    if event.get("gate_magnitude") is not None:
        known.append(f"gate_magnitude={event['gate_magnitude']}")
    return tuple(known)


def cycle_from_whole_flow_event(
    event: Mapping,
    *,
    terminal_outcome: Optional[str] = None,
    candidate_modes: Sequence[str] = ("push", "maintain", "stop", "switch"),
) -> JudgmentCycle:
    """Translate one controller event without claiming that its choice was good."""
    mode = event.get("mode")
    controlled = mode not in (None, "control_off")

    missing = []
    if terminal_outcome is None:
        missing.append("terminal_outcome")
    if event.get("axis_movements") is None:
        missing.append("relation_movement_baseline")

    observe = Observe(
        known=_known_from_event(event),
        missing=tuple(missing),
    )

    frame = Frame(
        question="which coarse relation-flow direction is worth applying now?",
        directions=("relation_flow_mode",),
        candidates=tuple(candidate_modes),
    )

    choose = Choose(
        intent=Intent.PERFORM,
        selected=mode if controlled else None,
        reason=(
            "existing_controller_mode_selection; judgment_record_only"
            if controlled
            else "control_disabled_or_mode_unavailable"
        ),
    )

    act = Act(
        selected=mode if controlled else None,
        executed=controlled,
        note="gate magnitude was applied by existing controller" if controlled else "no judgment-controlled execution",
    )

    if terminal_outcome is None:
        learn = Learn(
            outcome="not_observed",
            abstraction="terminal effect remains unknown",
            return_signal="preserve uncertainty; do not promote controller mode",
        )
    else:
        learn = Learn(
            outcome=terminal_outcome,
            abstraction="terminal outcome observed for this battle context only",
            return_signal="return as bounded experience; re-evaluate on re-entry",
        )

    return JudgmentCycle(
        observe=observe,
        frame=frame,
        choose=choose,
        act=act,
        learn=learn,
    )


def cycles_from_trace(trace: Mapping, *, terminal_outcome: Optional[str] = None) -> tuple[JudgmentCycle, ...]:
    """Translate all whole-flow events in an existing trace."""
    events = trace.get("whole_flow") or ()
    return tuple(
        cycle_from_whole_flow_event(event, terminal_outcome=terminal_outcome)
        for event in events
    )
