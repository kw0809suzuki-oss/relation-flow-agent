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
START,END=96,130

def latest_snapshot():
    tr=agent.get_trace()
    return tr["body"]["observe"]["body"]["snapshots"][-1]

def classify(obs,snap):
    p=int(obs["player"]); me=obs["farms"][p]; private=obs["private"]
    day=int(obs.get("day",0)); remaining=30-day
    money=float(me.get("money",0) or 0)
    tiles=me.get("tiles",[])
    unlocked=occupied=0
    live={"WHEAT":0,"STRAWBERRY":0,"MELON":0}
    for row in tiles:
        for tile in row:
            if tile=="LOCKED": continue
            unlocked+=1
            if tile is None: continue
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

    land_open=bool(
        strategy_name not in ("LIQUID","ENDGAME")
        and land_cost
        and remaining>=9
        and occupancy>=occupancy_target
        and money-float(land_cost)>=reserve
    )

    targets=oi.get("targets",{}) or {}
    scores=oi.get("scores",{}) or {}
    have=float((private.get("seeds",{}) or {}).get("WHEAT",0) or 0)
    need=max(0.0,float(targets.get("WHEAT",0) or 0)-float(live.get("WHEAT",0))-have)
    projected_cash=money-(float(land_cost) if land_open and land_cost else 0.0)
    affordable=max(0,int((projected_cash-reserve)//strong_origin.SEED_COST["WHEAT"]))
    wheat_open=bool(need>0 and float(scores.get("WHEAT",0) or 0)>0 and affordable>0)

    actual_wheat=False
    for a in (oi.get("market",[]) or []):
        if isinstance(a,(list,tuple)) and len(a)>=2 and a[0]=="BUY_SEED" and a[1]=="WHEAT":
            actual_wheat=True
            break

    return {
        "turn":int(snap.get("turn")),
        "wheat_need":need,
        "WHEAT_policy_open":wheat_open,
        "LAND_policy_open":land_open,
        "actual_WHEAT":actual_wheat,
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

def first_turn(rows,key,pred=lambda x: bool(x)):
    for r in rows:
        if pred(r.get(key)):
            return r["turn"]
    return None

out_rows=[]
for seed,seat in CASES:
    rows=play(seed,seat)
    need_open=None
    prev_need=0.0
    for r in rows:
        need=float(r["wheat_need"] or 0.0)
        if prev_need<=0.0 and need>0.0:
            need_open=r["turn"]; break
        prev_need=need
    tau_w=first_turn(rows,"WHEAT_policy_open")
    actual_w=first_turn(rows,"actual_WHEAT")
    tau_l=first_turn(rows,"LAND_policy_open")
    delta=None if tau_w is None or tau_l is None else tau_l-tau_w
    if tau_w is None:
        cls="W-never"
    elif tau_l is None:
        cls="W-first"
    elif tau_w < tau_l:
        cls="W-first"
    else:
        cls="L-first"
    out_rows.append({
        "seed":seed,"seat":seat,
        "group":"land" if (seed,seat) in LAND else "seed3",
        "wheat_need_open_turn":need_open,
        "tau_W":tau_w,
        "first_actual_WHEAT":actual_w,
        "tau_L":tau_l,
        "delta_tau":delta,
        "class":cls,
    })

summary={
    "seed3_classes":{},
    "land_classes":{},
}
for r in out_rows:
    bucket=summary["seed3_classes"] if r["group"]=="seed3" else summary["land_classes"]
    bucket[r["class"]]=bucket.get(r["class"],0)+1

out={"schema":"policy-timing-order.v1","policy_mutated":False,"window":[START,END],"cases":out_rows,"summary":summary}
Path("policy_timing_order_v1.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("POLICY_TIMING_ORDER_V1",json.dumps(summary,separators=(",",":")))
