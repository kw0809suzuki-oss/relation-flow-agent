"""Origin-side integration of native decision state and Role context.

Role never chooses direction.
The native Origin state supplies direction; Role context only modulates
how strongly Origin commits to its own already-observed direction.
"""

import os
import model_candidate_evaluator_v0
import model_candidate_comparator_v0


def _clip01(x):
    return max(0.0, min(1.0, float(x)))


def integrate(origin_internal, role_reading):
    internal = dict(origin_internal or {})
    reading = dict(role_reading or {})

    distortion = _clip01(internal.get("distortion", 0.0) or 0.0)
    counter_weight = _clip01(internal.get("counter_weight", 0.0) or 0.0)
    opportunity = _clip01(internal.get("counter_opportunity", 0.0) or 0.0)

    scores = dict(internal.get("scores", {}) or {})
    score_values = sorted((float(v) for v in scores.values()), reverse=True)
    if len(score_values) >= 2:
        score_separation = _clip01(max(0.0, score_values[0] - score_values[1]) / 1.5)
    else:
        score_separation = 0.0

    native_strength = _clip01(
        0.30 * distortion
        + 0.30 * counter_weight
        + 0.20 * opportunity
        + 0.20 * score_separation
    )

    familiarity = _clip01(reading.get("familiarity", 0.0) or 0.0)
    ambiguity = _clip01(reading.get("ambiguity", 0.0) or 0.0)
    role_present = bool(reading.get("role_present", False))
    field_context_present = bool(reading.get("field_context_present", False))
    field_description = dict(reading.get("field_description", {}) or {})
    outer_meaning = dict(field_description.get("outer_meaning", {}) or {})
    outer_phase = str(outer_meaning.get("phase", "") or "").upper()
    outer_meaning_present = bool(outer_meaning)
    evaluation_lens = reading.get("evaluation_lens")
    candidate_evaluation = None
    if os.getenv("ORIGIN_MODEL_CANDIDATE_EVALUATION", "0") == "1":
        candidate_evaluation = model_candidate_evaluator_v0.evaluate(
            evaluation_lens,
            internal,
            field_description,
        )
    candidate_comparison = None
    if os.getenv("ORIGIN_MODEL_CANDIDATE_COMPARISON", "0") == "1":
        candidate_comparison = model_candidate_comparator_v0.compare(candidate_evaluation)
    meaning_commitment_scale = 0.70 if outer_phase == "CLOSURE" else 1.0

    if role_present:
        role_reliability = _clip01(familiarity * (1.0 - 0.50 * ambiguity))
    else:
        role_reliability = 0.0

    opponent_cycle = dict(field_description.get("opponent_cycle", {}) or {})
    opponent_state = dict(field_description.get("opponent", {}) or {})
    self_motion = dict(field_description.get("self_motion", {}) or {})
    self_state = dict(self_motion.get("state", {}) or {})
    opponent_velocity = dict(opponent_cycle.get("raw_velocity", {}) or {})
    self_velocity = dict(self_motion.get("raw_velocity", {}) or {})
    phase = opponent_cycle.get("phase", "unclear")

    opponent_vector = []
    self_vector = []
    for key in ("money", "land", "hands", "supply"):
        opponent_delta = float(opponent_velocity.get(key, 0.0) or 0.0)
        opponent_level = abs(float(opponent_state.get(key, 0.0) or 0.0))
        self_delta = float(self_velocity.get(key, 0.0) or 0.0)
        self_level = abs(float(self_state.get(key, 0.0) or 0.0))
        opponent_vector.append(opponent_delta / max(1.0, opponent_level, abs(opponent_delta)))
        self_vector.append(self_delta / max(1.0, self_level, abs(self_delta)))

    opponent_norm = sum(value * value for value in opponent_vector) ** 0.5
    self_norm = sum(value * value for value in self_vector) ** 0.5

    relation_votes = [
        1.0 if left * right > 0.0 else -1.0
        for key, left, right in zip(("money", "land", "hands", "supply"), self_vector, opponent_vector)
        if left != 0.0
        and right != 0.0
        and (
            float(self_velocity.get(key, 0.0) or 0.0) > 0.0
            or float(opponent_velocity.get(key, 0.0) or 0.0) > 0.0
        )
        and float(self_velocity.get(key, 0.0) or 0.0) != float(opponent_velocity.get(key, 0.0) or 0.0)
    ]
    field_alignment = sum(relation_votes) / len(relation_votes) if relation_votes else 0.0

    field_evidence = _clip01(min(opponent_norm, self_norm))
    if not field_context_present or phase == "unclear":
        field_evidence = 0.0
        field_alignment = 0.0

    field_axis_relation = {}
    for key, self_value, opponent_value in zip(("money", "land", "hands", "supply"), self_vector, opponent_vector):
        product = self_value * opponent_value
        self_delta = float(self_velocity.get(key, 0.0) or 0.0)
        opponent_delta = float(opponent_velocity.get(key, 0.0) or 0.0)
        shared_delta = self_delta == opponent_delta
        no_growth = self_delta <= 0.0 and opponent_delta <= 0.0
        field_axis_relation[key] = (
            "neutral" if shared_delta or no_growth
            else "aligned" if product > 0.0
            else "opposed" if product < 0.0
            else "neutral"
        )

    aligned_evidence = field_evidence * max(0.0, field_alignment)
    opposed_evidence = field_evidence * max(0.0, -field_alignment)
    reinforced = 1.0 - (1.0 - role_reliability) * (1.0 - aligned_evidence)
    context_reliability = _clip01(reinforced * (1.0 - opposed_evidence))
    commitment = _clip01(native_strength * (0.75 + 0.25 * context_reliability) * meaning_commitment_scale)

    signed_native = max(-1.0, min(1.0, (native_strength - 0.5) * 2.0))
    magnitude = float(os.getenv("ORIGIN_GATE_MAGNITUDE", "0.04"))
    magnitude = max(0.0, min(0.04, magnitude))
    polarity_name = os.getenv("ORIGIN_GATE_POLARITY", "normal").strip().lower()
    polarity = -1.0 if polarity_name == "inverted" else 1.0
    gate_scale = 1.0 - polarity * magnitude * context_reliability * signed_native
    gate_scale = max(1.0 - magnitude, min(1.0 + magnitude, gate_scale))

    return {
        "native_strength": round(native_strength, 6),
        "context_reliability": round(context_reliability, 6),
        "role_reliability": round(role_reliability, 6),
        "field_evidence": round(field_evidence, 6),
        "field_alignment": round(field_alignment, 6),
        "field_axis_relation": field_axis_relation,
        "aligned_evidence": round(aligned_evidence, 6),
        "opposed_evidence": round(opposed_evidence, 6),
        "field_phase": phase,
        "commitment": round(commitment, 6),
        "gate_scale": round(gate_scale, 6),
        "gate_polarity": polarity_name,
        "gate_magnitude": round(magnitude, 6),
        "direction_source": "native_origin",
        "field_effect": "directional_relation_to_commitment",
        "origin_strategy": internal.get("strategy_name"),
        "field_context_present": field_context_present,
        "field_description": field_description,
        "outer_meaning_present": outer_meaning_present,
        "outer_phase": outer_phase or None,
        "meaning_commitment_scale": round(meaning_commitment_scale, 6),
        "evaluation_lens": evaluation_lens,
        "evaluation_lens_present": bool(evaluation_lens),
        "candidate_evaluation": candidate_evaluation,
        "candidate_evaluation_present": bool(candidate_evaluation),
        "candidate_comparison": candidate_comparison,
        "candidate_comparison_present": bool(candidate_comparison),
        "candidate_ranking": None,
        "role_direction": None,
        "action_instruction": None,
        "strategy_instruction": None,
        "applies_on": "next_reentry",
    }
