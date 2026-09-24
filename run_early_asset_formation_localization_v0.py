#!/usr/bin/env python3
"""Early Asset Formation Localization v0.

Refines only the first coarse Asset Formation interval: Day0 -> Day8.
Daily h0 snapshots, same five fixed Battles, same World-only fields as
Asset Formation Map v0. No Action or policy observation.
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
OUT = Path(f"early_asset_formation_localization_v0_{SEED}_seat{SEAT}.json")
DAYS = tuple(range(0, 9))


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
        if day not in DAYS or hour != 0 or day in seen:
            continue
        seen.add(day)

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
        "schema": "kaggriculture.strong-origin-v2.early-asset-formation-localization.v0",
        "seed": SEED,
        "seat": SEAT,
        "days": list(DAYS),
        "checkpoints": checkpoints,
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "boundary": [
            "This probe only refines the already-selected coarse interval Day0->8.",
            "It reuses the same World-side Asset Formation definitions without adding new concepts.",
            "No Action, movement, worker, purchase, policy, Candidate, or causal explanation is observed.",
            "Unlike asset types remain separate.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("EARLY_ASSET_FORMATION_LOCALIZATION " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "days": [c["day"] for c in checkpoints],
        "terminal": payload["terminal"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
