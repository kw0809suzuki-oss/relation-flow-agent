#!/usr/bin/env python3
"""Composition Transformation Audit v0.

Compares exactly three lanes at Day0 h13 -> h14:
- baseline self
- baseline Seyamalam
- Formation Position Candidate self

For newly formed productive assets, attach public-rule time-to-return fields from
asset_state_schedule_v0.json. No new Candidate is introduced.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as baseline
import formation_position_candidate_v0 as position_candidate
import run_asset_formation_map_v0 as af
import run_h13_formation_feasibility_v0 as feas

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"composition_transformation_audit_v0_{SEED}_seat{SEAT}.json")
SCHEDULE=json.loads(Path("asset_state_schedule_v0.json").read_text(encoding="utf-8"))
TPD=int(SCHEDULE["world"]["default_turns_per_day"])
ENTRY_DAY=0
ENTRY_HOUR=13

def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"

def snapshot_from_steps(env, day, hour):
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<2:
            continue
        obs=[af.plain(af.getv(step[p],"observation")) for p in (0,1)]
        if not all(isinstance(o,dict) for o in obs):
            continue
        if int(obs[0].get("day",0) or 0)==day and int(obs[0].get("hour",0) or 0)==hour:
            return obs
    raise RuntimeError(f"missing snapshot day={day} hour={hour}")

def play(agent_fn, reset_fn):
    configure()
    reset_fn()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=agent_fn
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    return {
        "h13":snapshot_from_steps(env,0,13),
        "h14":snapshot_from_steps(env,0,14),
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
        },
    }

def asset_identity(tile):
    if not isinstance(tile,dict):
        return None
    if tile.get("kind")=="PLANT" and tile.get("crop"):
        return ("crop",str(tile["crop"]))
    if tile.get("animal"):
        return ("animal",str(tile["animal"]))
    return None

def farm(obs,pidx):
    return (obs.get("farms",[]) or [])[pidx]

def new_asset_tiles(before_obs,after_obs,pidx):
    bf=farm(before_obs,pidx); afarm=farm(after_obs,pidx)
    btiles=bf.get("tiles",[]) or []; atiles=afarm.get("tiles",[]) or []
    out=[]
    for y,row in enumerate(atiles):
        for x,after in enumerate(row or []):
            before=btiles[y][x] if y<len(btiles) and x<len(btiles[y]) else None
            bid=asset_identity(before); aid=asset_identity(after)
            if aid is not None and aid != bid:
                out.append({
                    "x":x,"y":y,
                    "asset_class":aid[0],
                    "asset_type":aid[1],
                    "before_identity":list(bid) if bid else None,
                    "after_tile":af.plain(after),
                })
    return out

def public_return(asset_type, tile):
    spec=SCHEDULE["assets"].get(asset_type)
    if not spec:
        return {"status":"NO_SCHEDULE_ENTRY"}
    prod=spec.get("production",{})
    cls=spec.get("asset_class")
    if "first_harvest_eligible_day_offset" in prod:
        offset=int(prod["first_harvest_eligible_day_offset"])
        kind="first_harvest_eligible"
    elif "first_output_day_offset" in prod:
        offset=int(prod["first_output_day_offset"])
        kind="first_automatic_output"
    else:
        return {"status":"NO_FIRST_RETURN_OFFSET"}

    origin_day=int(tile.get("planted_day",tile.get("placed_day",ENTRY_DAY)) or 0)
    boundary_day=origin_day+offset
    turns_from_entry=max(0,boundary_day*TPD-ENTRY_HOUR)
    harvestable_offset=prod.get("harvest_eligible_from_day_offset",offset)
    harvestable_day=origin_day+int(harvestable_offset)

    return {
        "status":"DERIVED_PUBLIC_RULE",
        "output_item":spec.get("output_item"),
        "production_mode":prod.get("mode"),
        "origin_day":origin_day,
        "observed_formation_interval":{"day":0,"from_hour":13,"to_hour":14},
        "entry_hour_for_boundary_formula":ENTRY_HOUR,
        "first_return_boundary_kind":kind,
        "first_return_day":boundary_day,
        "turns_from_h13_entry_to_first_return_boundary":turns_from_entry,
        "first_harvestable_day":harvestable_day,
        "base_held_units_on_entry":prod.get("base_held_units_on_entry"),
        "no_fertilizer_max_held_if_all_window_waters":prod.get("no_fertilizer_max_held_if_all_window_waters"),
        "held_yield_cap":prod.get("held_yield_cap"),
        "conditional_note":(
            "Public timing only. Survival and any required future WATER/FEED remain Battle-path dependent."
        ),
    }

def lane(before_obs,after_obs,pidx):
    resources=feas.h13_resources(before_obs,pidx)
    c13=feas.composition(before_obs,pidx,0)
    c14=feas.composition(after_obs,pidx,0)
    delta=feas.delta(c13,c14)
    tiles=new_asset_tiles(before_obs,after_obs,pidx)
    new_assets=[]
    for z in tiles:
        rr=public_return(z["asset_type"],z["after_tile"])
        new_assets.append({**z,"public_return":rr})
    profile={}
    for z in new_assets:
        typ=z["asset_type"]
        rr=z["public_return"]
        p=profile.setdefault(typ,{
            "quantity":0,
            "first_return_day":rr.get("first_return_day"),
            "turns_from_h13_entry_to_first_return_boundary":rr.get("turns_from_h13_entry_to_first_return_boundary"),
            "first_harvestable_day":rr.get("first_harvestable_day"),
            "production_mode":rr.get("production_mode"),
            "output_item":rr.get("output_item"),
        })
        p["quantity"]+=1
    return {
        "h13_resources":resources,
        "h13_composition":c13,
        "h14_composition":c14,
        "h13_to_h14_present_asset_delta":delta,
        "new_asset_instances":new_assets,
        "new_asset_return_profile_by_type":profile,
    }

def cumulative_boundary_profile(lane_data):
    events=[]
    for typ,p in lane_data["new_asset_return_profile_by_type"].items():
        if p.get("first_return_day") is None:
            continue
        events.append({
            "asset_type":typ,
            "quantity":p["quantity"],
            "first_return_day":p["first_return_day"],
            "turns_from_h13":p["turns_from_h13_entry_to_first_return_boundary"],
        })
    days=sorted(set(e["first_return_day"] for e in events))
    return [
        {
            "by_day":d,
            "cumulative_new_asset_count_reaching_first_return_boundary":sum(
                e["quantity"] for e in events if e["first_return_day"]<=d
            ),
            "asset_types":{
                e["asset_type"]:e["quantity"] for e in events if e["first_return_day"]<=d
            },
        }
        for d in days
    ]

def main():
    b=play(baseline.agent,baseline.reset_telemetry)
    c=play(position_candidate.agent,position_candidate.reset_telemetry)

    baseline_self=lane(b["h13"][SEAT],b["h14"][SEAT],SEAT)
    baseline_opponent=lane(b["h13"][1-SEAT],b["h14"][1-SEAT],1-SEAT)
    candidate_self=lane(c["h13"][SEAT],c["h14"][SEAT],SEAT)

    lanes={
        "baseline_self":baseline_self,
        "baseline_seyamalam":baseline_opponent,
        "position_candidate_self":candidate_self,
    }
    for v in lanes.values():
        v["cumulative_first_return_profile"]=cumulative_boundary_profile(v)

    payload={
        "schema":"kaggriculture.strong-origin-v2.composition-transformation-audit.v0",
        "seed":SEED,
        "seat":SEAT,
        "baseline_terminal":b["terminal"],
        "position_candidate_terminal":c["terminal"],
        "lanes":lanes,
        "boundary":[
            "The audit compares h13 World resources to h14 newly formed productive Asset State.",
            "New asset identity is a structural tile-state transition only.",
            "Time-to-return is derived from asset_state_schedule_v0 public rules and the observed h13->h14 formation interval.",
            "For nonongoing crops, first return means first harvest-eligible boundary; future WATER/survival conditions remain conditional.",
            "No market value, expected score, asset preference, new Candidate, or adoption conclusion is introduced.",
        ],
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("COMPOSITION_TRANSFORMATION_AUDIT "+json.dumps({
        "seed":SEED,
        "seat":SEAT,
        "baseline_self":baseline_self["new_asset_return_profile_by_type"],
        "baseline_seyamalam":baseline_opponent["new_asset_return_profile_by_type"],
        "position_candidate_self":candidate_self["new_asset_return_profile_by_type"],
        "baseline_terminal":b["terminal"],
        "position_candidate_terminal":c["terminal"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
