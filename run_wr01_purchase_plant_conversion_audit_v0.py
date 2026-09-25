#!/usr/bin/env python3
"""WR-01 Purchase -> Seed -> PLANT -> Productive Asset audit v0.

Matched baseline / unchanged WR-01 on fixed five Battles.

Observed after Day14:
- actual executed BUY_SEED units (public market execution)
- final model PLANT commands
- successful PLANT transformations (seed consumed and crop tile created)
- seed inventory at Day14 h0 and Day24 h0

No motive/evaluation inference. The first connection where WR-01 incremental
flow fails to pass is the only target of this audit.
"""
import json, os
from collections import Counter, defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as baseline
import world_reference_reachability_candidate_v0 as wr01

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"wr01_purchase_plant_conversion_audit_v0_{SEED}_seat{SEAT}.json")
START_DAY=14
CROPS=("WHEAT","STRAWBERRY","MELON")

_original_apply=kg._apply_unit_action


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"


def seed_snapshot(obs):
    seeds=(obs.get("private",{}) or {}).get("seeds",{}) or {}
    return {c:int(seeds.get(c,0) or 0) for c in CROPS}


def plant_commands(action):
    out=[]
    if not isinstance(action,dict):
        return out
    acts=[action.get("farmer",["PASS"])] + list(action.get("hands",[]) or [])
    for a in acts:
        if isinstance(a,(list,tuple)) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS:
            out.append(a[1])
    return out


def play(module):
    configure()
    module.reset_telemetry()

    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    buy_events=[]
    command_events=[]
    success_events=[]
    checkpoints={}
    farm_to_player={}
    main_calls=0

    def observed_agent(obs):
        key=f'd{int(obs.get("day",0) or 0)}h{int(obs.get("hour",0) or 0)}'
        if key in ("d14h0","d24h0") and key not in checkpoints:
            checkpoints[key]={"seeds":seed_snapshot(obs)}
        action=module.agent(obs)
        day=int(obs.get("day",0) or 0)
        hour=int(obs.get("hour",0) or 0)
        if day>=START_DAY:
            me=obs["farms"][int(obs["player"])]
            positions=[me["farmer"]] + list(me.get("hands",[]) or [])
            acts=[action.get("farmer",["PASS"])] + list(action.get("hands",[]) or [])
            seen={}
            for idx,a in enumerate(acts):
                if not (isinstance(a,(list,tuple)) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS):
                    continue
                pos=positions[idx] if idx < len(positions) else None
                pkey=tuple(pos) if pos is not None else None
                duplicate=pkey in seen if pkey is not None else False
                if pkey is not None:
                    seen[pkey]=seen.get(pkey,0)+1
                command_events.append({
                    "day":day,"hour":hour,"crop":a[1],
                    "unit_index":idx,
                    "position":list(pos) if pos is not None else None,
                    "same_tile_duplicate":duplicate,
                })
        return action

    def measured_market(state,env):
        obs0=state[0].observation
        day=int(obs0.day)
        hour=int(obs0.hour)
        farms=obs0.farms
        for p in (0,1):
            farm_to_player[id(farms[p])]=p
        n=len(exact.events)
        exact.measured_process_market(state,env)
        if day>=START_DAY:
            for e in exact.events[n:]:
                if int(e.get("player",-1))==SEAT and e.get("op")=="BUY_SEED" and e.get("item") in CROPS:
                    buy_events.append({
                        "day":day,"hour":hour,
                        "crop":e["item"],
                        "cash_delta":float(e.get("cash_delta",0) or 0),
                    })

    def wrapped_apply(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity=100):
        nonlocal main_calls
        if idx==0:
            p=main_calls%2
            main_calls+=1
            farm_to_player[id(farm)]=p
        p=farm_to_player.get(id(farm))
        crop=None
        before_seed=None
        pos=None
        if (
            p==SEAT and int(day)>=START_DAY and
            isinstance(action,(list,tuple)) and len(action)>=2 and
            action[0]=="PLANT" and action[1] in CROPS
        ):
            crop=action[1]
            pos=kg._farmer_position(farm,idx)
            before_seed=int((private.get("seeds",{}) or {}).get(crop,0) or 0)

        _original_apply(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)

        if crop is not None and pos is not None:
            after_seed=int((private.get("seeds",{}) or {}).get(crop,0) or 0)
            x,y=int(pos[0]),int(pos[1])
            try:
                tile=farm["tiles"][y][x]
            except Exception:
                tile=None
            ok=(
                after_seed==before_seed-1 and
                isinstance(tile,dict) and tile.get("kind")=="PLANT" and tile.get("crop")==crop
            )
            if ok:
                success_events.append({
                    "day":int(day),
                    "crop":crop,
                    "x":x,"y":y,
                })

    original_market=kg._process_market
    kg._process_market=measured_market
    kg._apply_unit_action=wrapped_apply
    try:
        env=make("kaggriculture",configuration={"seed":SEED},debug=False)
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=observed_agent
        env.run(players)
        rewards=[float(x.reward) for x in env.state]
    finally:
        kg._process_market=original_market
        kg._apply_unit_action=_original_apply

    buy=Counter(e["crop"] for e in buy_events)
    cmd=Counter(e["crop"] for e in command_events)
    suc=Counter(e["crop"] for e in success_events)
    start=checkpoints.get("d14h0",{"seeds":{c:0 for c in CROPS}})["seeds"]
    end=checkpoints.get("d24h0",{"seeds":{c:0 for c in CROPS}})["seeds"]

    return {
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
        },
        "executed_buy_seed_units":{c:int(buy[c]) for c in CROPS},
        "plant_command_units":{c:int(cmd[c]) for c in CROPS},
        "successful_plant_units":{c:int(suc[c]) for c in CROPS},
        "duplicate_plant_commands":sum(1 for e in command_events if e.get("same_tile_duplicate")),
        "duplicate_plant_commands_by_crop":{
            c:sum(1 for e in command_events if e.get("same_tile_duplicate") and e.get("crop")==c) for c in CROPS
        },
        "seed_inventory_day14":start,
        "seed_inventory_day24":end,
        "seed_inventory_change":{c:int(end.get(c,0)-start.get(c,0)) for c in CROPS},
        "buy_events":buy_events,
        "plant_command_events":command_events,
        "successful_plant_events":success_events,
        "telemetry":module.get_telemetry(),
    }


def main():
    b=play(baseline)
    w=play(wr01)
    payload={
        "schema":"kaggriculture.strong-origin-v2.wr01-purchase-plant-conversion-audit.v0",
        "seed":SEED,
        "seat":SEAT,
        "baseline":b,
        "wr01":w,
        "delta":{
            "executed_buy_seed_units":{
                c:w["executed_buy_seed_units"][c]-b["executed_buy_seed_units"][c] for c in CROPS
            },
            "plant_command_units":{
                c:w["plant_command_units"][c]-b["plant_command_units"][c] for c in CROPS
            },
            "successful_plant_units":{
                c:w["successful_plant_units"][c]-b["successful_plant_units"][c] for c in CROPS
            },
            "duplicate_plant_commands":w["duplicate_plant_commands"]-b["duplicate_plant_commands"],
            "duplicate_plant_commands_by_crop":{
                c:w["duplicate_plant_commands_by_crop"][c]-b["duplicate_plant_commands_by_crop"][c] for c in CROPS
            },
            "seed_inventory_day24":{
                c:w["seed_inventory_day24"][c]-b["seed_inventory_day24"][c] for c in CROPS
            },
            "terminal_self":w["terminal"]["self"]-b["terminal"]["self"],
        },
        "boundary":[
            "BUY_SEED counts are successfully executed public market units from Day14 onward.",
            "PLANT command counts are final model unit actions after all overlays.",
            "Successful PLANT requires observed seed consumption and immediate creation of the matching crop tile in World state.",
            "Day14 and Day24 seed inventory are snapshots; no internal motive is inferred from retained stock.",
            "The audit identifies connection loss only; it does not prescribe a planting policy or create WR-02."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("WR01_PURCHASE_PLANT_CONVERSION_AUDIT "+json.dumps({
        "seed":SEED,"seat":SEAT,
        "delta":payload["delta"],
        "baseline_terminal":b["terminal"],
        "wr01_terminal":w["terminal"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
