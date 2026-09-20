"""Compressed judgment frame adopted from Judgment Garden.

Core cycle:
    Observe -> Frame -> Choose -> Act -> Learn

Core boundaries:
    Missing != Negative
    Frame != Answer
    Choice != Execution
    Local Outcome != Battle Outcome
    Outcome != Rule
    Experience != Adoption
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


PRINCIPLES: Tuple[str, ...] = (
    "missing_is_not_negative",
    "frame_is_not_answer",
    "choice_is_not_execution",
    "local_outcome_is_not_battle_outcome",
    "outcome_is_not_rule",
    "experience_is_not_adoption",
)


class Intent(str, Enum):
    PERFORM = "perform"
    LEARN = "learn"
    PRESERVE = "preserve"


@dataclass(frozen=True)
class Observe:
    known: Tuple[str, ...] = ()
    missing: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Frame:
    question: str
    directions: Tuple[str, ...] = ()
    candidates: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Choose:
    intent: Intent
    selected: Optional[str]
    reason: str


@dataclass(frozen=True)
class Act:
    selected: Optional[str]
    executed: bool
    note: str = ""


@dataclass(frozen=True)
class Learn:
    outcome: str
    abstraction: str
    return_signal: str
    adoption: str = "candidate_only"


@dataclass(frozen=True)
class JudgmentCycle:
    observe: Observe
    frame: Frame
    choose: Choose
    act: Act
    learn: Learn


@dataclass(frozen=True)
class BattleOutcome:
    result: str
    scope: str = "battle_only"
    causal_attribution: bool = False
    adoption: str = "candidate_only"


def execution_consistent(choice: Choose, act: Act) -> bool:
    """Check trace consistency without claiming strategic correctness."""
    if act.executed:
        return choice.selected is not None and act.selected == choice.selected
    return True


def can_auto_adopt(_: Learn | BattleOutcome) -> bool:
    """Observed experience never auto-promotes into mainline behavior."""
    return False
