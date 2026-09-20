#!/usr/bin/env python3
"""LAND coarse prestate observer for High-Leverage Search.

Replays the same fresh10 (7101-7110) and records only observable outer state
immediately before the first native BUY_LAND, together with terminal effect of
suppressing that one purchase.

No causal attribution. No rescue conditions.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as native

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"land_coarse_prestate_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    native.set_probe_enabled(True)
    native.set_attribution_enabled(True)
    native.reset_telemetry()

def count_animals(farm):
    c=0
    for row in farm.get("tiles",[]) or []:
        for tile in row or []:
            if isinstance(tile,dict) and tile.get("animal"):
                c+=1
    return c

def outer_state(obs):
    p=int(obs["player"])
    me=obs["farms"][p]
    opp=obs["farms"][1-p]
    tiles=[]
    for row in me.get("tiles",[]) or []:
        for tile in row or []:
            if tile!="LOCKED" and tile is not None:
                tiles.append(tile)
    occupied=sum(1 for t in tiles if isinstance(t,dict) and (t.get("plant") or t.get("animal")))
    total=len(tiles)
    return {
        "day":int(obs.get("day",0) or 0),
        "money":float(me.get("money",0) or 0),
        "opponent_money":float(opp.get("money",0) or 0),
        "hands":len(me.get("hands",[]) or []),
        "animals":count_animals(me),
        "unlocked_tiles":total,
        "occupied_tiles":occupied,
        "empty_tiles":total-occupied,
        "occupancy":None if total==0 else occupied/total,
    }

def play(suppress):
    configure()
    seen=False
    pre=None
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    def agent(obs):
        nonlocal seen,pre
        actions=native.agent(obs)
        if seen or not isinstance(actions,dict):
            return actions
        market=list(actions.get("market",[]) or [])
        hit=any(isinstance(a,(list,tuple)) and a and a[0]=="BUY_LAND" for a in market)
        if not hit:
            return actions
        pre=outer_state(obs)
        seen=True
        if not suppress:
            return actions
        revised=copy.deepcopy(actions)
        revised["market"]=[a for a in market if not (isinstance(a,(list,tuple)) and a and a[0]=="BUY_LAND")]
        return revised
    players=[OPPONENT,OPPONENT]; players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"pre":pre}

def main():
    baseline=play(False)
    variant=play(True)
    row={
        "schema":"kaggriculture.high-leverage.land-coarse-prestate.v0",
        "seed":SEED,"seat":SEAT,
        "pre":variant["pre"],
        "baseline":{"self":baseline["self"],"margin":baseline["margin"]},
        "variant":{"self":variant["self"],"margin":variant["margin"]},
        "self_diff":variant["self"]-baseline["self"],
        "margin_diff":variant["margin"]-baseline["margin"],
        "direction":"improved" if variant["self"]>baseline["self"] else "worsened" if variant["self"]<baseline["self"] else "equal",
        "boundary":"outer prestate only; descriptive separator search, not causal attribution"
    }
    OUT.write_text(json.dumps(row,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LAND_COARSE_PRESTATE_RESULT "+json.dumps(row,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
