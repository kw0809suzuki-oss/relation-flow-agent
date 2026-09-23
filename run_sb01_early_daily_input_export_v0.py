#!/usr/bin/env python3
"""SB-01 Early Daily State export v0.

Exact SB-01 policy/runtime, no Candidate and no agent wrapper.
After env.run(), export the first retained observation for Day 0..6 for both seats.
This is calculation input only.
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
TARGET_DAYS = tuple(range(0, 7))
OUT = Path(f"sb01_early_daily_input_{SEED}.json")


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
            if day not in TARGET_DAYS:
                continue
            key = str(day)
            if key not in snapshots[str(seat)]:
                snapshots[str(seat)][key] = {
                    "step_index": step_index,
                    "observation": obs,
                }

    audit = {}
    for seat in (0, 1):
        rows = snapshots[str(seat)]
        audit[str(seat)] = {
            "target_days_found": sorted(int(k) for k in rows),
            "all_days_found": len(rows) == len(TARGET_DAYS),
            "private_present_all": all(
                bool((entry.get("observation") or {}).get("private"))
                for entry in rows.values()
            ) and len(rows) == len(TARGET_DAYS),
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
        "schema": "kaggriculture.sb01.early-daily-input.v0",
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
            "opponent": rewards[1-SEAT],
            "margin": rewards[SEAT] - rewards[1-SEAT],
        },
        "state_export": state_export,
        "export_audit": audit,
        "boundary": [
            "Exact SB-01 policy/runtime configuration is reused.",
            "No Candidate, threshold, strategy rule, Action change, or agent wrapper is added.",
            "State is read only after env.run() from environment-retained observations.",
            "Exported State is calculation input, not explanation.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print("SB01_EARLY_DAILY_INPUT " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "terminal": payload["terminal_result"],
        "audit": audit,
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
