#!/usr/bin/env python3
"""Return-enabled MELON seed -> PLANT -> Production lineage v0.

Actual-path, public-rule observation only.

Seed fungibility is handled conservatively:
- initial MELON seed and every non-return-necessary MELON seed purchase form the
  nonreturn pool;
- return-necessary MELON seed purchases form the return pool;
- successful MELON PLANTs consume nonreturn pool first.
A PLANT is labeled return-seed-necessary only when even this conservative
allocation must consume the return pool.

The first such planted tile is then followed to its first actual yield increase.
"""
import copy,json,os
from collections import defaultdict
from pathlib import Path
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import run_first_return_enabled_productive_input_v0 as ret
import wr02_same_tile_plant_deconfliction_v0 as active

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"return_melon_lineage_v0_{SEED}_seat{SEAT}.json")

nonreturn=[0,0]
returnpool=[0,0]
first_required=[None,None]
plant_events=[]
production_events=[]
farm_player={}
live_farms=[]
main_calls=0
current_hour=0

def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    return str(v)

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
    try:
        x,y=int(pos[0]),int(pos[1])
        return copy.deepcopy(farm["tiles"][y][x])
    except Exception:return None

def target_match(p,pos,tile):
    z=first_required[p]
    if z is None or pos is None or not isinstance(tile,dict):return False
    return (
      [int(pos[0]),int(pos[1])]==z["position"]
      and tile.get("kind")=="PLANT"
      and tile.get("crop")=="MELON"
      and int(tile.get("planted_day",-999))==int(z["planted_day"])
    )

def observed_apply(original):
    def wrapped(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity=100):
        global main_calls,current_hour
        p=player_for_farm(farm)
        if idx==0:
            # Public engine applies player farms in stable 0,1 order each turn;
            # this is the same clock reconstruction used by existing probes.
            current_hour=(main_calls//2)%int(turns_per_day)
            main_calls+=1
        pos=kg._farmer_position(farm,idx)
        before_tile=tile_at(farm,pos)
        before_seed=int((private.get("seeds",{}) or {}).get("MELON",0) or 0)
        op=action[0] if isinstance(action,list) and action else None

        original(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)

        after_tile=tile_at(farm,pos)
        after_seed=int((private.get("seeds",{}) or {}).get("MELON",0) or 0)

        if p is not None and op=="PLANT" and len(action)>=2 and action[1]=="MELON":
            success=(
              after_seed==before_seed-1
              and isinstance(after_tile,dict)
              and after_tile.get("kind")=="PLANT"
              and after_tile.get("crop")=="MELON"
              and (not isinstance(before_tile,dict) or before_tile.get("crop")!="MELON")
            )
            if success:
                pool_before={"nonreturn":nonreturn[p],"return":returnpool[p],"actual_seed":before_seed}
                uses_return=False
                if nonreturn[p]>0:
                    nonreturn[p]-=1
                elif returnpool[p]>0:
                    returnpool[p]-=1
                    uses_return=True
                else:
                    raise SystemExit(f"seed pool underflow p={p} day={day} hour={current_hour} before={before_seed}")
                rec={
                  "player":p,"day":int(day),"hour":int(current_hour),"unit_index":idx,
                  "position":[int(pos[0]),int(pos[1])],"planted_day":int(day),
                  "seed_pool_before":pool_before,
                  "seed_pool_after":{"nonreturn":nonreturn[p],"return":returnpool[p],"actual_seed":after_seed},
                  "return_seed_necessary":uses_return,
                }
                plant_events.append(rec)
                if uses_return and first_required[p] is None:
                    first_required[p]=dict(rec)

        if p is not None and op=="WATER" and isinstance(before_tile,dict) and isinstance(after_tile,dict):
            if before_tile.get("crop")=="MELON" and after_tile.get("crop")=="MELON":
                by=int(before_tile.get("yield_units",0) or 0); ay=int(after_tile.get("yield_units",0) or 0)
                if ay>by:
                    production_events.append({
                      "player":p,"day":int(day),"hour":int(current_hour),"source":"WATER",
                      "position":[int(pos[0]),int(pos[1])],"asset_origin_day":int(before_tile.get("planted_day",-999)),
                      "units":ay-by,"is_first_return_required_tile":target_match(p,pos,before_tile),
                    })
    return wrapped

def observed_daily(original):
    def wrapped(farm,day,turns_per_day):
        p=player_for_farm(farm)
        before={}
        for y,row in enumerate(farm.get("tiles",[]) or []):
            for x,t in enumerate(row or []):
                if isinstance(t,dict) and t.get("kind")=="PLANT" and t.get("crop")=="MELON":
                    before[(x,y)]=copy.deepcopy(t)
        original(farm,day,turns_per_day)
        if p is None:return
        for (x,y),bt in before.items():
            try:at=farm["tiles"][y][x]
            except Exception:continue
            if not isinstance(at,dict) or at.get("crop")!="MELON":continue
            by=int(bt.get("yield_units",0) or 0); ay=int(at.get("yield_units",0) or 0)
            if ay>by:
                production_events.append({
                  "player":p,"day":int(day),"hour":24,"source":"DAILY_CROP",
                  "position":[x,y],"asset_origin_day":int(bt.get("planted_day",-999)),
                  "units":ay-by,"is_first_return_required_tile":target_match(p,(x,y),bt),
                })
    return wrapped

def measured_market(state,env):
    obs0=state[0].observation
    live_farms[:]=list(obs0.farms)
    for p,f in enumerate(live_farms):farm_player[id(f)]=p
    n=len(ret.events)
    ret.measured_market(state,env)
    for e in ret.events[n:]:
        if e.get("op")=="BUY_SEED" and e.get("item")=="MELON":
            p=int(e["player"])
            if e.get("return_necessary"): returnpool[p]+=1
            else: nonreturn[p]+=1

def main():
    global main_calls,current_hour
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0";os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    active.reset_telemetry()
    ret.events.clear();ret.cum_sell[0]=ret.cum_sell[1]=0.0
    plant_events.clear();production_events.clear();farm_player.clear();live_farms.clear()
    first_required[0]=first_required[1]=None
    main_calls=0;current_hour=0

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    for p in (0,1):
        seeds=env.state[p].observation.private.seeds
        nonreturn[p]=int(seeds.get("MELON",0) or 0);returnpool[p]=0
    live_farms[:]=list(env.state[0].observation.farms)
    for p,f in enumerate(live_farms):farm_player[id(f)]=p

    oa=kg._apply_unit_action; od=kg._daily_refresh_plants; om=kg._process_market
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
        xs=[e for e in production_events if e["player"]==p and e["is_first_return_required_tile"]]
        xs=sorted(xs,key=lambda e:(e["day"],e["hour"]))
        first_prod[str(p)]=xs[0] if xs else None

    # At the target production timestamp, report all MELON production on both sides.
    production_context={}
    opp=1-SEAT
    z=first_prod.get(str(opp))
    if z:
        tm=(z["day"],z["hour"])
        production_context={
          str(p):sum(e["units"] for e in production_events if e["player"]==p and (e["day"],e["hour"])==tm)
          for p in (0,1)
        }

    payload={
      "schema":"kaggriculture.return-melon-lineage.v0","seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "first_return_seed_required_plant_by_player":{str(p):first_required[p] for p in (0,1)},
      "first_production_from_that_tile_by_player":first_prod,
      "opponent_target_production_context_units_by_player":production_context,
      "plant_events":plant_events,
      "melon_production_events":production_events,
      "boundary":[
        "Nonreturn seed supply is consumed before return-necessary seed supply, so a return-seed-necessary PLANT is a conservative quantity-necessity result.",
        "The target tile is followed by coordinate + MELON + planted_day to an observed yield increase.",
        "This is actual-path physical lineage. It does not assert that a different policy without the seed would leave every later action unchanged.",
        "WR-02 is the active self body, but it is inactive before Day14; the observed early path is therefore unchanged from Body-only.",
        "No WR-03 Candidate or policy mutation is introduced."
      ]}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RETURN_MELON_LINEAGE "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "self_plant":first_required[SEAT],"opponent_plant":first_required[1-SEAT],
      "self_production":first_prod[str(SEAT)],"opponent_production":first_prod[str(1-SEAT)],
      "context":production_context
    },ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
