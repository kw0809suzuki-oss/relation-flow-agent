"""Kaggriculture Judgment Guide v0.

This is not a policy and contains no action commands.
It defines what a judgment process should look at, what distinctions it should
preserve, and what it must not promote to fact without evidence.
"""

JUDGMENT_GUIDE_V0 = {
    "purpose": (
        "Read farm State and preserve plausible judgment directions without "
        "directly fixing an Action."
    ),
    "observe": [
        "Time: remaining horizon",
        "Capacity: land, cows, hands, crops, inventory",
        "Flow: money, feed/input, labor/work, harvest, sell",
        "Recovery: whether the production loop appears constrained or blocked",
        "Returnability: whether additional investment could plausibly return before terminal",
    ],
    "directions": {
        "grow": "まだ回収時間があり、能力拡張に余地がある",
        "earn": "今ある生産力をMoneyへ戻す方を重く見る",
        "recover": "Flowの詰まりを先に解いて生産ループを戻す",
    },
    "boundaries": [
        "Directions are not mutually exclusive.",
        "Direction is not Action.",
        "earn != early harvest",
        "closure != stop hiring",
        "recover != buy wheat",
        "self, margin, and win are separate evidence axes.",
        "Do not promote an unobserved relation to fact.",
        "Do not reject an upper-level direction from one failed concrete action.",
    ],
    "known_evidence": [
        "Late continued Expansion has shown terminal-self loss signals.",
        "Closure direction has reproduced terminal-self improvement across multiple opponents.",
        "The concrete Switch 'stop HIRE + early HARVEST' worsened against Closure-only in 15/15 cases.",
        "The upper-level Switch direction itself remains open.",
    ],
}
