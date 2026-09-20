"""Kaggriculture Judgment Manufacturing Policy v0.

Central principle:
Do not preserve uncertainty for its own sake.
Preserve uncertainty so the system can close only where evidence supports closure.
"""

MANUFACTURING_POLICY_V0 = {
    "central_principle": (
        "閉じないために曖昧にするのではない。"
        "正しく閉じるために、未確定を保持できるようにする。"
    ),
    "design_question": (
        "このコードはAIに考えさせているのか、それとも根拠より先に閉じているのか。"
    ),
    "required_separations": [
        "observed_state != interpretation",
        "relation_hint != established_rule",
        "triage_strength != decision_weight",
        "hint_relevance != precomputed_truth",
        "direction != action",
        "candidate != selection",
        "learning_candidate != adopted_guide_update",
        "self != margin != win",
    ],
    "premature_closure_signals": [
        "A threshold directly emits a judgment direction.",
        "A triage label is reused as a fixed decision weight.",
        "A relation hint is treated as true before State-specific interpretation.",
        "One failed action rejects an upper-level direction.",
        "A candidate action is promoted without comparison.",
        "A learning candidate updates the guide automatically.",
    ],
    "healthy_open_state": [
        "Unknown or conflicting evidence can remain explicit.",
        "Multiple directions may coexist.",
        "A strong candidate hint may be not relevant in the current State.",
        "A weak candidate hint may still become relevant in the current State.",
        "The system may delay commitment until the selection boundary.",
        "Battle evidence can reopen earlier interpretation.",
    ],
}
