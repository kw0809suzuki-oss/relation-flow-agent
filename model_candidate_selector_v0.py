"""Model-side Candidate Selection Priority v0.

Consumes descriptive candidate evaluation plus partial-order comparison.
It does not create a scalar score, fixed weights, or a total ranking.

A selection is emitted only when the comparison has directional information
(at least one dominated candidate). Among comparable nondominated candidates,
the model's existing/native candidate order is preserved.
"""

def select(candidate_evaluation, candidate_comparison):
    ev = dict(candidate_evaluation or {})
    comp = dict(candidate_comparison or {})
    rows = list(ev.get("candidate_evaluations", []) or [])
    pairs = list(comp.get("pairwise_relations", []) or [])
    if not rows or not pairs:
        return None

    comparable = set()
    dominated = set()
    for p in pairs:
        if int(p.get("observed_dimensions", 0) or 0) > 0:
            comparable.add(p.get("a_index"))
            comparable.add(p.get("b_index"))
        rel = p.get("relation")
        if rel == "a_dominates":
            dominated.add(p.get("b_index"))
        elif rel == "b_dominates":
            dominated.add(p.get("a_index"))

    # Do not invent a choice when comparison produced no directional difference.
    dominated.discard(None)
    comparable.discard(None)
    if not dominated:
        return None

    frontier = [
        row for row in rows
        if row.get("candidate_index") in comparable
        and row.get("candidate_index") not in dominated
    ]
    if not frontier:
        return None

    # Preserve the model's own proposal order; comparison only removes
    # candidates known to be dominated on the observed dimensions.
    chosen = frontier[0]
    return {
        "selection_method": "native_order_after_partial_order_filter",
        "selected_candidate_index": chosen.get("candidate_index"),
        "selected_candidate": chosen.get("candidate"),
        "directional_evidence": "pairwise_dominance_present",
        "dominated_candidate_indices": sorted(dominated),
        "total_ranking": None,
        "weights": None,
        "scalar_score": None,
        "action_instruction": "prioritize selected candidate if it is still available on next reentry",
    }
