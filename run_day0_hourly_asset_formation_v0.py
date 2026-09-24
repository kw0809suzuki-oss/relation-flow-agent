#!/usr/bin/env python3
"""Day0 Hourly Asset Formation Localization v0.

Refines only the confirmed first World gap: equal starting land -> different
productive asset occupancy during Day0. Hourly World snapshots through Day1 h0.
No Action observation.
"""
import json
import os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body_only
import run_asset_formation_map_v0 as af

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"day0_hourly_asset_formation_v0_{SEED}_seat{SEAT}.json")


def main():
    af.configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[SEAT] = body_only.agent
    env.run(players)

    checkpoints = []
    seen = set()
    for step in getattr(env, "steps", []) or []:
        if not isinstance(step, (list, tuple)) or len(step) < 2:
            continue
        so = af.plain(af.getv(step[SEAT], "observation"))
        oo = af.plain(af.getv(step[1 - SEAT], "observation"))
        if not isinstance(so, dict) or not isinstance(oo, dict):
            continue
        day = int(so.get("day", 0) or 0)
        hour = int(so.get("hour", 0) or 0)
        if not (day == 0 or (day == 1 and hour == 0)):
            continue
        key = (day, hour)
        if key in seen:
            continue
        seen.add(key)

        sides = {}
        for label, obs, pidx in (("self", so, SEAT), ("opponent", oo, 1 - SEAT)):
            farms = obs.get("farms", []) or []
            farm = farms[pidx] if pidx < len(farms) else {}
            instances = []
            for y, row in enumerate(farm.get("tiles", []) or []):
                for x, tile in enumerate(row or []):
                    z = af.asset_instance(tile, x, y, day)
                    if z is not None:
                        instances.append(z)
            sides[label] = {
                "land": af.land_context(farm),
                "summary_by_type": af.summarize(instances),
            }
        checkpoints.append({"day": day, "hour": hour, **sides})

    rewards = [float(x.reward) for x in env.state]
    payload = {
        "schema": "kaggriculture.strong-origin-v2.day0-hourly-asset-formation.v0",
        "seed": SEED,
        "seat": SEAT,
        "checkpoints": checkpoints,
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "boundary": [
            "This probe refines only the already-confirmed Day0->1 World gap.",
            "Hourly snapshots contain land and productive asset State only.",
            "No Action, order, movement, worker, policy, motive, Candidate, or causal explanation is observed.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DAY0_HOURLY_ASSET_FORMATION " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "checkpoint_count": len(checkpoints),
        "terminal": payload["terminal"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
