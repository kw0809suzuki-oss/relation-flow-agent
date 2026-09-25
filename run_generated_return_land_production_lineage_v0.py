#!/usr/bin/env python3
"""Generated Return -> LAND -> newly unlocked tile -> Production lineage v0.

Tracks the first productive BUY_LAND whose affordability depends on prior
generated farm Return (as defined by first_generated_return_input_bridge_v0),
identifies exactly which coordinates were unlocked by that purchase, then
records successful PLANTs and actual yield increases on those coordinates.

Observation only. No policy mutation.
"""
import copy,json,os
from pathlib import Path
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import run_first_generated_return_input_bridge_v0 as gen
import wr02_same_tile_plant_deconfliction_v0 as active

SEED=int(os.environ["BATTLE_SEED"]);SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"generated_return_land_production_lineage_v0_{SEED}_seat{SEAT}.json")

farm_player={}
live_farms=[]
first_land=[None,None]
new_coords=[set(),set()]
plants=[[],[]]
production_events=[]
main_calls=0
current_hour=0

def player_for_farm(farm):
    p=farm_player.get(id(farm))
    if p is not None:return p
    hits=[]
    for i,k in enumerate(live_farms):
        try:
            if farm==k:hits.append(i)
        except Exception:pass
    if len(hits)==1:
        farm_player[id(farm)]=hits[0];return hits[0]
    return None

def tile_at(farm,pos):
    if pos is None:return None
    try:return copy.deepcopy(farm["tiles"][int(pos[1])][int(pos[0])])
    except Exception:return None

def unlocked_positions(farm):
    out=set()
    for y,row in enumerate(farm.get("tiles",[]) or []):
        for x,t in enumerate(row or []):
            if t!="LOCKED":out.add((x,y))
    return out

def tracked_plant(p,pos,tile):
    if p is None or pos is None or not isinstance(tile,dict):return None
    for z in plants[p]:
        if tuple(z["position"])==(int(pos[0]),int(pos[1])) and z["crop"]==tile.get("crop") and int(z["planted_day"])==int(tile.get("planted_day",-999)):
            return z
    return None

def observed_apply(original):
    def wrapped(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity=100):
        global main_calls,current_hour
        p=player_for_farm(farm)
        if idx==0:
            current_hour=(main_calls//2)%int(turns_per_day)
            main_calls+=1
        pos=kg._farmer_position(farm,idx)
        before_tile=tile_at(farm,pos)
        op=action[0] if isinstance(action,list) and action else None
        before_seeds=copy.deepcopy(private.get("seeds",{}) or {})

        original(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)

        after_tile=tile_at(farm,pos)
        after_seeds=private.get("seeds",{}) or {}

        if p is not None and op=="PLANT" and len(action)>=2:
            crop=action[1]
            success=(
                crop in after_seeds
                and int(after_seeds.get(crop,0) or 0)==int(before_seeds.get(crop,0) or 0)-1
                and isinstance(after_tile,dict) and after_tile.get("kind")=="PLANT" and after_tile.get("crop")==crop
            )
            if success and pos is not None and (int(pos[0]),int(pos[1])) in new_coords[p]:
                if not any(tuple(z["position"])==(int(pos[0]),int(pos[1])) and int(z["planted_day"])==int(day) for z in plants[p]):
                    plants[p].append({
                        "player":p,"day":int(day),"hour":int(current_hour),"crop":crop,
                        "position":[int(pos[0]),int(pos[1])],"planted_day":int(day),
                    })

        if p is not None and op=="WATER" and isinstance(before_tile,dict) and isinstance(after_tile,dict):
            by=int(before_tile.get("yield_units",0) or 0);ay=int(after_tile.get("yield_units",0) or 0)
            z=tracked_plant(p,pos,before_tile)
            if z is not None and ay>by:
                production_events.append({
                    "player":p,"day":int(day),"hour":int(current_hour),"source":"WATER",
                    "crop":before_tile.get("crop"),"position":[int(pos[0]),int(pos[1])],
                    "planted_day":int(before_tile.get("planted_day",-999)),"units":ay-by
                })
    return wrapped

def observed_daily(original):
    def wrapped(farm,day,turns_per_day):
        p=player_for_farm(farm)
        before={}
        if p is not None:
            for z in plants[p]:
                pos=tuple(z["position"]);t=tile_at(farm,pos)
                if isinstance(t,dict) and t.get("kind")=="PLANT" and t.get("crop")==z["crop"] and int(t.get("planted_day",-999))==z["planted_day"]:
                    before[pos]=t
        original(farm,day,turns_per_day)
        if p is None:return
        for pos,bt in before.items():
            at=tile_at(farm,pos)
            if not isinstance(at,dict) or at.get("crop")!=bt.get("crop"):continue
            by=int(bt.get("yield_units",0) or 0);ay=int(at.get("yield_units",0) or 0)
            if ay>by:
                production_events.append({
                    "player":p,"day":int(day),"hour":24,"source":"DAILY_CROP",
                    "crop":bt.get("crop"),"position":[int(pos[0]),int(pos[1])],
                    "planted_day":int(bt.get("planted_day",-999)),"units":ay-by
                })
    return wrapped

def measured_market(state,env):
    live_farms[:]=list(state[0].observation.farms)
    for p,f in enumerate(live_farms):farm_player[id(f)]=p
    before_unlock=[unlocked_positions(f) for f in live_farms]
    n=len(gen.events)
    gen.measured_market(state,env)
    after_unlock=[unlocked_positions(f) for f in live_farms]
    new_events=gen.events[n:]
    for e in new_events:
        if e.get("op")=="BUY_LAND" and e.get("generated_return_necessary"):
            p=int(e["player"])
            if first_land[p] is None:
                gained=sorted(after_unlock[p]-before_unlock[p])
                first_land[p]=dict(e)
                first_land[p]["newly_unlocked_positions"]=[list(x) for x in gained]
                new_coords[p].update(gained)

def main():
    global main_calls,current_hour
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0";os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    active.reset_telemetry()
    gen.events.clear();gen.gen_cash[0]=gen.gen_cash[1]=0.0
    farm_player.clear();live_farms.clear();production_events.clear()
    for p in (0,1):
        first_land[p]=None;new_coords[p].clear();plants[p].clear()
    main_calls=0;current_hour=0

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    obs=env.state[0].observation
    gen.initial_on_hand=[]
    for p in (0,1):
        op=env.state[p].observation
        gen.initial_on_hand.append({i:gen.stock(op,i) for i in gen.EXACT_RETURN_ITEMS})
    live_farms[:]=list(env.state[0].observation.farms)
    for p,f in enumerate(live_farms):farm_player[id(f)]=p

    oa=kg._apply_unit_action;od=kg._daily_refresh_plants;om=kg._process_market
    kg._apply_unit_action=observed_apply(oa)
    kg._daily_refresh_plants=observed_daily(od)
    kg._process_market=measured_market
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT];players[SEAT]=active.agent
        env.run(players)
    finally:
        kg._apply_unit_action=oa;kg._daily_refresh_plants=od;kg._process_market=om

    rewards=[float(x.reward) for x in env.state]
    first_prod={}
    for p in (0,1):
        xs=sorted([e for e in production_events if e["player"]==p],key=lambda e:(e["day"],e["hour"]))
        first_prod[str(p)]=xs[0] if xs else None

    opp=1-SEAT
    opp_first=first_prod[str(opp)]
    context={}
    if opp_first:
        tm=(opp_first["day"],opp_first["hour"])
        context={
          "timestamp":{"day":tm[0],"hour":tm[1]},
          "self_generated_land_production_units":sum(e["units"] for e in production_events if e["player"]==SEAT and (e["day"],e["hour"])==tm),
          "opponent_generated_land_production_units":sum(e["units"] for e in production_events if e["player"]==opp and (e["day"],e["hour"])==tm),
        }

    payload={
      "schema":"kaggriculture.generated-return-land-production-lineage.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[opp],"margin":rewards[SEAT]-rewards[opp]},
      "first_generated_return_land_by_player":{str(p):first_land[p] for p in (0,1)},
      "successful_plants_on_that_new_land_by_player":{str(p):plants[p] for p in (0,1)},
      "production_events_from_that_new_land":production_events,
      "first_production_from_that_new_land_by_player":first_prod,
      "opponent_first_production_context":context,
      "boundary":[
        "Generated Return uses the existing exact-return definition: non-WHEAT sold product with zero initial on-hand and no external BUY_PRODUCT path.",
        "New land coordinates are the exact tile positions that change from locked to unlocked across the first generated-return-necessary BUY_LAND market event.",
        "Only successful PLANTs physically located on those newly unlocked coordinates are followed.",
        "Production is an observed yield increase from public WATER or daily crop refresh.",
        "This is actual-path World lineage, not a policy counterfactual and not yet a WR-03.",
        "WR-02 is the active self body but has no effect before Day14."
      ]}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("GENERATED_RETURN_LAND_PRODUCTION_LINEAGE "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "self_land":first_land[SEAT],"opponent_land":first_land[opp],
      "self_plants":plants[SEAT],"opponent_plants":plants[opp],
      "self_first_production":first_prod[str(SEAT)],"opponent_first_production":first_prod[str(opp)],
      "context":context
    },ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
