#!/usr/bin/env python3
"""Observe both players on Day29 for Open Learning seed 6205.

No intervention. Compare action/value realization at the largest relative-gap jump.
"""
import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED=6205
SEAT=0
DAY=29
OPPONENT_PATH=Path("opponents/seyamalam_v21.py")
OUT=Path("open_learning_day29_dual_observation_v0.json")


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def load_opponent():
    spec=importlib.util.spec_from_file_location("seyamalam_v21_runtime", OPPONENT_PATH)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn=getattr(mod,"agent",None)
    if not callable(fn):
        raise RuntimeError("opponent agent callable not found")
    return fn


def compact_action(a):
    if isinstance(a,dict):
        return {
            "market":list(a.get("market",[]) or []),
            "farm":list(a.get("farm",[]) or []),
        }
    return a


def main():
    configure()
    opp_agent=load_opponent()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    trace={0:[],1:[]}

    def wrap(player_index, fn):
        def wrapped(obs):
            action=fn(obs)
            if int(obs.get("day",0) or 0)==DAY:
                farm=obs["farms"][player_index]
                market=(obs.get("market",{}) or {}).get("prices",{}) or {}
                trace[player_index].append({
                    "call":len(trace[player_index])+1,
                    "money_before":float(farm.get("money",0.0)),
                    "market_prices":{k:v for k,v in market.items() if isinstance(v,(int,float))},
                    "action":compact_action(action),
                })
            return action
        return wrapped

    players=[None,None]
    players[SEAT]=wrap(SEAT,combat.agent)
    players[1-SEAT]=wrap(1-SEAT,opp_agent)
    env.run(players)
    rewards=[float(x.reward) for x in env.state]

    summary={}
    for p in (0,1):
        rows=trace[p]
        market_actions=[]
        farm_actions=[]
        for r in rows:
            a=r["action"]
            if isinstance(a,dict):
                market_actions.extend(a.get("market",[]) or [])
                farm_actions.extend(a.get("farm",[]) or [])
        summary[str(p)]={
            "calls":len(rows),
            "first_money_before":rows[0]["money_before"] if rows else None,
            "last_money_before":rows[-1]["money_before"] if rows else None,
            "market_actions":market_actions,
            "farm_actions":farm_actions,
            "first_prices":rows[0]["market_prices"] if rows else {},
            "last_prices":rows[-1]["market_prices"] if rows else {},
        }

    payload={
        "schema":"kaggriculture.open-learning-day29-dual-observation.v0",
        "case":{"seed":SEED,"self_seat":SEAT,"day":DAY},
        "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
        "summary":summary,
        "boundary":[
            "Observation only; no action is changed.",
            "Day29 was selected because it had the largest observed relative money-gap growth.",
            "Action frequency is descriptive and does not establish causal value."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OPEN_LEARNING_DAY29_DUAL "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
