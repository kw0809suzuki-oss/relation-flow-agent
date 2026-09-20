import json
from pathlib import Path

from analyze_decision_boundaries import identical_state_choice_conflicts, transition_candidates


def cycle(choice, known):
    return {
        "observe": {"known": known, "missing": []},
        "choose": {"selected": choice},
    }


def test_identical_full_state_has_no_conflict_when_choice_matches():
    cycles = [
        cycle("maintain", ["relation.money=0.1", "movement_favorable_votes=2"]),
        cycle("maintain", ["movement_favorable_votes=2", "relation.money=0.1"]),
    ]
    assert identical_state_choice_conflicts(cycles) == []


def test_choice_change_is_observation_not_rule():
    cycles = [
        cycle("maintain", ["movement_favorable_votes=2"]),
        cycle("switch", ["movement_favorable_votes=1"]),
    ]
    result = transition_candidates(cycles)
    item = result["maintain->switch"]
    assert item["count"] == 1
    assert item["status"] == "observed_boundary_candidate"
    assert item["promote"] is False
