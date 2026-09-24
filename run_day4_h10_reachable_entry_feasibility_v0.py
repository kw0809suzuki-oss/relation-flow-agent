#!/usr/bin/env python3
"""Day4 h10 Next-Cycle Reachable Entry Feasibility Probe v0.

No Candidate and no policy mutation.

Replays the same fixed Fresh10 only because the existing raw audit omitted
hourly unit positions. At Day4 hour10 (the saved State immediately before the
first opponent next-cycle-positioned G1 appears at hour11), records:
- self Cash / seeds / empty unlocked tiles / unit positions
- shortest public-rule movement distance from any self unit to an empty tile
- whether an existing MELON seed can be planted before Day4 ends
- public maturity position of such a Day4 MELON

This is an existence test, not a policy recommendation.
"""
import json,os
from pathlib import Path
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"day4_h10_reachable_entry_feasibility_v0_{SEED}.json")


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


def pos_list(farm):
    out=[tuple(farm["farmer"])]
    out.extend(tuple(x) for x in (farm.get("hands",[]) or []))
    return out


def empty_unlocked(farm):
    out=[]
    for y,row in enumerate(farm.get("tiles",[]) or []):
        for x,t in enumerate(row or []):
            if t is None:
                out.append((x,y))
    return out


def main():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=body_only.agent
    env.run(players)

    target=None
    for step_index,step in enumerate(getattr(env,"steps",[]) or []):
        obs=plain(getv(step[SEAT],"observation"))
        if isinstance(obs,dict) and int(obs.get("day",-1))==4 and int(obs.get("hour",-1))==10:
            target=(step_index,obs)
            break
    if target is None:
        raise SystemExit("Day4 hour10 State not found")

    step_index,obs=target
    farm=obs["farms"][SEAT]
    private=obs.get("private",{}) or {}
    units=pos_list(farm)
    empties=empty_unlocked(farm)

    pairs=[]
    for ui,u in enumerate(units):
        for e in empties:
            d=abs(u[0]-e[0])+abs(u[1]-e[1])
            pairs.append((d,ui,u,e))
    pairs.sort()
    best=pairs[0] if pairs else None
    min_dist=best[0] if best else None

    hour=10
    remaining_action_turns=24-hour
    melon_seeds=int((private.get("seeds",{}) or {}).get("MELON",0) or 0)
    # d MOVE actions + one PLANT action; movement onto LOCKED is public-rule legal.
    plant_before_day_end=bool(
        melon_seeds>0 and empties and min_dist is not None
        and min_dist+1 <= remaining_action_turns
    )

    result={
        "schema":"kaggriculture.strong-origin-v2.day4-h10-next-cycle-entry-feasibility.v0",
        "seed":SEED,"seat":SEAT,
        "state":{"day":4,"hour":10,"step_index":step_index},
        "cash":float(farm.get("money",0) or 0),
        "seed_stock":{k:int(v or 0) for k,v in (private.get("seeds",{}) or {}).items()},
        "unit_positions":[list(x) for x in units],
        "empty_unlocked_count":len(empties),
        "closest_empty_path":{
            "manhattan_moves":min_dist,
            "unit_index":best[1] if best else None,
            "unit_position":list(best[2]) if best else None,
            "empty_tile":list(best[3]) if best else None,
        },
        "remaining_action_turns_in_day":remaining_action_turns,
        "certified_existing_seed_entry":{
            "asset":"MELON",
            "seed_available":melon_seeds,
            "movement_plus_plant_actions":None if min_dist is None else min_dist+1,
            "can_enter_productive_state_before_day5":plant_before_day_end,
            "origin_day_if_planted":4,
            "public_next_production_day_if_planted_day4":10,
            "public_harvest_eligible_day_if_planted_day4":14,
            "reaches_day8_to_12_production_window":plant_before_day_end,
            "reaches_day8_to_12_harvest_window":False,
        },
        "boundary":[
            "This certifies existence of at least one action path under public movement/plant/maturity rules; it does not claim the current policy should choose it.",
            "The path uses seed already held at Day4 h10; no market purchase is required.",
            "Future care actions are required for crop survival/production; this probe does not claim they would be selected by the current policy.",
            "No asset is declared optimal and no terminal effect is inferred."
        ]
    }
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DAY4_H10_REACHABLE_ENTRY_FEASIBILITY "+json.dumps(result,ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
