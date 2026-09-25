"""WR-02 + WR-03 Bundle v0.

WR-03 first connects generated Return to the next native productive surface by
temporarily releasing only Origin reserve_base.
WR-02 then deconflicts duplicate same-tile PLANT commands on the final action.

No product, crop, LAND, HIRE, position, or quantity is prescribed here.
"""
import wr03_cycle_carry_reserve_release_v0 as wr03
import wr02_same_tile_plant_deconfliction_v0 as wr02

_state={}


def reset_telemetry():
    global _state
    wr03.reset_telemetry()
    wr02._state={
        "turns":0,
        "duplicate_plant_commands_seen":0,
        "deconflicted_to_move":0,
        "deconflicted_to_pass":0,
        "events":[],
    }
    _state={"turns":0}


def agent(obs):
    if not _state:
        reset_telemetry()
    action=wr03.agent(obs)
    revised,changes=wr02.deconflict(obs,action)
    wr02._state["turns"]+=1
    if changes:
        wr02._state["events"].append({
            "day":int(obs.get("day",0) or 0),
            "hour":int(obs.get("hour",0) or 0),
            "changes":changes,
        })
    _state["turns"]+=1
    return revised


def get_telemetry():
    return {
        "wr_bundle_wr02_wr03":True,
        "wr03":wr03.get_telemetry(),
        "wr02":{
            "turns":wr02._state.get("turns",0),
            "duplicate_plant_commands_seen":wr02._state.get("duplicate_plant_commands_seen",0),
            "deconflicted_to_move":wr02._state.get("deconflicted_to_move",0),
            "deconflicted_to_pass":wr02._state.get("deconflicted_to_pass",0),
            "events":list(wr02._state.get("events",[])),
        },
    }
