#!/usr/bin/env python3
"""A/B/C Seed Horizon Isolation fresh10 v0.

Runs the same frozen body and opponent on fixed seed/seat pairs.

A: Current D14.
B: D14 Seed reopen, unconditioned.
C: D14 Seed reopen only when earliest public-rule HARVEST eligibility is within
   the playable season.

The runner records:
- filter telemetry,
- actual self action sequence and first pairwise divergence,
- post-D14 physical plant activation,
- actual HARVEST boundaries,
- terminal result.

It does not claim Cash lineage from the additional seeds.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import seed_horizon_isolation_probe_v0 as probe


CASES = [
    (7351, 0),
    (7352, 1),
    (7353, 0),
    (7354, 1),
    (7355, 0),
    (7356, 1),
    (7357, 0),
    (7358, 1),
    (7359, 0),
    (7360, 1),
]
MODES = (
    probe.MODE_CURRENT_D14,
    probe.MODE_SEED_REOPEN,
    probe.MODE_HARVEST_FEASIBLE_SEED,
)
OUT = Path("seed_horizon_isolation_fresh10_v0_result.json")


def plain(v: Any) -> Any:
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
            return {
                str(k): plain(x)
                for k, x in vars(v).items()
                if not str(k).startswith("_")
            }
        except Exception:
            pass
    return str(v)


def own_farm(obs: Dict[str, Any], player: int) -> Dict[str, Any]:
    farms = obs.get("farms", []) or []
    if player < len(farms) and isinstance(farms[player], dict):
        return farms[player]
    return {}


def tile_map(obs: Dict[str, Any], player: int) -> Dict[str, Dict[str, Any]]:
    farm = own_farm(obs, player)
    out = {}
    for y, row in enumerate(farm.get("tiles", []) or []):
        for x, tile in enumerate(row or []):
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "PLANT" and tile.get("crop"):
                crop = str(tile["crop"])
                pd = int(tile.get("planted_day", 0) or 0)
                key = f"crop:{crop}:{x},{y}:d{pd}"
                out[key] = {
                    "lineage_key": key,
                    "position": [x, y],
                    "crop": crop,
                    "planted_day": pd,
                    "yield_units": int(tile.get("yield_units", 0) or 0),
                }
    return out


def inventory_total(obs: Dict[str, Any], item: str) -> int:
    private = obs.get("private", {}) or {}
    total = 0
    shed = private.get("shed", {}) or {}
    total += int(shed.get(item, 0) or 0)
    for inv in private.get("inventories", []) or []:
        if isinstance(inv, dict):
            total += int(inv.get(item, 0) or 0)
    return total


def state_seed_stock(obs: Dict[str, Any]) -> Dict[str, int]:
    private = obs.get("private", {}) or {}
    seeds = private.get("seeds", {}) or {}
    return {
        crop: int(seeds.get(crop, 0) or 0)
        for crop in kg.CROPS
        if int(seeds.get(crop, 0) or 0)
    }


def extract_replay(env) -> List[List[Dict[str, Any]]]:
    out = []
    for step in getattr(env, "steps", []) or []:
        row = []
        for p in (0, 1):
            s = step[p]
            row.append(
                {
                    "observation": plain(getattr(s, "observation", None)),
                    "action": plain(getattr(s, "action", None)),
                    "reward": plain(getattr(s, "reward", None)),
                    "status": plain(getattr(s, "status", None)),
                }
            )
        out.append(row)
    return out


def canonical_action(action: Any) -> str:
    return json.dumps(action or {}, sort_keys=True, separators=(",", ":"))


def self_action_trace(steps, seat: int) -> List[Dict[str, Any]]:
    out = []
    for idx, step in enumerate(steps):
        obs = step[seat].get("observation", {}) or {}
        out.append(
            {
                "step_index": idx,
                "day": int(obs.get("day", 0) or 0),
                "hour": int(obs.get("hour", 0) or 0),
                "action": step[seat].get("action") or {},
            }
        )
    return out


def action_hash(trace) -> str:
    canonical = json.dumps(
        [x["action"] for x in trace],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def first_action_difference(a, b):
    n = min(len(a), len(b))
    for idx in range(n):
        if canonical_action(a[idx]["action"]) != canonical_action(b[idx]["action"]):
            return {
                "step_index": idx,
                "day_a": a[idx]["day"],
                "hour_a": a[idx]["hour"],
                "day_b": b[idx]["day"],
                "hour_b": b[idx]["hour"],
                "action_a": a[idx]["action"],
                "action_b": b[idx]["action"],
            }
    if len(a) != len(b):
        return {"step_index": n, "length_a": len(a), "length_b": len(b)}
    return None


def plant_harvest_audit(steps, seat: int) -> Dict[str, Any]:
    activations: Dict[str, Dict[str, Any]] = {}
    harvests: Dict[str, Dict[str, Any]] = {}

    previous = None
    for idx, step in enumerate(steps):
        obs = step[seat].get("observation", {}) or {}
        current = tile_map(obs, seat)

        if previous is not None:
            for key, tile in current.items():
                if key not in previous and tile["planted_day"] >= probe.D14_START_DAY:
                    activations.setdefault(
                        key,
                        {
                            **tile,
                            "activation_step": idx,
                            "activation_day": int(obs.get("day", 0) or 0),
                            "activation_hour": int(obs.get("hour", 0) or 0),
                            "rule_first_yield_day": int(
                                kg.CROPS[tile["crop"]]["first_yield_day"]
                            ),
                            "rule_earliest_harvest_day": tile["planted_day"]
                            + int(kg.CROPS[tile["crop"]]["first_yield_day"]),
                        },
                    )

            action = step[seat].get("action") or {}
            unit_actions = []
            farmer = action.get("farmer")
            if isinstance(farmer, list) and farmer:
                unit_actions.append(farmer)
            for x in action.get("hands", []) or []:
                if isinstance(x, list) and x:
                    unit_actions.append(x)
            harvest_requested = any(x[0] == "HARVEST" for x in unit_actions)

            if harvest_requested:
                for key, tile in previous.items():
                    now = current.get(key)
                    if now is None or now.get("yield_units", 0) < tile.get("yield_units", 0):
                        if key in activations and key not in harvests:
                            harvests[key] = {
                                "step_index": idx,
                                "day": int(obs.get("day", 0) or 0),
                                "hour": int(obs.get("hour", 0) or 0),
                            }

        previous = current

    terminal_obs = steps[-1][seat].get("observation", {}) or {}
    terminal_tiles = tile_map(terminal_obs, seat)

    by_crop = {}
    crops = sorted({x["crop"] for x in activations.values()})
    for crop in crops:
        keys = [k for k, x in activations.items() if x["crop"] == crop]
        by_crop[crop] = {
            "activated": len(keys),
            "harvested": sum(1 for k in keys if k in harvests),
            "still_present_terminal": sum(1 for k in keys if k in terminal_tiles),
            "rule_harvest_after_terminal": sum(
                1
                for k in keys
                if activations[k]["rule_earliest_harvest_day"]
                > probe.LAST_PLAYABLE_DAY
            ),
        }

    late = [x for x in activations.values() if x["planted_day"] >= 20]
    late_keys = {x["lineage_key"] for x in late}

    return {
        "post_d14_activated": len(activations),
        "post_d14_harvested": sum(1 for k in activations if k in harvests),
        "post_d14_by_crop": by_crop,
        "day20_plus_activated": len(late),
        "day20_plus_harvested": sum(1 for k in late_keys if k in harvests),
        "day20_plus_rule_after_terminal": sum(
            1
            for x in late
            if x["rule_earliest_harvest_day"] > probe.LAST_PLAYABLE_DAY
        ),
        "terminal_seed_stock": state_seed_stock(terminal_obs),
        "terminal_crop_tiles": Counter(
            x["crop"] for x in terminal_tiles.values()
        ),
        "late_lineages": sorted(
            [
                {
                    **x,
                    "harvest": harvests.get(x["lineage_key"]),
                    "still_present_terminal": x["lineage_key"] in terminal_tiles,
                }
                for x in late
            ],
            key=lambda z: (
                z["planted_day"],
                z["activation_step"],
                z["lineage_key"],
            ),
        ),
    }


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def play(seed: int, seat: int, mode: str) -> Dict[str, Any]:
    configure()
    probe.set_mode(mode)
    probe.reset_telemetry()

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[seat] = probe.agent
    env.run(players)

    rewards = [float(x.reward) for x in env.state]
    steps = extract_replay(env)
    trace = self_action_trace(steps, seat)
    telemetry = probe.get_telemetry()

    # Retain detailed Seed decisions but avoid duplicating body telemetry noise.
    filter_summary = {
        "mode": mode,
        "turns": telemetry.get("turns"),
        "changed_turns": telemetry.get("changed_turns"),
        "removed_orders": telemetry.get("removed_orders"),
        "native_seed_requests_after_d14": telemetry.get(
            "native_seed_requests_after_d14"
        ),
        "seed_requests_allowed_after_d14": telemetry.get(
            "seed_requests_allowed_after_d14"
        ),
        "seed_requests_suppressed_after_d14": telemetry.get(
            "seed_requests_suppressed_after_d14"
        ),
        "seed_decisions": telemetry.get("seed_decisions", []),
    }

    return {
        "mode": mode,
        "terminal": {
            "self": rewards[seat],
            "opponent": rewards[1 - seat],
            "margin": rewards[seat] - rewards[1 - seat],
        },
        "filter": filter_summary,
        "action_hash": action_hash(trace),
        "action_trace": trace,
        "physical": plant_harvest_audit(steps, seat),
    }


def compact_arm(arm: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mode": arm["mode"],
        "terminal": arm["terminal"],
        "filter": arm["filter"],
        "action_hash": arm["action_hash"],
        "physical": arm["physical"],
    }


def main():
    cases = []
    for seed, seat in CASES:
        arms = {mode: play(seed, seat, mode) for mode in MODES}

        # On the exact Current-D14 path, ask what C would have done with every
        # native post-D14 seed request. This is a pure representation check,
        # before B/C path divergence can change later native requests.
        a_shadow = []
        for d in arms["A"]["filter"]["seed_decisions"]:
            h = probe.harvest_feasibility(
                {"day": d["day"], "hour": d["hour"]},
                d["crop"],
            )
            a_shadow.append(
                {
                    "day": d["day"],
                    "hour": d["hour"],
                    "crop": d["crop"],
                    "order": d["order"],
                    "b_would_allow": True,
                    "c_would_allow": h["allowed"],
                    "c_earliest_plant_day": h.get("earliest_plant_day"),
                    "c_earliest_harvest_day": h.get("earliest_harvest_day"),
                }
            )

        cases.append(
            {
                "seed": seed,
                "seat": seat,
                "arms": {k: compact_arm(v) for k, v in arms.items()},
                "current_path_shadow_seed_decisions": a_shadow,
                "first_action_difference": {
                    "A_vs_B": first_action_difference(
                        arms["A"]["action_trace"], arms["B"]["action_trace"]
                    ),
                    "B_vs_C": first_action_difference(
                        arms["B"]["action_trace"], arms["C"]["action_trace"]
                    ),
                    "A_vs_C": first_action_difference(
                        arms["A"]["action_trace"], arms["C"]["action_trace"]
                    ),
                },
            }
        )

    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    aggregate = {}
    for mode in MODES:
        vals = [c["arms"][mode] for c in cases]
        aggregate[mode] = {
            "terminal_self_mean": mean([x["terminal"]["self"] for x in vals]),
            "terminal_margin_mean": mean([x["terminal"]["margin"] for x in vals]),
            "native_seed_requests_after_d14": sum(
                int(x["filter"]["native_seed_requests_after_d14"] or 0)
                for x in vals
            ),
            "seed_requests_allowed_after_d14": sum(
                int(x["filter"]["seed_requests_allowed_after_d14"] or 0)
                for x in vals
            ),
            "seed_requests_suppressed_after_d14": sum(
                int(x["filter"]["seed_requests_suppressed_after_d14"] or 0)
                for x in vals
            ),
            "post_d14_activated": sum(
                x["physical"]["post_d14_activated"] for x in vals
            ),
            "post_d14_harvested": sum(
                x["physical"]["post_d14_harvested"] for x in vals
            ),
            "day20_plus_activated": sum(
                x["physical"]["day20_plus_activated"] for x in vals
            ),
            "day20_plus_harvested": sum(
                x["physical"]["day20_plus_harvested"] for x in vals
            ),
            "day20_plus_rule_after_terminal": sum(
                x["physical"]["day20_plus_rule_after_terminal"] for x in vals
            ),
        }

    def paired_delta(left: str, right: str, key: str):
        ds = [
            c["arms"][right]["terminal"][key]
            - c["arms"][left]["terminal"][key]
            for c in cases
        ]
        return {
            "mean": mean(ds),
            "improved": sum(1 for x in ds if x > 0),
            "worse": sum(1 for x in ds if x < 0),
            "equal": sum(1 for x in ds if x == 0),
            "by_case": ds,
        }

    result = {
        "schema": "kaggriculture.seed-horizon-isolation.fresh10.result.v0",
        "cases": cases,
        "aggregate": aggregate,
        "paired_terminal_delta": {
            "B_minus_A_self": paired_delta("A", "B", "self"),
            "C_minus_B_self": paired_delta("B", "C", "self"),
            "C_minus_A_self": paired_delta("A", "C", "self"),
            "B_minus_A_margin": paired_delta("A", "B", "margin"),
            "C_minus_B_margin": paired_delta("B", "C", "margin"),
            "C_minus_A_margin": paired_delta("A", "C", "margin"),
        },
        "probe0": {
            "cases_A_vs_B_action_diverged": sum(
                1 for c in cases
                if c["first_action_difference"]["A_vs_B"] is not None
            ),
            "cases_B_vs_C_action_diverged": sum(
                1 for c in cases
                if c["first_action_difference"]["B_vs_C"] is not None
            ),
            "current_path_seed_requests_where_C_differs_from_B": sum(
                1
                for c in cases
                for d in c["current_path_shadow_seed_decisions"]
                if not d["c_would_allow"]
            ),
        },
        "boundary": [
            "A/B/C share the same Frozen Body and differ only in the D14 market filter.",
            "C uses public-rule earliest HARVEST eligibility, not Cash-return reachability.",
            "Because unit actions execute before market, same-turn seed purchase cannot satisfy same-turn PLANT.",
            "Physical plant/harvest audit is actual-path observation; it does not token-attribute a harvested crop to one specific restored seed purchase.",
            "Terminal differences are Battle outcomes, not proof that Remaining Horizon is the sole cause.",
            "World context is logged by the environment but is not used by the C gate in this probe.",
        ],
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "SEED_HORIZON_FRESH10 "
        + json.dumps(
            {
                "aggregate": aggregate,
                "paired_terminal_delta": result["paired_terminal_delta"],
                "probe0": result["probe0"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
