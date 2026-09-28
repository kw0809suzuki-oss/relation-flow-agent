#!/usr/bin/env python3
"""Capture the canonical normal-vs-replaced delta trace after Day3 H0.

This is an observation-only probe for Delta Trace Split:
the first time a previously shared intervention-delta signature becomes
case-dependent across Fresh20.

Per case this runner:
1. records the same-seed/current WR-02 selected-agent action at Day3 H0;
2. runs normal P12;
3. runs P12 with only that Day3 H0 action replaced;
4. canonicalizes selected-seat observations into self/opponent form;
5. stores the non-zero delta signature at every common observation from Day3 H1 onward.

Terminal response is recorded but is not used to construct or select signatures.
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
OUT = Path(f"p12_day3h0_delta_trace_split_v0_{SEED}_seat{SEAT}.json")
TARGET = (3, 0)
START = (3, 1)


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


def point(obs):
    return (int(obs.get("day", 0) or 0), int(obs.get("hour", 0) or 0))


def canonical_obs(obs):
    """Canonicalize seat-dependent farm ordering; remove clock/runtime fields."""
    x = plain(obs)
    farms = list(x.get("farms", []) or [])
    player = int(x.get("player", SEAT))
    other = 1 - player

    out = {
        "self": farms[player] if player < len(farms) else None,
        "opponent": farms[other] if other < len(farms) else None,
        "private": x.get("private", {}) or {},
        "market": x.get("market", {}) or {},
        "town": x.get("town", {}) or {},
    }
    return out


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        if not obj and prefix:
            out[prefix] = {}
        for k in sorted(obj):
            p = f"{prefix}.{k}" if prefix else str(k)
            out.update(flatten(obj[k], p))
        return out
    if isinstance(obj, list):
        if not obj and prefix:
            out[prefix] = []
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
        return out
    out[prefix] = obj
    return out


def delta_signature(normal, replaced):
    """Return only changed canonical leaves.

    Numeric leaves use replaced-normal deltas.
    Non-numeric leaves use explicit normal->replaced transitions.
    """
    a = flatten(normal)
    b = flatten(replaced)
    sig = {}
    for p in sorted(set(a) | set(b)):
        av = a.get(p, "__MISSING__")
        bv = b.get(p, "__MISSING__")
        if av == bv:
            continue

        if (
            isinstance(av, (int, float))
            and not isinstance(av, bool)
            and isinstance(bv, (int, float))
            and not isinstance(bv, bool)
        ):
            d = float(bv) - float(av)
            if d == 0:
                continue
            # Keep integer-looking values compact and deterministic.
            sig[p] = int(d) if d.is_integer() else round(d, 9)
        else:
            sig[p] = {"normal": av, "replaced": bv}
    return sig


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
            target_action = plain(action)
            if replacement is not None:
                return copy.deepcopy(replacement)
        if pt >= START:
            observations[f"{pt[0]}:{pt[1]}"] = canonical_obs(obs)
        return action

    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[SEAT] = observed
    env.run(players)
    rewards = [float(x.reward) for x in env.state]
    return {
        "target_action": target_action,
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


def main():
    cur = play(current)
    normal = play(candidate)
    replaced = play(candidate, replacement=cur["target_action"])

    common = sorted(
        set(normal["observations"]) & set(replaced["observations"]),
        key=parse_key,
    )

    trace = {}
    for k in common:
        trace[k] = delta_signature(
            normal["observations"][k],
            replaced["observations"][k],
        )

    payload = {
        "schema": "kaggriculture.p12-day3h0-delta-trace-split.case.v0",
        "seed": SEED,
        "seat": SEAT,
        "replacement": {
            "source": "current WR-02 selected-agent Day3H0 submitted action",
            "target": "normal P12 selected-agent Day3H0 submitted action",
            "action_changed": cur["target_action"] != normal["target_action"],
        },
        "terminal": {
            "normal_self": normal["terminal"]["self"],
            "replaced_self": replaced["terminal"]["self"],
            "replacement_effect": replaced["terminal"]["self"] - normal["terminal"]["self"],
        },
        "trace": trace,
        "observation_point_count": len(common),
        "boundary": [
            "Delta signature is canonicalized to self/opponent before cross-case comparison.",
            "Only normal-vs-replaced differences are stored; absolute seed/world State is not compared across cases.",
            "Numeric leaves are replaced-minus-normal; changed non-numeric leaves are explicit transitions.",
            "Trace begins at Day3 Hour1, the already-confirmed shared immediate response.",
            "Terminal response is recorded but is not used to generate delta signatures.",
            "A future cross-case split is descriptive until terminal-sign association is checked after the split is located.",
            "No policy logic is changed or promoted by this observer.",
        ],
    }

    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("P12_DAY3H0_DELTA_TRACE_CASE " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "action_changed": payload["replacement"]["action_changed"],
        "observation_point_count": len(common),
        "day3h1_signature": trace.get("3:1", {}),
        "terminal_effect": payload["terminal"]["replacement_effect"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
