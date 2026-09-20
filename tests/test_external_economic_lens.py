from external_economic_lens import candidate_space_snapshot, evaluate_economic


def test_candidate_space_keeps_all_coarse_modes():
    snap = candidate_space_snapshot()
    assert snap["candidates"] == ["push", "maintain", "stop", "switch"]
    assert snap["winner_only"] is False


def test_economic_lens_is_independent_and_nonpromoting():
    event = {
        "relation_axes": {"money": -0.4, "capacity": -0.2, "production": 0.3},
        "axis_movements": {"money": 0.1, "capacity": 0.1, "production": 0.1},
    }
    result = evaluate_economic(event)
    assert result["judgment"] == "switch"
    assert result["promote"] is False
