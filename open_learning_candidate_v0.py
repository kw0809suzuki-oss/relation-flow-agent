"""Open Learning Candidate v0.

Keeps an unresolved learning position across observations without promoting it
into the formal taxonomy. Maturity and adoption are deliberately independent.
"""

MATURITY_ORDER = ["new", "reappeared", "tested", "replicated"]


def _maturity_from_evidence(evidence_history):
    stages = {item.get("stage") for item in evidence_history}
    if "replicated" in stages:
        return "replicated"
    if "tested" in stages:
        return "tested"
    if "reappeared" in stages:
        return "reappeared"
    return "new"


def build_open_learning_candidate(name, evidence_history, *, adoption="proposed"):
    history = [dict(item) for item in evidence_history]
    maturity = _maturity_from_evidence(history)

    if adoption != "proposed":
        raise ValueError(
            "Open Learning Candidate v0 cannot adopt or formalize a candidate automatically."
        )

    return {
        "schema": "kaggriculture.open-learning-candidate.v0",
        "candidate": name,
        "maturity": maturity,
        "adoption": adoption,
        "evidence_history": history,
        "formal_taxonomy_member": False,
        "auto_promote_taxonomy": False,
        "auto_update_judgment_guide": False,
        "boundary": [
            "Maturity records evidential growth; it is not adoption.",
            "proposed != adopted.",
            "replicated != formal taxonomy membership.",
            "Uncertainty is retained across observations rather than reset to zero.",
            "Formal adoption requires a separate decision outside this object.",
        ],
    }
