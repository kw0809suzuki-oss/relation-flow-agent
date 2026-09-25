"""WR-01 + WR-02 Bundle v0.

WR-01: reopen native Day14+ productive purchases only when first public output
boundary is terminal-reachable.

WR-02: deconflict same-tile simultaneous PLANT commands at Day14+.

WR-02 is applied only after WR-01 has produced the final model action.
"""
import world_reference_reachability_candidate_v0 as wr01
import wr02_same_tile_plant_deconfliction_v0 as wr02

_state={}


def reset_telemetry():
    global _state
    wr01.reset_telemetry()
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
    action=wr01.agent(obs)
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
        "wr_bundle_wr01_wr02":True,
        "wr01":wr01.get_telemetry(),
        "wr02":{
            "turns":wr02._state.get("turns",0),
            "duplicate_plant_commands_seen":wr02._state.get("duplicate_plant_commands_seen",0),
            "deconflicted_to_move":wr02._state.get("deconflicted_to_move",0),
            "deconflicted_to_pass":wr02._state.get("deconflicted_to_pass",0),
            "events":list(wr02._state.get("events",[])),
        },
    }
