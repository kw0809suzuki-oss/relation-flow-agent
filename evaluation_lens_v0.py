"""Evaluation Lens v0.

Converts a high-level abstraction into questions for viewing existing candidates.
It does not score, rank, suppress, force, or rewrite candidates/actions.
"""

def build(outer_meaning, origin_internal):
    meaning=dict(outer_meaning or {})
    internal=dict(origin_internal or {})
    phase=str(meaning.get("phase","") or "").upper()
    if phase!="OPTION_PRESERVATION":
        return None

    market=list(internal.get("market",[]) or [])
    candidates=[]
    for idx,action in enumerate(market):
        candidates.append({
            "candidate_index":idx,
            "candidate":action,
            "questions":{
                "future_fixation":"How much future state would this candidate lock in?",
                "reversibility":"How easy would it be to reverse or redirect after taking this candidate?",
                "option_retention":"How many meaningful alternatives would remain available after taking this candidate?",
            },
            "evaluation":None,
            "score":None,
            "rank":None,
            "decision":None,
        })

    return {
        "source_abstraction":"OPTION_PRESERVATION",
        "principle":meaning.get("principle"),
        "dimensions":[
            "future_fixation",
            "reversibility",
            "option_retention",
        ],
        "candidates":candidates,
        "ranking_instruction":None,
        "action_instruction":None,
        "strategy_instruction":None,
        "numeric_rule":None,
    }
