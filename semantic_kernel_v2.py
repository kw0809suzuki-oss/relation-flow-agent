from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Callable, Mapping, Optional, Sequence


def _freeze_map(values: Mapping[str, int] | None = None) -> Mapping[str, int]:
    return MappingProxyType(dict(values or {}))


@dataclass(frozen=True)
class StateSnapshot:
    values: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", _freeze_map(self.values))

    def get(self, key: str, default: int = 0) -> int:
        return self.values.get(key, default)


Trigger = Callable[[StateSnapshot], bool]
Requirement = Callable[[StateSnapshot], bool]
Effect = tuple[str, str, int]


@dataclass(frozen=True)
class ActionIntent:
    id: str
    kind: str
    claims: Mapping[str, int] = field(default_factory=dict)
    effects: tuple[Effect, ...] = ()
    conflict_keys: frozenset[str] = frozenset()
    phase: Optional[int] = None
    after: tuple[str, ...] = ()
    requires: Optional[Requirement] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "claims", _freeze_map(self.claims))
        object.__setattr__(self, "conflict_keys", frozenset(self.conflict_keys))
        object.__setattr__(self, "after", tuple(self.after))
        object.__setattr__(self, "effects", tuple(self.effects))


@dataclass(frozen=True)
class Rule:
    id: str
    version: str
    trigger: Trigger
    action: ActionIntent
    observation_scope: str = "step"
    priority: int = 0
    compose: bool = True
    exclusive: bool = False
    conflicts_with: frozenset[str] = frozenset()
    supersedes: frozenset[str] = frozenset()
    evidence_status: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "conflicts_with", frozenset(self.conflicts_with))
        object.__setattr__(self, "supersedes", frozenset(self.supersedes))
        if self.exclusive and self.compose:
            raise ValueError(f"{self.id}: exclusive=true cannot compose=true")


@dataclass(frozen=True)
class StepTrace:
    state_before: Mapping[str, int]
    eligible_rule_ids: tuple[str, ...] = ()
    selected_rule_ids: tuple[str, ...] = ()
    rejection_reasons: tuple[tuple[str, str], ...] = ()
    plan_status: str = "not_run"
    plan_reason: Optional[str] = None
    planned_action_ids: tuple[str, ...] = ()
    executed_action_ids: tuple[str, ...] = ()
    state_after: Optional[Mapping[str, int]] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_before", _freeze_map(self.state_before))
        if self.state_after is not None:
            object.__setattr__(self, "state_after", _freeze_map(self.state_after))


ActionBundle = tuple[ActionIntent, ...]


def evaluate(snapshot: StateSnapshot, rules: Sequence[Rule]) -> tuple[tuple[Rule, ...], StepTrace]:
    eligible = tuple(sorted((rule for rule in rules if rule.trigger(snapshot)), key=lambda r: r.id))
    return eligible, StepTrace(
        state_before=snapshot.values,
        eligible_rule_ids=tuple(rule.id for rule in eligible),
    )


def _rules_conflict(a: Rule, b: Rule) -> bool:
    return a.exclusive or b.exclusive or b.id in a.conflicts_with or a.id in b.conflicts_with


def resolve(snapshot: StateSnapshot, eligible_rules: Sequence[Rule], trace: StepTrace):
    del snapshot
    eligible_by_id = {rule.id: rule for rule in eligible_rules}
    rejections: dict[str, str] = {}
    for winner in eligible_rules:
        for loser_id in winner.supersedes:
            if loser_id in eligible_by_id and loser_id != winner.id:
                rejections.setdefault(loser_id, f"superseded_by:{winner.id}")

    ranked = sorted((r for r in eligible_rules if r.id not in rejections), key=lambda r: (-r.priority, r.id))
    selected: list[Rule] = []
    for candidate in ranked:
        conflict = next((chosen for chosen in selected if _rules_conflict(candidate, chosen)), None)
        if conflict is None:
            selected.append(candidate)
        else:
            rejections[candidate.id] = f"rule_conflict_with:{conflict.id}"

    selected_tuple = tuple(sorted(selected, key=lambda r: r.id))
    return selected_tuple, replace(
        trace,
        selected_rule_ids=tuple(r.id for r in selected_tuple),
        rejection_reasons=tuple(sorted(rejections.items())),
    )


def _has_path(start: str, target: str, deps: Mapping[str, set[str]]) -> bool:
    stack = [start]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(deps.get(current, ()))
    return False


def _order_actions(actions: Sequence[ActionIntent]) -> tuple[ActionIntent, ...] | None:
    by_id = {a.id: a for a in actions}
    deps: dict[str, set[str]] = {a.id: set(a.after) for a in actions}
    for action in actions:
        if any(dep not in by_id for dep in action.after):
            return None

    remaining = set(by_id)
    ordered: list[ActionIntent] = []
    while remaining:
        ready = [by_id[action_id] for action_id in remaining if deps[action_id].isdisjoint(remaining)]
        if not ready:
            return None
        ready.sort(key=lambda a: (a.phase is None, a.phase if a.phase is not None else 0, a.id))
        chosen = ready[0]
        ordered.append(chosen)
        remaining.remove(chosen.id)
    return tuple(ordered)


def plan(snapshot: StateSnapshot, selected_rules: Sequence[Rule], trace: StepTrace):
    actions = tuple(rule.action for rule in selected_rules)

    for action in actions:
        if action.requires is not None and not action.requires(snapshot):
            return None, replace(
                trace,
                plan_status="invalid",
                plan_reason=f"requirement_failed:{action.id}",
                planned_action_ids=(),
                executed_action_ids=(),
            )

    totals: dict[str, int] = {}
    for action in actions:
        for resource, amount in action.claims.items():
            totals[resource] = totals.get(resource, 0) + amount

    for resource, total in sorted(totals.items()):
        if total > snapshot.get(resource):
            return None, replace(
                trace,
                plan_status="invalid",
                plan_reason=f"resource_claim_conflict:{resource}",
                planned_action_ids=(),
                executed_action_ids=(),
            )

    deps = {a.id: set(a.after) for a in actions}
    for i, a in enumerate(actions):
        for b in actions[i + 1:]:
            shared = a.conflict_keys & b.conflict_keys
            if not shared:
                continue
            dependency_orders = _has_path(a.id, b.id, deps) or _has_path(b.id, a.id, deps)
            phase_orders = a.phase is not None and b.phase is not None and a.phase != b.phase
            if not dependency_orders and not phase_orders:
                key = sorted(shared)[0]
                pair = ":".join(sorted((a.id, b.id)))
                return None, replace(
                    trace,
                    plan_status="invalid",
                    plan_reason=f"non_commutative_conflict:{pair}:{key}",
                    planned_action_ids=(),
                    executed_action_ids=(),
                )

    ordered = _order_actions(actions)
    if ordered is None:
        return None, replace(trace, plan_status="invalid", plan_reason="invalid_action_dependency_graph")

    return ordered, replace(
        trace,
        plan_status="valid",
        plan_reason=None,
        planned_action_ids=tuple(action.id for action in ordered),
    )


def apply(snapshot: StateSnapshot, action_bundle: ActionBundle, trace: StepTrace):
    state = dict(snapshot.values)
    for action in action_bundle:
        for key, op, value in action.effects:
            if op == "add":
                state[key] = state.get(key, 0) + value
            elif op == "set":
                state[key] = value
            else:
                raise ValueError(f"unsupported effect op: {op}")

    next_state = StateSnapshot(state)
    return next_state, replace(
        trace,
        executed_action_ids=tuple(action.id for action in action_bundle),
        state_after=next_state.values,
    )
