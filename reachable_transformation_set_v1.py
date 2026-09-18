#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent
import strong_origin

LAND={(4129,1),(4130,0),(4131,1),(4147,1),(4149,1),(4151,1),(4158,0)}
SEED={(4142,0),(4143,1),(4144,0),(4152,0),(4156,0),(4161,1)}
CASES=sorted(LAND|SEED)
OPP=base.OPPONENT
START,END=96,110

def latest_snapshot():
    tr=agent.get_trace()
    return tr["body"]["observe"]["body"]["snapshots"][-1]

def stores(private):
    return [private.get("shed",{}) or {}] + list(private.get("inventories",[]) or [])

def total_item(private,item):
    return sum(float(s.get(item,0) or 0) for s in stores(private) if isinstance(s,dict))

def classify(obs,snap):
    p=int(obs["player"]); me=obs["farms"][p]; private=obs["private"]
    day=int(obs.get("day",0)); remaining=30-day
    money=float(me.get("money",0) or 0)
    tiles=me.get("tiles",[])
    unlocked=occupied=empty=harvest_ready=growing=0
    live={"WHEAT":0,"STRAWBERRY":0,"MELON":0}
    for row in tiles:
        for tile in row:
            if tile=="LOCKED": continue
            unlocked+=1
            if tile is None:
                empty+=1
                continue
            occupied+=1
            if isinstance(tile,dict) and tile.get("kind")=="PLANT":
                crop=tile.get("crop")
                if crop in live: live[crop]+=1
                if float(tile.get("yield_units",0) or 0)>0: harvest_ready+=1
                else: growing+=1

    quadrants=len(me.get("unlocked_quadrants",[]))
    land_cost={1:1000,2:2000,3:4000}.get(quadrants)
    oi=snap.get("origin_internal",{}) or {}
    strategy_name=oi.get("strategy_name")
    strategy=strong_origin.STRATEGIES.get(strategy_name,{})
    reserve=float(strategy.get("reserve_base",0) or 0)+20*occupied
    occupancy=(occupied/unlocked) if unlocked else 1.0
    occupancy_target=float(strategy.get("occupancy_target",1.0) or 1.0)

    resource_land_open=bool(land_cost and money>=land_cost and remaining>=1)
    policy_land_open=bool(
        strategy_name not in ("LIQUID","ENDGAME")
        and land_cost
        and remaining>=9
        and occupancy>=occupancy_target
        and money-float(land_cost)>=reserve
    )
    projected_after_land=money-(float(land_cost) if policy_land_open and land_cost else 0.0)

    targets=oi.get("targets",{}) or {}
    scores=oi.get("scores",{}) or {}
    seed_policy={}
    seed_resource={}
    for crop,cost in strong_origin.SEED_COST.items():
        have=float((private.get("seeds",{}) or {}).get(crop,0) or 0)
        need=max(0.0,float(targets.get(crop,0) or 0)-float(live.get(crop,0))-have)
        affordable_resource=max(0,int(money//cost))
        affordable_policy=max(0,int((projected_after_land-reserve)//cost))
        seed_resource[crop]=bool(empty>0 and affordable_resource>0)
        seed_policy[crop]=bool(need>0 and float(scores.get(crop,0) or 0)>0 and affordable_policy>0)

    wheat=total_item(private,"WHEAT")
    cows=total_item(private,"COW")
    for row in tiles:
        for tile in row:
            if isinstance(tile,dict) and tile.get("animal")=="COW": cows+=1
    feed_need=max(0.0,2.0*cows-wheat)

    shed=private.get("shed",{}) or {}
    sellable_now={k:float(v or 0) for k,v in shed.items() if k in ("WHEAT","STRAWBERRY","MELON","MILK","WOOL","EGG","FERTILIZER") and float(v or 0)>0}

    market_action=(oi.get("market",[]) or [])
    actual=[]
    for a in market_action:
        if not isinstance(a,(list,tuple)) or not a: continue
        if a[0]=="BUY_LAND": actual.append("LAND")
        elif a[0]=="BUY_SEED" and len(a)>=2: actual.append("SEED_"+str(a[1]))
        elif a[0]=="SELL" and len(a)>=2: actual.append("SELL_"+str(a[1]))
        elif a[0]=="HIRE": actual.append("HIRE")
        else: actual.append(str(a[0]))

    resource_open={
        "LAND":resource_land_open,
        "WHEAT_SEED":seed_resource["WHEAT"],
        "STRAWBERRY_SEED":seed_resource["STRAWBERRY"],
        "MELON_SEED":seed_resource["MELON"],
        "CROP_EXPANSION_SPACE":empty>0,
        "SELL_NOW":bool(sellable_now),
        "WAIT":True,
    }
    policy_open={
        "LAND":policy_land_open,
        "WHEAT_SEED":seed_policy["WHEAT"],
        "STRAWBERRY_SEED":seed_policy["STRAWBERRY"],
        "MELON_SEED":seed_policy["MELON"],
        "WAIT":True,
    }
    return {
        "turn":snap.get("turn"),"day":day,
        "state":{
            "money":money,"quadrants":quadrants,"unlocked_tiles":unlocked,"occupied_tiles":occupied,"empty_tiles":empty,
            "occupancy":round(occupancy,6),"reserve":reserve,"land_cost":land_cost,
            "post_land_cash":None if land_cost is None else money-float(land_cost),
            "hands":1+len(me.get("hands",[])),"wheat":wheat,"cows":cows,"feed_gap":feed_need,
            "live_crops":live,"harvest_ready":harvest_ready,"growing":growing,"sellable_now":sellable_now,
        },
        "resource_open":resource_open,
        "policy_open":policy_open,
        "actual_next":actual,
        "final_target":targets,
    }

def play(seed,seat):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    agent.reset_telemetry()
    rows=[]
    turn=-1
    def observed(obs):
        nonlocal turn
        turn+=1
        act=agent.agent(obs)
        if START<=turn<=END:
            rows.append(classify(obs,latest_snapshot()))
        return act
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    ps=[OPP,OPP]; ps[seat]=observed
    env.run(ps)
    return rows

cases=[]
for seed,seat in CASES:
    cases.append({"seed":seed,"seat":seat,"group":"land_reinvest" if (seed,seat) in LAND else "seed3","trace":play(seed,seat)})

out={"schema":"reachable-transformation-set.v1","policy_mutated":False,"window":[START,END],
     "note":"resource_open separates physical/resource feasibility from current-agent policy_open; no causal ranking",
     "cases":cases}
Path("reachable_transformation_set_v1.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("REACHABLE_TRANSFORMATION_SET_V1",len(cases))
