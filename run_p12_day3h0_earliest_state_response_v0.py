#!/usr/bin/env python3
"""Locate the earliest observable State response to the Day3 Hour0 action replacement.

Comparison:
  normal P12
  vs
  P12 with only the selected agent's Day3 Hour0 submitted action replaced by
  the same-seed/current-world submitted action.

This probe scans official observations forward from immediately after Day3 H0
and records only the earliest differing observable State leaves. It does not
use terminal outcome to choose the first difference and does not infer cause
beyond sensitivity to the intervention.
"""
import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as current
import wr02_p12_day0_reservation_v0 as candidate

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"p12_day3h0_earliest_state_response_v0_{SEED}_seat{SEAT}.json")
TARGET = (3, 0)


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def plain(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if hasattr(v, "items"):
        try:
            return {str(k): plain(x) for k, x in v.items()}
        except Exception:
            pass
    if hasattr(v, "tolist"):
        try:
            return plain(v.tolist())
        except Exception:
            pass
    if hasattr(v, "item"):
        try:
            return plain(v.item())
        except Exception:
            pass
    if hasattr(v, "__dict__"):
        try:
            return {str(k): plain(x) for k, x in vars(v).items()}
        except Exception:
            pass
    return repr(v)


def jsonable(v):
    return json.loads(json.dumps(plain(v), ensure_ascii=False))


def point(obs):
    return (int(obs.get("day", 0) or 0), int(obs.get("hour", 0) or 0))


def scrub_obs(obs):
    """Keep world-facing observation fields; drop timing/runtime noise only."""
    x = jsonable(obs)
    if isinstance(x, dict):
        x.pop("remainingOverageTime", None)
    return x


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k in sorted(obj):
            p = f"{prefix}.{k}" if prefix else str(k)
            out.update(flatten(obj[k], p))
        if not obj and prefix:
            out[prefix] = {}
        return out
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            p = f"{prefix}[{i}]"
            out.update(flatten(v, p))
        if not obj and prefix:
            out[prefix] = []
        return out
    out[prefix] = obj
    return out


def play(module, replacement=None):
    configure()
    module.reset_telemetry()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    target_action = None
    observations = {}

    def observed(obs):
        nonlocal target_action
        action = module.agent(obs)
        pt = point(obs)
        if pt == TARGET:
            target_action = jsonable(action)
            if replacement is not None:
                return copy.deepcopy(replacement)
        if pt > TARGET:
            observations[f"{pt[0]}:{pt[1]}"] = scrub_obs(obs)
        return action

    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[SEAT] = observed
    env.run(players)
    rewards = [float(x.reward) for x in env.state]
    return {
        "target_action_generated": target_action,
        "observations": observations,
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
    }


def parse_key(k):
    d, h = k.split(":")
    return (int(d), int(h))


def diff_leaves(a, b):
    fa = flatten(a)
    fb = flatten(b)
    paths = sorted(set(fa) | set(fb))
    diffs = []
    for p in paths:
        av = fa.get(p, "__MISSING__")
        bv = fb.get(p, "__MISSING__")
        if av != bv:
            diffs.append({
                "path": p,
                "normal": av,
                "replaced": bv,
            })
    return diffs


def main():
    baseline = play(current)
    normal = play(candidate)
    replacement_action = baseline["target_action_generated"]
    replaced = play(candidate, replacement=replacement_action)

    common = sorted(
        set(normal["observations"]).intersection(replaced["observations"]),
        key=parse_key,
    )

    earliest = None
    first_diff_paths = []
    state_reconvergence = None
    changed_points = 0

    seen_difference = False
    for k in common:
        diffs = diff_leaves(normal["observations"][k], replaced["observations"][k])
        if diffs:
            changed_points += 1
            if earliest is None:
                d, h = parse_key(k)
                earliest = {
                    "day": d,
                    "hour": h,
                    "difference_count": len(diffs),
                    "differences": diffs,
                }
                first_diff_paths = [x["path"] for x in diffs]
            seen_difference = True
        elif seen_difference and state_reconvergence is None:
            d, h = parse_key(k)
            state_reconvergence = {"day": d, "hour": h}

    # Persistence of the exact first-difference paths across later observations.
    persistence = {}
    if earliest is not None:
        start = (earliest["day"], earliest["hour"])
        for path in first_diff_paths:
            first_equal_after = None
            different_points = 0
            observed_points = 0
            for k in common:
                pt = parse_key(k)
                if pt < start:
                    continue
                fn = flatten(normal["observations"][k])
                fr = flatten(replaced["observations"][k])
                if path not in fn and path not in fr:
                    continue
                observed_points += 1
                if fn.get(path, "__MISSING__") != fr.get(path, "__MISSING__"):
                    different_points += 1
                elif pt > start and first_equal_after is None:
                    first_equal_after = {"day": pt[0], "hour": pt[1]}
            persistence[path] = {
                "observed_points_from_first_difference": observed_points,
                "different_points": different_points,
                "first_equal_after": first_equal_after,
            }

    payload = {
        "schema": "kaggriculture.p12-day3h0-earliest-state-response.v0",
        "seed": SEED,
        "seat": SEAT,
        "replacement": {
            "source": "current WR-02 selected-agent submitted action at same seed/seat Day3 Hour0",
            "target": "P12 selected-agent submitted action at Day3 Hour0",
            "action_changed": replacement_action != normal["target_action_generated"],
        },
        "terminal": {
            "normal_self": normal["terminal"]["self"],
            "replaced_self": replaced["terminal"]["self"],
            "replacement_effect": replaced["terminal"]["self"] - normal["terminal"]["self"],
        },
        "scan": {
            "common_observation_points": len(common),
            "earliest_difference": earliest,
            "first_difference_path_persistence": persistence,
            "first_full_state_reconvergence_after_difference": state_reconvergence,
            "changed_observation_point_count": changed_points,
        },
        "boundary": [
            "The scan begins strictly after Day3 Hour0, so the target pre-action observation is not counted as a response.",
            "Only official selected-seat observations are compared; runtime timing noise is removed.",
            "Earliest difference is selected without using terminal sign or magnitude.",
            "A differing field is intervention-sensitive in this replay; it is not automatically the complete causal mechanism.",
            "The transplanted action is processed inside the P12 world, so natural-policy equivalence is not assumed.",
            "No policy logic is changed or promoted by this observer.",
        ],
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("P12_DAY3H0_EARLIEST_STATE_RESPONSE " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "action_changed": payload["replacement"]["action_changed"],
        "replacement_terminal_effect": payload["terminal"]["replacement_effect"],
        "earliest": earliest and {
            "day": earliest["day"],
            "hour": earliest["hour"],
            "difference_count": earliest["difference_count"],
            "paths": first_diff_paths,
        },
        "reconvergence": state_reconvergence,
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
