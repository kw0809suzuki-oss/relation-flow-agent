from analyze_boundary_aftermath import observe_aftermath


def cycle(choice, movements):
    known = []
    if movements is not None:
        known += [f"movement.{k}={v}" for k, v in movements.items()]
    return {
        "observe": {"known": known, "missing": []},
        "choose": {"selected": choice},
    }


def test_aftermath_uses_following_cycle_and_stays_noncausal():
    cycles = [
        cycle("maintain", {"money": 0.0, "capacity": 0.0, "production": 0.0}),
        cycle("switch", {"money": -0.1, "capacity": -0.1, "production": -0.1}),
        cycle("switch", {"money": 0.2, "capacity": -0.1, "production": 0.3}),
    ]

    item = observe_aftermath(cycles)["maintain->switch"]
    assert item["transition_count"] == 1
    assert item["observed_count"] == 1
    assert item["mean"]["money"] == 0.2
    assert item["causal_attribution"] is False
    assert item["promote"] is False
