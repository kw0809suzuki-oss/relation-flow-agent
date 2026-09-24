#!/usr/bin/env python3
"""Battle Value Flow Sequence v0.

Observation-only replay for the repeated Day13->15 and Day16->18 pulses.

Records public-world facts only:
- committed productive-State current-price mark at every observed State
- actual production increments from public WATER / daily refresh
- exact realized SELL Cash from the validated public market processor
- Cash at every observed State

No Action diagnosis, cause, Representation, Evaluation, Direction, Candidate,
or policy mutation.
"""
import copy,json,os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"battle_value_flow_sequence_v0_{SEED}_seat{SEAT}.json")

production_events=[]
farm_player={}
live_farms=[]
_current_day=0
_current_hour=0
_current_prices={}
unmapped_relevant_events=0


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    return str(v)


def getv(x,key,default=None):
    if isinstance(x,dict): return x.get(key,default)
    try:return getattr(x,key)
    except Exception:return default


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()


def player_for_farm(farm):
    p=farm_player.get(id(farm))
    if p is not None:return p
    matches=[]
    for i,known in enumerate(live_farms):
        try:
            if farm==known:matches.append(i)
        except Exception:pass
    if len(matches)==1:
        p=matches[0]
        farm_player[id(farm)]=p
        return p
    return None


def tile_copy(farm,pos):
    if pos is None:return None
    try:
        x,y=int(pos[0]),int(pos[1])
        return copy.deepcopy(farm["tiles"][y][x])
    except Exception:return None


def add_prod(p,item,units,source,result_day,result_hour,origin_day):
    price=float(_current_prices.get(item,0) or 0)
    production_events.append({
        "player":p,
        "item":item,
        "units":int(units),
        "source":source,
        "result_day":int(result_day),
        "result_hour":int(result_hour),
        "asset_origin_day":int(origin_day),
        "display_price":price,
        "event_price_mark":float(units)*price,
    })


def observed_apply_unit_action(original):
    def wrapped(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity=100):
        global unmapped_relevant_events
        p=player_for_farm(farm)
        pos=kg._farmer_position(farm,idx)
        before_tile=tile_copy(farm,pos)
        original(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)
        after_tile=tile_copy(farm,pos)
        op=action[0] if isinstance(action,list) and action else None
        if op=="WATER" and isinstance(before_tile,dict) and isinstance(after_tile,dict):
            crop=before_tile.get("crop")
            if crop and crop==after_tile.get("crop"):
                by=int(before_tile.get("yield_units",0) or 0)
                ay=int(after_tile.get("yield_units",0) or 0)
                if ay>by:
                    if p is None:unmapped_relevant_events+=1
                    else:add_prod(
                        p,crop,ay-by,"WATER",int(day),int(_current_hour),
                        int(day if before_tile.get("planted_day") is None else before_tile.get("planted_day"))
                    )
    return wrapped


def observed_daily_plants(original):
    def wrapped(farm,current_day,turns_per_day):
        global unmapped_relevant_events
        p=player_for_farm(farm)
        before={}
        for y,row in enumerate(farm.get("tiles",[]) or []):
            for x,t in enumerate(row or []):
                if isinstance(t,dict) and t.get("kind")=="PLANT":
                    before[(x,y)]=copy.deepcopy(t)
        original(farm,current_day,turns_per_day)
        for (x,y),bt in before.items():
            try:at=farm["tiles"][y][x]
            except Exception:continue
            if not isinstance(at,dict) or at.get("kind")!="PLANT" or at.get("crop")!=bt.get("crop"):
                continue
            by=int(bt.get("yield_units",0) or 0)
            ay=int(at.get("yield_units",0) or 0)
            if ay>by:
                if p is None:unmapped_relevant_events+=1
                else:add_prod(
                    p,bt.get("crop"),ay-by,"DAILY_CROP",int(current_day)+1,0,
                    int(current_day if bt.get("planted_day") is None else bt.get("planted_day"))
                )
    return wrapped


def observed_daily_animals(original):
    def wrapped(farm,day):
        global unmapped_relevant_events
        p=player_for_farm(farm)
        before={}
        for y,row in enumerate(farm.get("tiles",[]) or []):
            for x,t in enumerate(row or []):
                if isinstance(t,dict) and t.get("animal"):
                    before[(x,y)]=copy.deepcopy(t)
        original(farm,day)
        for (x,y),bt in before.items():
            try:at=farm["tiles"][y][x]
            except Exception:continue
            if not isinstance(at,dict) or at.get("animal")!=bt.get("animal"):continue
            by=int(bt.get("yield_units",0) or 0)
            ay=int(at.get("yield_units",0) or 0)
            if ay>by:
                animal=bt.get("animal")
                item=kg.ANIMALS[animal]["product"]
                if p is None:unmapped_relevant_events+=1
                else:add_prod(
                    p,item,ay-by,"DAILY_ANIMAL",int(day)+1,0,
                    int(day if bt.get("placed_day") is None else bt.get("placed_day"))
                )
    return wrapped


def measured_market_with_time(state,env):
    global _current_day,_current_hour,_current_prices
    obs0=state[0].observation
    _current_day=int(getv(obs0,"day",0) or 0)
    _current_hour=int(getv(obs0,"hour",0) or 0)
    market=getv(obs0,"market",{}) or {}
    _current_prices=dict(getv(market,"prices",{}) or {})
    live_farms[:] = list(obs0.farms)
    for p,farm in enumerate(obs0.farms):
        farm_player[id(farm)]=p
    before=len(exact.events)
    exact.measured_process_market(state,env)
    for e in exact.events[before:]:
        e["day"]=_current_day
        e["hour"]=_current_hour


def side_state(obs):
    s=econ.derive_side(obs)
    return {
        "cash":float(s["cash"]),
        "committed_production_mark":float(s["committed_production"]["same_basis_subtotal"]),
        "crop_production_mark":float(s["committed_production"]["crop_current_price_potential_mark"]),
        "animal_production_mark":float(s["committed_production"]["animal_base_current_price_potential_mark"]),
    }


def main():
    global unmapped_relevant_events
    configure()
    production_events.clear();farm_player.clear();live_farms.clear()
    unmapped_relevant_events=0
    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    live_farms[:] = list(env.state[0].observation.farms)
    for p,farm in enumerate(live_farms):farm_player[id(farm)]=p

    original_market=kg._process_market
    original_apply=kg._apply_unit_action
    original_plants=kg._daily_refresh_plants
    original_animals=kg._daily_refresh_animals
    kg._process_market=measured_market_with_time
    kg._apply_unit_action=observed_apply_unit_action(original_apply)
    kg._daily_refresh_plants=observed_daily_plants(original_plants)
    kg._daily_refresh_animals=observed_daily_animals(original_animals)
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=body_only.agent
        env.run(players)
    finally:
        kg._process_market=original_market
        kg._apply_unit_action=original_apply
        kg._daily_refresh_plants=original_plants
        kg._daily_refresh_animals=original_animals

    timeline=[]
    for step_index,step in enumerate(getattr(env,"steps",[]) or []):
        if not isinstance(step,(list,tuple)) or len(step)<2:continue
        so=plain(getv(step[SEAT],"observation"))
        oo=plain(getv(step[1-SEAT],"observation"))
        if not isinstance(so,dict) or not isinstance(oo,dict):continue
        d=int(so.get("day",0) or 0);h=int(so.get("hour",0) or 0)
        if not (12<=d<=18):continue
        ss=side_state(so);oside=side_state(oo)
        timeline.append({
            "step":step_index,"day":d,"hour":h,
            "self":ss,"opponent":oside,
            "residual":{
                "cash":oside["cash"]-ss["cash"],
                "committed_production_mark":oside["committed_production_mark"]-ss["committed_production_mark"],
                "crop_production_mark":oside["crop_production_mark"]-ss["crop_production_mark"],
                "animal_production_mark":oside["animal_production_mark"]-ss["animal_production_mark"],
            }
        })

    sell_events=[]
    for e in exact.events:
        if e.get("op")=="SELL" and 12<=int(e.get("day",-1))<=18:
            sell_events.append(plain(e))
    prod=[plain(e) for e in production_events if 12<=int(e.get("result_day",-1))<=18]

    rewards=[float(x.reward) for x in env.state]
    payload={
      "schema":"kaggriculture.strong-origin-v2.battle-value-flow-sequence.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "timeline":timeline,
      "production_events":prod,
      "sell_events":sell_events,
      "audit":{"unmapped_relevant_events":unmapped_relevant_events},
      "boundary":[
        "Committed Production is the existing Battle Value Map current-price potential valuation.",
        "Actual output events are public-rule production increments; event_price_mark is units x displayed price at the observed event turn and is descriptive valuation only.",
        "SELL events are exact realized Cash deltas from the validated public market processor.",
        "No causal link between productive State, output, SELL, and later Cash is asserted by the logger.",
        "No Action, mechanism, Representation, Evaluation, Direction, Candidate, or policy mutation."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BATTLE_VALUE_FLOW_SEQUENCE "+json.dumps({
        "seed":SEED,"seat":SEAT,
        "production_events":len(prod),"sell_events":len(sell_events),
        "unmapped":unmapped_relevant_events,
        "terminal":payload["terminal"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
