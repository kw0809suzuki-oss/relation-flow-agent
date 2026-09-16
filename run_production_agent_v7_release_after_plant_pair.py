#!/usr/bin/env python3
"""Fresh10 replication: v7 release-after-plant vs v6 Bridge1.
Bundle is comparison-only. Terminal is applied after observation.
"""
import copy, json, statistics
from collections import Counter
from pathlib import Path
from kaggle_environments import make
import production_agent_v6_bridge1 as baseline_agent
import production_agent_v7_release_after_plant as candidate_agent

OPPONENT="opponents/seyamalam_v21.py"
CASES=tuple((seed,(seed-4092)%2) for seed in range(4092,4102))
MAINT={"NORTH","SOUTH","EAST","WEST","WATER","FEED","CARE","PICKUP","DROP"}
PROD={"PLANT","HARVEST","PLACE","BUILD_PASTURE","COLLECT_FERTILIZER","DIG"}

def score(rewards,seat):
    own=float(rewards[seat]); opp=float(rewards[1-seat])
    return {"self":own,"opponent":opp,"margin":own-opp,"win":own>opp}

def public_bundle(obs,seat):
    farm=obs["farms"][seat]; animals=Counter(); active=planted=0
    for row in farm.get("tiles",[]) or []:
        for tile in row:
            if tile in (None,"LOCKED"): continue
            active+=1
            if isinstance(tile,dict):
                if tile.get("animal"): animals[str(tile.get("animal"))]+=1
                if tile.get("crop") or tile.get("plant") or tile.get("kind")=="PLANT": planted+=1
    return {"money":farm.get("money",0),"hands":len(farm.get("hands",[]) or []),"land":len(farm.get("unlocked_quadrants",[]) or []),"active_tiles":active,"planted_tiles":planted,"animals":dict(animals),"animal_total":sum(animals.values())}

def classify(action,allocation,detail):
    units=[action.get("farmer",["PASS"])]+list(action.get("hands",[]) or [])
    for a in units:
        if not a: continue
        k=str(a[0]); detail[k]+=1
        if k in MAINT: allocation["maintenance"]+=1
        elif k in PROD: allocation["production"]+=1
    for o in action.get("market",[]) or []:
        if not o: continue
        k=str(o[0]); detail[f"MKT_{k}"]+=1
        if k in {"BUY_LAND","HIRE","BUY_ANIMAL","BUY_PRODUCT","BUY_SEED"}: allocation["investment"]+=1
        elif k=="SELL": allocation["realization"]+=1

def play(seed,seat,module):
    module.reset_telemetry(); allocation=Counter(); detail=Counter(); days={}
    def wrapped(obs):
        day=int(obs.get("day",0)); rec=days.setdefault(day,{})
        rec["self"]=public_bundle(obs,seat); rec["opponent"]=public_bundle(obs,1-seat)
        action=module.agent(obs); classify(action,allocation,detail); return action
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    players=[OPPONENT,OPPONENT]; players[seat]=wrapped; env.run(players)
    rewards=[state.reward for state in env.state]
    return {"terminal":score(rewards,seat),"allocation":dict(allocation),"detail":dict(detail),"bundle":[{"day":d,**days[d]} for d in sorted(days)],"telemetry":copy.deepcopy(module.get_telemetry())}

def main():
    rows=[]
    for seed,seat in CASES:
        base=play(seed,seat,baseline_agent); cand=play(seed,seat,candidate_agent)
        rows.append({"seed":seed,"seat":seat,"baseline":base,"candidate":cand,
            "self_delta":cand["terminal"]["self"]-base["terminal"]["self"],
            "margin_delta":cand["terminal"]["margin"]-base["terminal"]["margin"],
            "maintenance_delta":cand["allocation"].get("maintenance",0)-base["allocation"].get("maintenance",0),
            "production_delta":cand["allocation"].get("production",0)-base["allocation"].get("production",0),
            "realization_delta":cand["allocation"].get("realization",0)-base["allocation"].get("realization",0)})
    def stats(key):
        vals=[r[key] for r in rows]
        return {"mean":statistics.mean(vals),"median":statistics.median(vals),"positive":sum(v>0 for v in vals),"negative":sum(v<0 for v in vals),"zero":sum(v==0 for v in vals)}
    summary={"cases":len(rows),"self_delta":stats("self_delta"),"margin_delta":stats("margin_delta"),"maintenance_delta":stats("maintenance_delta"),"production_delta":stats("production_delta"),"realization_delta":stats("realization_delta"),"baseline_wins":sum(r["baseline"]["terminal"]["win"] for r in rows),"candidate_wins":sum(r["candidate"]["terminal"]["win"] for r in rows)}
    out={"schema":"kaggriculture.production-v7-release-after-plant-pair.v1","baseline":"production_agent_v6_bridge1.py","candidate":"production_agent_v7_release_after_plant.py","design_unit":"Bridge1: release after PLANT; first WATER returns to normal scheduler","observation_boundary":{"bundle_comparison_only":True,"bundle_semantics_added":False,"bundle_used_for_control":False,"terminal_applied_after_observation":True,"causal_attribution":False},"cases":rows,"summary":summary}
    Path("production_agent_v7_release_after_plant_pair_result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("PRODUCTION_V7_RELEASE_AFTER_PLANT_PAIR "+json.dumps(summary,separators=(",",":")))
if __name__=="__main__": main()
