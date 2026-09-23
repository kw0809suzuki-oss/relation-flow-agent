#!/usr/bin/env python3
"""SB-01 Economic Layer raw input export v0.

Replays one fixed SB-01 benchmark case with the exact benchmark policy/runtime,
then reads environment-retained step observations AFTER env.run() and exports
the first Day 6/8/10/12 State for both seats.

This file does not add an Observer to either agent path and does not alter policy.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OPPONENT = base.OPPONENT
TARGET_DAYS = (6, 8, 10, 12)
OUT = Path(f"sb01_economic_input_export_{SEED}.json")


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def _plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "items"):
        try:
            return {str(k): _plain(v) for k, v in value.items()}
        except Exception:
            pass
    if hasattr(value, "tolist"):
        try:
            return _plain(value.tolist())
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return _plain(value.item())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {
                str(k): _plain(v)
                for k, v in vars(value).items()
                if not str(k).startswith("_")
            }
        except Exception:
            pass
    return str(value)


def _get(state, key, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    try:
        return getattr(state, key)
    except Exception:
        return default


def export_target_states(env):
    snapshots = {"0": {}, "1": {}}
    steps = getattr(env, "steps", []) or []

    for step_index, step in enumerate(steps):
        if not isinstance(step, (list, tuple)) or len(step) < 2:
            continue
        for seat in (0, 1):
            obs = _plain(_get(step[seat], "observation"))
            if not isinstance(obs, dict):
                continue
            try:
                day = int(obs.get("day", 0) or 0)
            except Exception:
                continue
            key = str(day)
            if day in TARGET_DAYS and key not in snapshots[str(seat)]:
                snapshots[str(seat)][key] = {
                    "step_index": step_index,
                    "observation": obs,
                }

    audit = {}
    for seat in (0, 1):
        rows = snapshots[str(seat)]
        audit[str(seat)] = {
            "target_days_found": sorted(int(k) for k in rows),
            "private_present_all": all(
                bool((entry.get("observation") or {}).get("private"))
                for entry in rows.values()
            ) and len(rows) == len(TARGET_DAYS),
            "observation_player_by_day": {
                day: (entry.get("observation") or {}).get("player")
                for day, entry in rows.items()
            },
        }
    return snapshots, audit, len(steps)


def main():
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[SEAT] = combat.agent
    env.run(players)

    rewards = [float(x.reward) for x in env.state]
    state_export, audit, step_count = export_target_states(env)

    payload = {
        "schema": "kaggriculture.sb01.economic-input-export.v0",
        "mode": "post_run_state_export",
        "policy_mutated": False,
        "seed": SEED,
        "seat": SEAT,
        "benchmark": "strength_benchmark_v0",
        "snapshot": "SB-01",
        "target_days": list(TARGET_DAYS),
        "env_step_count": step_count,
        "terminal_result": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "state_export": state_export,
        "export_audit": audit,
        "boundary": [
            "Exact SB-01 policy/runtime configuration is reused.",
            "No agent wrapper, Candidate, threshold, strategy rule, or Action is added.",
            "Both players execute through the same paths as the benchmark.",
            "State is read only after env.run() from environment-retained step observations.",
            "Exported State is calculation input, not interpretation.",
        ],
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        "SB01_ECONOMIC_INPUT_EXPORT "
        + json.dumps(
            {
                "seed": SEED,
                "seat": SEAT,
                "terminal": payload["terminal_result"],
                "audit": audit,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
