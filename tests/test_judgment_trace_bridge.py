from judgment_frame import BattleOutcome, Intent, can_auto_adopt, execution_consistent
from judgment_trace_bridge import cycle_from_whole_flow_event


def test_local_missing_stays_local_missing():
    cycle = cycle_from_whole_flow_event({
        "relation_axes": {"money": -0.2, "capacity": 0.1, "production": 0.0},
        "mode": "maintain",
        "gate_magnitude": 0.04,
        "axis_movements": None,
    })

    assert cycle.choose.intent is Intent.PERFORM
    assert cycle.choose.selected == "maintain"
    assert cycle.act.executed is True
    assert "relation_movement_baseline" in cycle.observe.missing
    assert cycle.learn.outcome == "local_not_observed"
    assert execution_consistent(cycle.choose, cycle.act)
    assert can_auto_adopt(cycle.learn) is False


def test_local_observation_does_not_claim_battle_effect():
    cycle = cycle_from_whole_flow_event({
        "relation_axes": {"money": 0.3, "capacity": 0.2, "production": 0.1},
        "mode": "push",
        "gate_magnitude": 0.04,
        "axis_movements": {"money": 0.1, "capacity": 0.0, "production": 0.02},
    })

    assert cycle.learn.outcome == "local_relation_movement_observed"
    assert "battle" not in cycle.learn.abstraction.lower()
    assert cycle.learn.adoption == "candidate_only"


def test_control_off_is_not_misreported_as_execution():
    cycle = cycle_from_whole_flow_event({
        "relation_axes": {"money": 0.0, "capacity": 0.0, "production": 0.0},
        "mode": "control_off",
        "gate_magnitude": 0.04,
        "axis_movements": None,
    })

    assert cycle.choose.selected is None
    assert cycle.act.executed is False


def test_battle_outcome_is_separate_and_noncausal():
    battle = BattleOutcome(
        result="margin_delta=+120",
        scope="battle_only",
        causal_attribution=False,
    )

    assert battle.scope == "battle_only"
    assert battle.causal_attribution is False
    assert battle.adoption == "candidate_only"
    assert can_auto_adopt(battle) is False
