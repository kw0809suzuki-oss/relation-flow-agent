#!/usr/bin/env python3
"""External asset-curve comparison v0.

Battle-first, outside view only.
Compare Current Combat Model, Seyamalam v21, and lonespear v18 on the same
fresh10 seeds. Record daily public/basic asset state; no internal traces.
"""

import json
import os
import statistics
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as current

SEYAMALAM = "opponents/seyamalam_v21.py"
LONESPEAR = "opponents/lonespear_v18.py"
CASES = [(4602 + i, i % 2) for i in range(10)]
OUT = Path("external_asset_curve_compare_v0.json")


def configure_current():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    current.set_control_enabled(False)
    current.set_probe_enabled(True)
    current.set_attribution_enabled(True)
    current.reset_telemetry()


def public_asset_state(obs):
    me = obs["farms"][obs["player"]]
    plants = 0
    animals = 0
    unlocked_tiles = 0
    for row in me.get("tiles", []):
        for tile in row:
            if tile != "LOCKED":
                unlocked_tiles += 1
            if isinstance(tile, dict):
                if tile.get("kind") == "PLANT":
                    plants += 1
                if tile.get("animal"):
                    animals += 1
    return {
        "money": float(me.get("money", 0)),
        "land": int(len(me.get("unlocked_quadrants", []))),
        "hands": int(len(me.get("hands", []))),
        "animals": int(animals),
        "productive_tiles": int(plants + animals),
        "unlocked_tiles": int(unlocked_tiles),
    }


def play(agent_kind, seed, seat):
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    daily = {}

    if agent_kind == "current":
        configure_current()
        def observed(obs):
            daily[int(obs["day"])] = public_asset_state(obs)
            return current.agent(obs)
        player = observed
    elif agent_kind == "seyamalam":
        module = env.agents[SEYAMALAM] if False else None
        # File-path agents cannot be wrapped directly, so load by exec into namespace.
        ns = {}
        exec(Path(SEYAMALAM).read_text(encoding="utf-8"), ns)
        fn = ns["agent"]
        def observed(obs):
            daily[int(obs["day"])] = public_asset_state(obs)
            return fn(obs)
        player = observed
    elif agent_kind == "lonespear":
        ns = {}
        exec(Path(LONESPEAR).read_text(encoding="utf-8"), ns)
        fn = ns["agent"]
        def observed(obs):
            daily[int(obs["day"])] = public_asset_state(obs)
            return fn(obs)
        player = observed
    else:
        raise ValueError(agent_kind)

    players = [SEYAMALAM, SEYAMALAM]
    players[seat] = player
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    own = rewards[seat]
    opp = rewards[1-seat]
    return {
        "seed": seed,
        "seat": seat,
        "terminal_self": own,
        "terminal_opponent": opp,
        "margin": own-opp,
        "win_loss": "win" if own>opp else "loss" if own<opp else "draw",
        "daily": daily,
    }


def mean_daily(rows):
    days = sorted({int(d) for r in rows for d in r["daily"]})
    fields = ["money","land","hands","animals","productive_tiles","unlocked_tiles"]
    out = {}
    for d in days:
        vals = {f: [] for f in fields}
        for r in rows:
            state = r["daily"].get(d) or r["daily"].get(str(d))
            if state is None:
                continue
            for f in fields:
                vals[f].append(float(state[f]))
        out[str(d)] = {
            f: (sum(vals[f])/len(vals[f]) if vals[f] else None)
            for f in fields
        }
    return out


def summary(rows):
    selfs=[r["terminal_self"] for r in rows]
    margins=[r["margin"] for r in rows]
    return {
        "mean_self":sum(selfs)/len(selfs),
        "median_self":statistics.median(selfs),
        "min_self":min(selfs),
        "max_self":max(selfs),
        "mean_margin":sum(margins)/len(margins),
        "wins":sum(r["win_loss"]=="win" for r in rows),
        "losses":sum(r["win_loss"]=="loss" for r in rows),
    }


def main():
    all_rows={}
    for kind in ("current","seyamalam","lonespear"):
        rows=[play(kind,seed,seat) for seed,seat in CASES]
        all_rows[kind]=rows

    payload={
        "schema":"kaggriculture.external-asset-curve-compare.v0",
        "purpose":"outside-view comparison of 30-day asset trajectories",
        "agents":{
            "current":"Current Combat Model frozen baseline",
            "seyamalam":"Seyamalam v21 fixed public agent",
            "lonespear":"lonespear main/v18 at pinned commit 774b26093ccf4246525517d48420349b841b6e50",
        },
        "measurement":"latest public observation seen on each in-game day",
        "cases":all_rows,
        "terminal_summary":{k:summary(v) for k,v in all_rows.items()},
        "mean_daily_curve":{k:mean_daily(v) for k,v in all_rows.items()},
        "analysis_boundary":"No internal trace or causal interpretation.",
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("EXTERNAL_ASSET_CURVE_TERMINAL "+json.dumps(payload["terminal_summary"],separators=(",",":")))
    print("EXTERNAL_ASSET_CURVE_MEAN_DAILY "+json.dumps(payload["mean_daily_curve"],separators=(",",":")))


if __name__=="__main__":
    main()
