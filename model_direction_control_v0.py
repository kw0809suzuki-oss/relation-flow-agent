"""Direction-control candidate extraction v0.

Produces one comparison alternative without inventing a total ranking.
The alternative is simply the first different BUY_SEED candidate, in native
proposal order, that remains on the nondominated frontier after the selected
candidate. It is not called runner-up or second-best.
"""

def alternative_frontier_candidate(candidate_evaluation, candidate_comparison, candidate_selection):
    ev = dict(candidate_evaluation or {})
    comp = dict(candidate_comparison or {})
    sel = dict(candidate_selection or {})
    rows = list(ev.get("candidate_evaluations", []) or [])
    frontier = list(comp.get("nondominated_frontier", []) or [])
    selected_index = sel.get("selected_candidate_index")
    selected = sel.get("selected_candidate")
    selected_crop = selected[1] if isinstance(selected, (list, tuple)) and len(selected) >= 2 and selected[0] == "BUY_SEED" else None

    if selected_index is None or not frontier or selected_crop is None:
        return None

    frontier_set = set(frontier)
    for row in rows:
        idx = row.get("candidate_index")
        cand = row.get("candidate")
        if idx == selected_index or idx not in frontier_set:
            continue
        if not isinstance(cand, (list, tuple)) or len(cand) < 2 or cand[0] != "BUY_SEED":
            continue
        if cand[1] == selected_crop:
            continue
        return {
            "selection_method": "first_distinct_native_order_nondominated_frontier_candidate",
            "selected_candidate_index": idx,
            "selected_candidate": cand,
            "relation_to_selected": "alternative_frontier_candidate_not_ranked",
            "total_ranking": None,
            "weights": None,
            "scalar_score": None,
            "action_instruction": None,
        }
    return None
