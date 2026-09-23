#!/usr/bin/env python3
import json, os, importlib
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"crop_maintenance_protection_v0_{SEED}.json")

def configure_env():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    for k in ["OUTER_MEANING_OPTION_PRESERVATION_DAY","OUTER_MEANING_REALIZABLE_CAPACITY_DAY","OUTER_MEANING_CONVERSION_PATH_DAY","OUTER_MEANING_GUIDED_CONVERSION_DAY"]:
        os.environ.pop(k,None)
    os.environ["OUTER_MEANING_OBJECTIVE_PRESSURE_DAY"]="14"
    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"
    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1"
    os.environ["ORIGIN_GUIDANCE_MODE"]="objective_pressure_guidance"

def visible(obs, player):
    farm=obs["farms"][player]
    crops=animals=prod=0
    for row in farm.get("tiles",[]) or []:
        for tile in row:
            if not isinstance(tile,dict): continue
            if tile.get("kind")=="PLANT":
                crops+=1; prod+=1
            if tile.get("animal") is not None or tile.get("kind")=="ANIMAL":
                animals+=1; prod+=1
    return {
      "money":float(farm.get("money",0) or 0),
      "hands":len(farm.get("hands",[]) or []),
      "land":len(farm.get("unlocked_quadrants",[]) or []),
      "crop_tiles":crops,
      "animal_tiles":animals,
      "production_tiles":prod
    }

def run_arm(module_name):
    configure_env()
    mod=importlib.import_module(module_name)
    mod.set_probe_enabled(True)
    if hasattr(mod,"set_attribution_enabled"): mod.set_attribution_enabled(True)
    mod.reset_telemetry()
    day_end={}
    def wrapped(obs):
        day=int(obs.get("day",0) or 0)
        if day in (5,7,10,12,15,20,26):
            day_end[day]=visible(obs,obs["player"])
        return mod.agent(obs)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=wrapped
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "day_end":day_end,
      "telemetry":mod.get_telemetry() if hasattr(mod,"get_telemetry") else {}
    }

def main():
    current=run_arm("g17_agent")
    candidate=run_arm("crop_maintenance_protection_v0")
    payload={
      "schema":"kaggriculture.crop-maintenance-protection.v0",
      "seed":SEED,"seat":SEAT,
      "current":current,"candidate":candidate,
      "delta_self":candidate["terminal"]["self"]-current["terminal"]["self"],
      "delta_margin":(candidate["terminal"]["self"]-candidate["terminal"]["opponent"])-(current["terminal"]["self"]-current["terminal"]["opponent"]),
      "boundary":"Only base WATER/PLANT/HARVEST slots changed by livestock overlay are restored on day5-12."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"self_current":current["terminal"]["self"],"self_candidate":candidate["terminal"]["self"],"delta":payload["delta_self"]},ensure_ascii=False))

if __name__=="__main__": main()
