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
START,END=102,121

def latest_snapshot():
    return agent.get_trace()["body"]["observe"]["body"]["snapshots"][-1]

def classify(obs,snap):
    p=int(obs["player"]); me=obs["farms"][p]
    day=int(obs.get("day",0)); remaining=30-day
    money=float(me.get("money",0) or 0)
    tiles=me.get("tiles",[])
    unlocked=occupied=empty=0
    for row in tiles:
        for tile in row:
            if tile=="LOCKED": continue
            unlocked+=1
            if tile is None:
                empty+=1
            else:
                occupied+=1

    oi=snap.get("origin_internal",{}) or {}
    strategy_name=oi.get("strategy_name")
    strategy=strong_origin.STRATEGIES.get(strategy_name,{})
    reserve=float(strategy.get("reserve_base",0) or 0)+20*occupied
    occupancy=(occupied/unlocked) if unlocked else 1.0
    occupancy_target=float(strategy.get("occupancy_target",1.0) or 1.0)
    quadrants=len(me.get("unlocked_quadrants",[]))
    land_cost={1:1000,2:2000,3:4000}.get(quadrants)

    land_resource_open=bool(land_cost and money>=land_cost and remaining>=1)
    post_land_cash=None if land_cost is None else money-float(land_cost)
    land_policy_open=bool(
        strategy_name not in ("LIQUID","ENDGAME")
        and land_cost
        and remaining>=9
        and occupancy>=occupancy_target
        and post_land_cash is not None
        and post_land_cash>=reserve
    )
    actual=[]
    for a in (oi.get("market",[]) or []):
        if not isinstance(a,(list,tuple)) or not a: continue
        if a[0]=="BUY_LAND": actual.append("LAND")
        elif a[0]=="BUY_SEED" and len(a)>=2: actual.append("SEED_"+str(a[1]))
        elif a[0]=="SELL" and len(a)>=2: actual.append("SELL_"+str(a[1]))
        elif a[0]=="HIRE": actual.append("HIRE")

    return {
        "turn":int(snap.get("turn")),
        "land_resource_open":land_resource_open,
        "land_policy_open":land_policy_open,
        "money":money,
        "reserve":reserve,
        "post_land_cash":post_land_cash,
        "occupancy":round(occupancy,6),
        "occupancy_target":occupancy_target,
        "empty_tiles":empty,
        "remaining":remaining,
        "actual_next":actual,
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
    ps=[OPP,OPP]; ps[seat]=observed
    env.run(ps)
    return rows

traces={k:play(*k) for k in CASES}
fields=["land_resource_open","land_policy_open","money","reserve","post_land_cash","occupancy","empty_tiles","remaining"]

first_full_sep=None
sep_fields=[]
for turn in range(START,END+1):
    land_rows=[next((r for r in traces[k] if r["turn"]==turn),None) for k in sorted(LAND)]
    seed_rows=[next((r for r in traces[k] if r["turn"]==turn),None) for k in sorted(SEED)]
    if any(r is None for r in land_rows+seed_rows): continue
    local=[]
    for f in fields:
        lv=[r[f] for r in land_rows]; sv=[r[f] for r in seed_rows]
        # complete categorical/numeric separation: no overlapping exact values
        if set(lv).isdisjoint(set(sv)):
            local.append(f)
    if local:
        first_full_sep=turn
        sep_fields=local
        break

cases=[]
for seed,seat in CASES:
    row=next((r for r in traces[(seed,seat)] if r["turn"]==first_full_sep),None) if first_full_sep is not None else None
    cases.append({"seed":seed,"seat":seat,"group":"land" if (seed,seat) in LAND else "seed3","first_divergence":row})

out={
  "schema":"land-recovery-boundary.v1",
  "policy_mutated":False,
  "window":[START,END],
  "first_full_group_separation_turn":first_full_sep,
  "separating_fields":sep_fields,
  "cases":cases
}
Path("land_recovery_boundary_v1.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("LAND_RECOVERY_BOUNDARY_V1",first_full_sep,sep_fields)
