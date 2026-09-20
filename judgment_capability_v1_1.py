"""Judgment Capability v1.1 packet builder.

This layer performs only:
State reading -> Flow grounding triage -> open hint evaluation task.

It does NOT:
- judge hint truth,
- apply triage as a weight,
- generate directions,
- generate actions,
- select actions.
"""
from copy import deepcopy

from judgment_guide_v1_1 import JUDGMENT_GUIDE_V11
from judgment_capability_v1 import observe_state


def build_packet(obs, human_direction=None):
    return {
        "schema": "kaggriculture.judgment-capability.v1.1",
        "observed_state": observe_state(obs),
        "human_direction": human_direction,
        "flow_grounding": {
            "relation_hints": deepcopy(JUDGMENT_GUIDE_V11["relation_hints"]),
            "triage_contract": deepcopy(JUDGMENT_GUIDE_V11["triage_contract"]),
        },
        "judgment_model_task": {
            "contract": deepcopy(JUDGMENT_GUIDE_V11["judgment_model_contract"]),
            "required_hint_evaluation": {
                hint["name"]: {
                    "relevance": None,
                    "state_support": [],
                    "state_counter": [],
                    "conflicts": [],
                    "missing_evidence": [],
                }
                for hint in JUDGMENT_GUIDE_V11["relation_hints"]
            },
            "direction_generation": "not_performed_in_v1.1",
        },
        "judgment_boundaries": deepcopy(JUDGMENT_GUIDE_V11["boundaries"]),
        "boundary": {
            "hint_truth_decided": False,
            "triage_used_as_weight": False,
            "hint_relevance_precomputed": False,
            "direction_precomputed": False,
            "action_precomputed": False,
            "selection_precomputed": False,
        },
    }


def guide():
    return deepcopy(JUDGMENT_GUIDE_V11)
