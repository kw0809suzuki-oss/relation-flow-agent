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

def classify(obs,snap):
    p=int(obs["player"]); me=obs["farms"][p]; private=obs["private"]
    day=int(obs.get("day",0)); remaining=30-day
    money=float(me.get("money",0) or 0)
    tiles=me.get("tiles",[])
    unlocked=occupied=empty=0
    live={"WHEAT":0,"STRAWBERRY":0,"MELON":0}
    for row in tiles:
        for tile in row:
            if tile=="LOCKED": continue
            unlocked+=1
            if tile is None:
                empty+=1; continue
            occupied+=1
            if isinstance(tile,dict) and tile.get("kind")=="PLANT":
                c=tile.get("crop")
                if c in live: live[c]+=1

    oi=snap.get("origin_internal",{}) or {}
    strategy_name=oi.get("strategy_name")
    strategy=strong_origin.STRATEGIES.get(strategy_name,{})
    reserve=float(strategy.get("reserve_base",0) or 0)+20*occupied
    occupancy=(occupied/unlocked) if unlocked else 1.0
    occupancy_target=float(strategy.get("occupancy_target",1.0) or 1.0)
    quadrants=len(me.get("unlocked_quadrants",[]))
    land_cost={1:1000,2:2000,3:4000}.get(quadrants)

    remaining_ok=remaining>=9
    occupancy_ok=occupancy>=occupancy_target
    reserve_ok=bool(land_cost is not None and money-float(land_cost)>=reserve)
    post_land_cash_ok=reserve_ok
    land_policy_open=bool(
        strategy_name not in ("LIQUID","ENDGAME")
        and land_cost
        and remaining_ok
        and occupancy_ok
        and reserve_ok
    )

    targets=oi.get("targets",{}) or {}
    scores=oi.get("scores",{}) or {}
    have=float((private.get("seeds",{}) or {}).get("WHEAT",0) or 0)
    need=max(0.0,float(targets.get("WHEAT",0) or 0)-float(live.get("WHEAT",0))-have)
    projected_cash=money-(float(land_cost) if land_policy_open and land_cost else 0.0)
    affordable=max(0,int((projected_cash-reserve)//strong_origin.SEED_COST["WHEAT"]))
    wheat_policy_open=bool(need>0 and float(scores.get("WHEAT",0) or 0)>0 and affordable>0)

    actual=[]
    for a in (oi.get("market",[]) or []):
        if not isinstance(a,(list,tuple)) or not a: continue
        if a[0]=="BUY_LAND": actual.append("LAND")
        elif a[0]=="BUY_SEED" and len(a)>=2 and a[1]=="WHEAT": actual.append("WHEAT")
        elif a[0]=="BUY_SEED" and len(a)>=2: actual.append("SEED_"+str(a[1]))
        elif a[0]=="SELL" and len(a)>=2: actual.append("SELL_"+str(a[1]))
        elif a[0]=="HIRE": actual.append("HIRE")

    return {
      "turn":snap.get("turn"),"day":day,
      "LAND_policy_open":land_policy_open,
      "WHEAT_policy_open":wheat_policy_open,
      "constraints":{
        "post_land_cash_ok":post_land_cash_ok,
        "reserve_ok":reserve_ok,
        "occupancy_ok":occupancy_ok,
        "remaining_ok":remaining_ok,
      },
      "actual_next":actual,
      "state":{"money":money,"reserve":reserve,"land_cost":land_cost,"occupancy":round(occupancy,6),
               "occupancy_target":occupancy_target,"empty_tiles":empty,"live_wheat":live["WHEAT"],
               "wheat_seed_have":have,"wheat_need":need,"wheat_affordable":affordable}
    }

def play(seed,seat):
    base._configure_baseline(); os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"; agent.reset_telemetry()
    rows=[]; turn=-1
    def observed(obs):
        nonlocal turn
        turn+=1
        act=agent.agent(obs)
        if START<=turn<=END:
            rows.append(classify(obs,latest_snapshot()))
        return act
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    ps=[OPP,OPP]; ps[seat]=observed; env.run(ps)
    return rows

traces={}
for seed,seat in CASES:
    traces[(seed,seat)]=play(seed,seat)

# first turn where policy-open vector is not uniform across all 13 cases
first=None
for turn in range(START,END+1):
    vals=[]
    ok=True
    for key in CASES:
        row=next((r for r in traces[key] if r["turn"]==turn),None)
        if row is None:
            ok=False; break
        vals.append((row["LAND_policy_open"],row["WHEAT_policy_open"]))
    if ok and len(set(vals))>1:
        first=turn; break

cases=[]
for seed,seat in CASES:
    row=next((r for r in traces[(seed,seat)] if r["turn"]==first),None) if first is not None else None
    cases.append({"seed":seed,"seat":seat,"group":"land_reinvest" if (seed,seat) in LAND else "seed3","first_policy_divergence":row})

out={"schema":"first-policy-divergence.v1","policy_mutated":False,"window":[START,END],
     "first_policy_divergence_turn":first,"cases":cases}
Path("first_policy_divergence_v1.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("FIRST_POLICY_DIVERGENCE_V1",first,len(cases))
