"""Model-side Candidate Evaluation v0.

Consumes an Evaluation Lens and the model's own current proposal/state.
Produces descriptive candidate evaluations only.

It does NOT rank, select, suppress, force, or rewrite actions.
Unknowns stay unknown.
"""

from strong_origin import SEED_COST

def _seed_cost(action):
    if not isinstance(action,(list,tuple)) or len(action)<3 or action[0]!="BUY_SEED":
        return None
    crop=action[1]
    qty=action[2]
    unit=SEED_COST.get(crop)
    if unit is None or not isinstance(qty,(int,float)):
        return None
    return float(unit)*float(qty)

def evaluate(evaluation_lens, origin_internal, field_description):
    lens=dict(evaluation_lens or {})
    internal=dict(origin_internal or {})
    field=dict(field_description or {})
    if not lens:
        return None

    self_state=dict(field.get("self",{}) or {})
    money=self_state.get("money")
    try:
        money=float(money)
    except Exception:
        money=None

    out=[]
    for item in list(lens.get("candidates",[]) or []):
        action=item.get("candidate")
        ev={
            "candidate_index":item.get("candidate_index"),
            "candidate":action,
            "future_fixation":{},
            "reversibility":{},
            "option_retention":{},
        }

        cost=_seed_cost(action)
        if cost is not None:
            ratio=(cost/money) if money and money>0 else None
            ev["future_fixation"]={
                "known_cash_commitment":cost,
                "commitment_ratio_to_liquid_cash":ratio,
                "future_specific_asset":"seed",
            }
            ev["reversibility"]={
                "direct_cash_reversal_known":False,
                "note":"cash becomes a crop-specific seed commitment; later recovery path is separate from this evaluation",
            }
            ev["option_retention"]={
                "liquid_cash_before":money,
                "liquid_cash_after_if_isolated":None if money is None else money-cost,
                "liquid_cash_fraction_remaining":None if ratio is None else max(0.0,1.0-ratio),
            }
        else:
            ev["future_fixation"]={
                "known_cash_commitment":None,
                "commitment_ratio_to_liquid_cash":None,
                "future_specific_asset":None,
            }
            ev["reversibility"]={
                "direct_cash_reversal_known":None,
                "note":"not evaluated by v0",
            }
            ev["option_retention"]={
                "liquid_cash_before":money,
                "liquid_cash_after_if_isolated":None,
                "liquid_cash_fraction_remaining":None,
            }

        ev["score"]=None
        ev["rank"]=None
        ev["decision"]=None
        out.append(ev)

    return {
        "source_lens":lens.get("source_abstraction"),
        "candidate_evaluations":out,
        "ranking":None,
        "selection":None,
        "action_instruction":None,
    }
