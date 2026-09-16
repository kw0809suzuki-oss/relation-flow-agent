#!/usr/bin/env python3
"""Observation-only fresh10 run for Production v3.

Views the same trajectories through two comparison surfaces:
1) action allocation: investment / maintenance / production / realization
2) existing Bundle-style daily snapshots
No observation value is fed back into control.
"""

import json
from collections import Counter
from pathlib import Path
from kaggle_environments import make
import production_agent_v3_expansion_bridge as body

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, i % 2) for i, seed in enumerate(range(4052, 4062)))


def public(farm):
    animals = Counter(); active = planted = 0
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if tile in (None, "LOCKED"): continue
            active += 1
            if isinstance(tile, dict):
                if tile.get("animal"): animals[str(tile.get("animal"))] += 1
                if tile.get("crop") or tile.get("plant"): planted += 1
    return {"money": farm.get("money",0), "hands": len(farm.get("hands",[]) or []),
            "land": len(farm.get("unlocked_quadrants",[]) or []), "active_tiles": active,
            "planted_tiles": planted, "animals": dict(animals), "animal_total": sum(animals.values())}


def action_surface(action):
    c = Counter()
    for o in action.get("market",[]) or []:
        if not o: continue
        k=o[0]
        if k in {"BUY_LAND","HIRE","BUY_ANIMAL","BUY_PRODUCT","BUY_SEED"}: c["investment"] += 1
        elif k == "SELL": c["realization"] += 1
    units=[action.get("farmer",["PASS"]), *(action.get("hands",[]) or [])]
    for a in units:
        if not a: continue
        k=a[0]
        if k in {"NORTH","SOUTH","EAST","WEST","WATER","FEED","CARE","PICKUP","DROP"}: c["maintenance"] += 1
        elif k in {"DIG","PLANT","HARVEST","PLACE","BUILD_PASTURE","COLLECT_FERTILIZER"}: c["production"] += 1
    return c


def play(seed, seat):
    body.reset_telemetry()
    allocation=Counter(); days={}; turn=0
    def wrapped(obs):
        nonlocal turn
        day=int(obs.get("day",0)); player=int(obs["player"])
        rec=days.setdefault(day,{"day":day,"last":None,"actions":Counter()})
        rec["last"]={"turn":turn,"self":public(obs["farms"][player]),"opponent":public(obs["farms"][1-player])}
        action=body.agent(obs)
        s=action_surface(action); allocation.update(s); rec["actions"].update(s)
        turn += 1
        return action
    env=make("kaggriculture", configuration={"seed":seed}, debug=False)
    players=[OPPONENT,OPPONENT]; players[seat]=wrapped; env.run(players)
    rewards=[state.reward for state in env.state]
    bundle=[{"day":d,"snapshot":days[d]["last"],"actions":dict(days[d]["actions"])} for d in sorted(days)]
    return {"seed":seed,"seat":seat,"allocation":dict(allocation),"bundle":bundle,
            "terminal":{"self":float(rewards[seat]),"opponent":float(rewards[1-seat]),"margin":float(rewards[seat]-rewards[1-seat])}}


def main():
    cases=[play(seed,seat) for seed,seat in CASES]
    totals=Counter()
    for c in cases: totals.update(c["allocation"])
    total=sum(totals.values()) or 1
    summary={"cases":len(cases),"allocation_totals":dict(totals),
             "allocation_share":{k:totals[k]/total for k in ("investment","maintenance","production","realization")}}
    out={"schema":"kaggriculture.v3-balance-bundle-observation.v1",
         "body":"production_agent_v3_expansion_bridge.py",
         "observation_only":True,"bundle_semantics_added":False,"bundle_used_for_control":False,
         "terminal_applied_after_observation":True,"summary":summary,"cases":cases}
    Path("v3_balance_bundle_observation.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("V3_BALANCE_BUNDLE_OBSERVATION "+json.dumps(summary,separators=(",",":")))

if __name__=="__main__": main()
