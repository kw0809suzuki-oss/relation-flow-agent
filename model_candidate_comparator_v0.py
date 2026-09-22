"""Model-side Candidate Comparison v0.

Consumes descriptive candidate evaluations and forms only a partial order.
No scalar score, fixed weighting, forced total ranking, selection, target rewrite,
or action rewrite is produced.

A candidate weakly dominates another only when all comparable Option Preservation
dimensions are no worse and at least one is better. Unknown dimensions remain
unresolved rather than being imputed.
"""

def _metrics(row):
    ff=dict(row.get("future_fixation",{}) or {})
    op=dict(row.get("option_retention",{}) or {})
    rv=dict(row.get("reversibility",{}) or {})

    # Lower commitment ratio preserves more optionality.
    fixation=ff.get("commitment_ratio_to_liquid_cash")
    # Higher remaining liquid cash fraction preserves more optionality.
    retention=op.get("liquid_cash_fraction_remaining")
    # True would mean directly reversible; False means known not directly reversible.
    reversible=rv.get("direct_cash_reversal_known")

    return {
        "future_fixation": fixation,
        "option_retention": retention,
        "reversibility": reversible,
    }

def _cmp(a,b):
    ma=_metrics(a); mb=_metrics(b)
    observed=0
    a_better=0
    b_better=0

    # future_fixation: lower is better
    av=ma["future_fixation"]; bv=mb["future_fixation"]
    if isinstance(av,(int,float)) and isinstance(bv,(int,float)):
        observed+=1
        if av < bv: a_better+=1
        elif bv < av: b_better+=1

    # option_retention: higher is better
    av=ma["option_retention"]; bv=mb["option_retention"]
    if isinstance(av,(int,float)) and isinstance(bv,(int,float)):
        observed+=1
        if av > bv: a_better+=1
        elif bv > av: b_better+=1

    # reversibility: True > False; None stays unknown
    av=ma["reversibility"]; bv=mb["reversibility"]
    if isinstance(av,bool) and isinstance(bv,bool):
        observed+=1
        if av and not bv: a_better+=1
        elif bv and not av: b_better+=1

    if observed == 0:
        relation="unresolved"
    elif a_better > 0 and b_better == 0:
        relation="a_dominates"
    elif b_better > 0 and a_better == 0:
        relation="b_dominates"
    elif a_better == 0 and b_better == 0:
        relation="equivalent_on_observed_dimensions"
    else:
        relation="tradeoff_unresolved"

    return {
        "a_index":a.get("candidate_index"),
        "b_index":b.get("candidate_index"),
        "relation":relation,
        "observed_dimensions":observed,
        "a_better_dimensions":a_better,
        "b_better_dimensions":b_better,
    }

def compare(candidate_evaluation):
    ev=dict(candidate_evaluation or {})
    rows=list(ev.get("candidate_evaluations",[]) or [])
    if not rows:
        return None

    pairs=[]
    for i in range(len(rows)):
        for j in range(i+1,len(rows)):
            pairs.append(_cmp(rows[i],rows[j]))

    dominated=set()
    for p in pairs:
        if p["relation"]=="a_dominates":
            dominated.add(p["b_index"])
        elif p["relation"]=="b_dominates":
            dominated.add(p["a_index"])

    frontier=[
        row.get("candidate_index")
        for row in rows
        if row.get("candidate_index") not in dominated
    ]

    return {
        "comparison_method":"partial_order_option_preservation",
        "pairwise_relations":pairs,
        "nondominated_frontier":frontier,
        "total_ranking":None,
        "selection":None,
        "action_instruction":None,
        "weights":None,
        "scalar_score":None,
    }
