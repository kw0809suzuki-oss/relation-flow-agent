#!/usr/bin/env python3
"""High-Leverage Harvest Timing Bundle v0.

Current G17 baseline vs late-window immediate-harvest variants:
H18 / H22 / H24 = from that day onward, if a worker is already standing on
a plant with yield_units > 0, force HARVEST. Otherwise preserve native action.

External timing sweep only. No causal claim. No auto-adoption.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as native

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"high_leverage_harvest_timing_v0_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    native.set_probe_enabled(True)
    native.set_attribution_enabled(True)
    native.reset_telemetry()

def harvestable(tile):
    return isinstance(tile,dict) and tile.get("kind")=="PLANT" and float(tile.get("yield_units",0) or 0)>0

def play(start_day=None):
    configure()
    events=[]
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    def agent(obs):
        actions=native.agent(obs)
        if start_day is None or not isinstance(actions,dict):
            return actions
        day=int(obs.get("day",0) or 0)
        if day<start_day:
            return actions
        p=int(obs["player"]); me=obs["farms"][p]; tiles=me.get("tiles",[]) or []
        revised=copy.deepcopy(actions); changed=[]

        farmer=me.get("farmer")
        if isinstance(farmer,(list,tuple)) and len(farmer)>=2:
            x,y=farmer[0],farmer[1]
            if 0<=y<len(tiles) and 0<=x<len(tiles[y]) and harvestable(tiles[y][x]):
                if revised.get("farmer")!=["HARVEST"]:
                    revised["farmer"]=["HARVEST"]; changed.append("farmer")

        hand_actions=list(revised.get("hands",[]) or [])
        positions=me.get("hands",[]) or []
        for i,pos in enumerate(positions):
            if i>=len(hand_actions) or not isinstance(pos,(list,tuple)) or len(pos)<2:
                continue
            x,y=pos[0],pos[1]
            if 0<=y<len(tiles) and 0<=x<len(tiles[y]) and harvestable(tiles[y][x]):
                if hand_actions[i]!=["HARVEST"]:
                    hand_actions[i]=["HARVEST"]; changed.append(f"hand_{i}")
        revised["hands"]=hand_actions
        if changed: events.append({"day":day,"units":changed})
        return revised
    players=[OPPONENT,OPPONENT]; players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],
            "event_count":len(events),"event_days":sorted({e["day"] for e in events})}

def main():
    b=play(None)
    variants={}
    for name,day in (("H18",18),("H22",22),("H24",24)):
        r=play(day)
        variants[name]={**r,"diff_self":r["self"]-b["self"],"diff_margin":r["margin"]-b["margin"]}
    payload={
      "schema":"kaggriculture.high-leverage.harvest-timing.bundle.v0",
      "seed":SEED,"seat":SEAT,"baseline":b,"variants":variants,
      "boundary":[
        "Same native G17 baseline, seed, seat, opponent and runtime config.",
        "Only late-window immediate harvest timing changes.",
        "Magnitude / Direction / Robustness screening only.",
        "No causal claim and no auto-adoption."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("HIGH_LEVERAGE_HARVEST_TIMING_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
