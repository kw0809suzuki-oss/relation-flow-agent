#!/usr/bin/env python3
"""State Transition Growth Audit v0.

No candidate and no policy mutation.

Replays Strong Origin v2 Body-only v0 vs Seyamalam on fixed fresh cases and
records public-rule world transitions across Day4 -> Day8 -> Day12.

Facts:
- State snapshots retained by the environment.
- Exact realized market Cash events from the validated public-rule market logger.
- Actual production increments from WATER / daily crop refresh / daily animal refresh.
- Actual HARVEST units from public-rule unit execution.

Valuation:
- Existing WB-0001 current-price committed-production potential.

Schedule:
- Next output-availability day implied by current State + public rules.
  This is an opportunity schedule, not a guarantee of realized output.
"""
import copy
import json
import os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
TARGET_DAYS=(0,4,8,12)
OUT=Path(f"state_transition_growth_audit_v0_{SEED}.json")

production_events=[]
harvest_events=[]
plant_events=[]
farm_player={}
live_farms=[]
_current_day=0
_current_hour=0
unmapped_relevant_events=0


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)):
        return v
    if isinstance(v,dict):
        return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):
        return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    if hasattr(v,"tolist"):
        try:return plain(v.tolist())
        except Exception:pass
    if hasattr(v,"item"):
        try:return plain(v.item())
        except Exception:pass
    if hasattr(v,"__dict__"):
        try:return {str(k):plain(x) for k,x in vars(v).items() if not str(k).startswith("_")}
        except Exception:pass
    return str(v)


def getv(x,key,default=None):
    if isinstance(x,dict):
        return x.get(key,default)
    try:return getattr(x,key)
    except Exception:return default


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()


def export_states(env):
    out={"0":{},"1":{}}
    for step_index,step in enumerate(getattr(env,"steps",[]) or []):
        if not isinstance(step,(list,tuple)) or len(step)<2:
            continue
        for p in (0,1):
            obs=plain(getv(step[p],"observation"))
            if not isinstance(obs,dict):
                continue
            day=int(obs.get("day",0) or 0)
            k=str(day)
            if day in TARGET_DAYS and k not in out[str(p)]:
                out[str(p)][k]={"step_index":step_index,"observation":obs}
    return out


def player_for_farm(farm):
    p=farm_player.get(id(farm))
    if p is not None:
        return p
    matches=[]
    for i,known in enumerate(live_farms):
        try:
            if farm==known:
                matches.append(i)
        except Exception:
            pass
    if len(matches)==1:
        p=matches[0]
        farm_player[id(farm)]=p
        return p
    return None


def tile_copy(farm,pos):
    if pos is None:
        return None
    try:
        x,y=int(pos[0]),int(pos[1])
        return copy.deepcopy(farm["tiles"][y][x])
    except Exception:
        return None


def observed_apply_unit_action(original):
    def wrapped(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity=100):
        global unmapped_relevant_events
        p=player_for_farm(farm)
        pos=kg._farmer_position(farm,idx)
        before_tile=tile_copy(farm,pos)
        invs=private.get("inventories",[]) or []
        before_inv=copy.deepcopy(invs[idx] if 0<=idx<len(invs) else {})
        op=action[0] if isinstance(action,list) and action else None

        original(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)

        after_tile=tile_copy(farm,pos)
        invs2=private.get("inventories",[]) or []
        after_inv=copy.deepcopy(invs2[idx] if 0<=idx<len(invs2) else {})

        if op=="PLANT" and isinstance(action,list) and len(action)>=2:
            crop=action[1]
            before_seed=int(before_inv.get(crop,0) or 0)
            after_seed=int(after_inv.get(crop,0) or 0)
            if (
                before_tile is None
                and isinstance(after_tile,dict)
                and after_tile.get("kind")=="PLANT"
                and after_tile.get("crop")==crop
                and after_seed==before_seed-1
            ):
                if p is None:
                    unmapped_relevant_events+=1
                else:
                    plant_events.append({
                        "player":p,
                        "day":int(day),
                        "hour":int(_current_hour),
                        "crop":crop,
                        "units":1,
                    })

        if op=="WATER" and isinstance(before_tile,dict) and isinstance(after_tile,dict):
            crop=before_tile.get("crop")
            if crop and crop==after_tile.get("crop"):
                before_y=int(before_tile.get("yield_units",0) or 0)
                after_y=int(after_tile.get("yield_units",0) or 0)
                if after_y>before_y:
                    if p is None:
                            unmapped_relevant_events+=1
                    else:
                        production_events.append({
                        "player":p,
                        "transition_day":int(day),
                        "hour":int(_current_hour),
                        "result_state_day":int(day),
                        "source":"WATER",
                        "item":crop,
                        "units":after_y-before_y,
                            "asset_origin_day":int(day if before_tile.get("planted_day") is None else before_tile.get("planted_day")),
                        })

        if op=="HARVEST" and isinstance(before_tile,dict):
            item=None
            origin_day=None
            if before_tile.get("kind")=="PLANT" and before_tile.get("crop"):
                item=before_tile.get("crop")
                origin_day=int(day if before_tile.get("planted_day") is None else before_tile.get("planted_day"))
            elif before_tile.get("animal"):
                animal=before_tile.get("animal")
                item=kg.ANIMALS[animal]["product"]
                origin_day=int(day if before_tile.get("placed_day") is None else before_tile.get("placed_day"))
            if item:
                gained=int(after_inv.get(item,0) or 0)-int(before_inv.get(item,0) or 0)
                if gained>0:
                    if p is None:
                        unmapped_relevant_events+=1
                    else:
                        harvest_events.append({
                        "player":p,
                        "day":int(day),
                        "hour":int(_current_hour),
                        "item":item,
                        "units":gained,
                            "asset_origin_day":origin_day,
                        })
    return wrapped


def observed_daily_plants(original):
    def wrapped(farm,current_day,turns_per_day):
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
                if p is None:
                    unmapped_relevant_events+=1
                else:
                    production_events.append({
                    "player":p,
                    "transition_day":int(current_day),
                    "hour":24,
                    "result_state_day":int(current_day)+1,
                    "source":"DAILY_CROP",
                    "item":bt.get("crop"),
                    "units":ay-by,
                        "asset_origin_day":int(current_day if bt.get("planted_day") is None else bt.get("planted_day")),
                    })
    return wrapped


def observed_daily_animals(original):
    def wrapped(farm,day):
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
            if not isinstance(at,dict) or at.get("animal")!=bt.get("animal"):
                continue
            by=int(bt.get("yield_units",0) or 0)
            ay=int(at.get("yield_units",0) or 0)
            if ay>by:
                animal=bt.get("animal")
                if p is None:
                    unmapped_relevant_events+=1
                else:
                    production_events.append({
                    "player":p,
                    "transition_day":int(day),
                    "hour":24,
                    "result_state_day":int(day)+1,
                    "source":"DAILY_ANIMAL",
                    "item":kg.ANIMALS[animal]["product"],
                    "units":ay-by,
                    "animal":animal,
                        "asset_origin_day":int(day if bt.get("placed_day") is None else bt.get("placed_day")),
                    })
    return wrapped


def measured_market_with_time(state,env):
    global _current_day,_current_hour
    obs0=state[0].observation
    _current_day=int(getv(obs0,"day",0) or 0)
    _current_hour=int(getv(obs0,"hour",0) or 0)
    live_farms[:] = list(obs0.farms)
    for p,farm in enumerate(obs0.farms):
        farm_player[id(farm)]=p
    before=len(exact.events)
    exact.measured_process_market(state,env)
    for e in exact.events[before:]:
        e["day"]=_current_day
        e["hour"]=_current_hour


def main():
    global _current_day,_current_hour,unmapped_relevant_events
    configure()
    production_events.clear()
    harvest_events.clear()
    plant_events.clear()
    farm_player.clear()
    live_farms.clear()
    unmapped_relevant_events=0
    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    initial=[float(env.state[p].observation.farms[p].money) for p in (0,1)]
    live_farms[:] = list(env.state[0].observation.farms)
    for p,farm in enumerate(live_farms):
        farm_player[id(farm)]=p

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

    terminal=[float(x.reward) for x in env.state]
    snapshots=export_states(env)

    commitment_trace={"0":[],"1":[]}
    for step_index,step in enumerate(getattr(env,"steps",[]) or []):
        if not isinstance(step,(list,tuple)) or len(step)<2:
            continue
        for p in (0,1):
            obs=plain(getv(step[p],"observation"))
            if not isinstance(obs,dict):
                continue
            day=int(obs.get("day",0) or 0)
            if day>=4:
                continue
            private=obs.get("private",{}) or {}
            farm=(obs.get("farms",[]) or [{},{}])[p]
            tiles=farm.get("tiles",[]) or []
            empty=sum(1 for row in tiles for t in (row or []) if t is None)
            seeds=private.get("seeds",{}) or {}
            commitment_trace[str(p)].append({
                "step_index":step_index,
                "day":day,
                "hour":int(obs.get("hour",0) or 0),
                "seed_stock":{k:int(v or 0) for k,v in seeds.items()},
                "empty_tiles":empty,
                "workers":1+len(farm.get("hands",[]) or []),
            })

    cash_validation=[]
    for p in (0,1):
        net=sum(float(v) for v in exact.ledger[p].values())
        reconstructed=initial[p]+net
        cash_validation.append({
            "player":p,
            "initial_cash":initial[p],
            "market_cash_flow_net":net,
            "reconstructed_terminal":reconstructed,
            "actual_terminal":terminal[p],
            "error":reconstructed-terminal[p],
        })

    missing=[
        {"player":p,"day":d}
        for p in (0,1) for d in TARGET_DAYS
        if str(d) not in snapshots[str(p)]
    ]

    payload={
        "schema":"kaggriculture.strong-origin-v2.state-transition-growth-audit.v0",
        "seed":SEED,
        "seat":SEAT,
        "target_days":list(TARGET_DAYS),
        "terminal":{
            "self":terminal[SEAT],
            "opponent":terminal[1-SEAT],
            "margin":terminal[SEAT]-terminal[1-SEAT],
        },
        "state_export":snapshots,
        "market_events":plain(exact.events),
        "production_events":plain(production_events),
        "harvest_events":plain(harvest_events),
        "plant_events":plain(plant_events),
        "commitment_trace":plain(commitment_trace),
        "cash_validation":cash_validation,
        "audit":{
            "missing_target_states":missing,
            "unmapped_relevant_events":unmapped_relevant_events,
            "production_event_count":len(production_events),
            "harvest_event_count":len(harvest_events),
            "plant_event_count":len(plant_events),
            "market_event_count":len(exact.events),
        },
        "boundary":[
            "No candidate, threshold, Action override, or policy mutation is introduced.",
            "Self policy is Strong Origin v2 Body-only v0; opponent is the fixed Seyamalam path used by the benchmark.",
            "Market Cash events use the already-validated logging-equivalent public-rule processor.",
            "Production increments are observed by wrapping the public-rule WATER and daily refresh functions without changing their return/state behavior.",
            "HARVEST and successful PLANT are observed by public-rule unit execution state/inventory deltas.",
            "Cash validation must be exactly zero for both players and all Day4/8/12 State snapshots must exist.",
            "No causal link from a specific SELL to a specific later investment is asserted."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("STATE_TRANSITION_GROWTH_AUDIT "+json.dumps({
        "seed":SEED,
        "seat":SEAT,
        "terminal":payload["terminal"],
        "audit":payload["audit"],
        "cash_errors":[x["error"] for x in cash_validation],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
