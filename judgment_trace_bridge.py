"""Trace-only bridge from Relation Flow battle events into judgment_frame.

Per-event cycles carry only local observation. Battle terminal outcomes belong
at battle scope and must not be copied into every local Learn record.
"""

from typing import Mapping, Sequence

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
    candidate_modes: Sequence[str] = ("push", "maintain", "stop", "switch"),
) -> JudgmentCycle:
    """Translate one controller event without attributing battle outcome to it."""
    mode = event.get("mode")
    controlled = mode not in (None, "control_off")
    movements = event.get("axis_movements")

    missing = []
    if movements is None:
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

    if movements is None:
        learn = Learn(
            outcome="local_not_observed",
            abstraction="local relation movement remains unavailable",
            return_signal="preserve local uncertainty; do not infer battle effect",
        )
    else:
        learn = Learn(
            outcome="local_relation_movement_observed",
            abstraction="relation movement observed for this event only",
            return_signal="return local observation without terminal attribution",
        )

    return JudgmentCycle(
        observe=observe,
        frame=frame,
        choose=choose,
        act=act,
        learn=learn,
    )


def cycles_from_trace(trace: Mapping) -> tuple[JudgmentCycle, ...]:
    """Translate all whole-flow events in an existing trace."""
    events = trace.get("whole_flow") or ()
    return tuple(cycle_from_whole_flow_event(event) for event in events)
