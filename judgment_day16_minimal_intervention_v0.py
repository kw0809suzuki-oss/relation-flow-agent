"""Day16 Judgment -> Minimal Intervention bridge v0.

This is not a policy and does not adopt either Judgment claim.

B claim projection: reduce newly-added workload.
  Minimal intervention: on day 16 only, suppress workload-adding purchases
  (BUY_SEED / BUY_ANIMAL / BUY_PRODUCT COW). Preserve all other native actions.

C claim projection: increase work capacity.
  Minimal intervention: on day 16 only, request one HIRE once.
  Preserve every other native G17 action.

The interventions are concrete probes. Their outcome does not by itself prove or
reject the abstract Judgment claim.
"""
import copy
import g17_agent as native

TARGET_DAY = 16

_mode = None
_events = []
_first_state = None
_hire_attempted = False


def reset_experiment(mode):
    global _mode, _events, _first_state, _hire_attempted
    _mode = mode
    _events = []
    _first_state = None
    _hire_attempted = False
    native.reset_telemetry()


def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)


def _snapshot(obs):
    player = obs["player"]
    me = obs["farms"][player]
    return {
        "day": int(obs.get("day", 0) or 0),
        "money": me.get("money", 0),
        "hands": len(me.get("hands", []) or []),
        "farmer": copy.deepcopy(me.get("farmer")),
    }


def _adds_workload(action):
    if not isinstance(action, (list, tuple)) or not action:
        return False
    op = action[0]
    if op in ("BUY_SEED", "BUY_ANIMAL"):
        return True
    return op == "BUY_PRODUCT" and len(action) > 1 and action[1] == "COW"


def agent(obs):
    global _first_state, _hire_attempted
    actions = native.agent(obs)
    if not isinstance(actions, dict):
        return actions

    day = int(obs.get("day", 0) or 0)
    if day != TARGET_DAY:
        return actions

    if _first_state is None:
        _first_state = _snapshot(obs)

    revised = copy.deepcopy(actions)
    market = list(revised.get("market", []) or [])

    if _mode == "B_reduce_workload":
        removed = [a for a in market if _adds_workload(a)]
        if removed:
            revised["market"] = [a for a in market if not _adds_workload(a)]
            _events.append({
                "day": day,
                "kind": "reduce_new_workload",
                "removed": copy.deepcopy(removed),
            })
        return revised

    if _mode == "C_increase_capacity":
        if not _hire_attempted:
            _hire_attempted = True
            already = any(
                isinstance(a, (list, tuple)) and a and a[0] == "HIRE"
                for a in market
            )
            if not already:
                revised["market"] = market + [["HIRE"]]
            _events.append({
                "day": day,
                "kind": "increase_work_capacity",
                "hire_requested": True,
                "native_hire_present": already,
                "before_market": copy.deepcopy(market),
                "after_market": copy.deepcopy(revised.get("market", [])),
            })
        return revised

    return actions


def get_events():
    return copy.deepcopy(_events)


def get_first_state():
    return copy.deepcopy(_first_state)


def get_trace():
    return native.get_trace()
