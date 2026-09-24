#!/usr/bin/env python3
"""Battle Value Map — Day0 Animal Productive-State Composition v0.

Opens exactly one public-State layer beneath the repeated Day0 animal residual.
No action, cause, representation, evaluation, direction, or candidate.
"""
import json, os
from pathlib import Path
from kaggle_environments import make

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
TARGETS={(0,10),(0,14),(0,17)}
OUT=Path(f"battle_value_map_day0_animal_composition_v0_{SEED}_seat{SEAT}.json")

def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception: pass
    return str(v)

def side_animal(obs):
    s=econ.derive_side(obs)
    c=s["committed_production"]
    return {
        "animal_count":{k:int(c["animal_count"].get(k,0) or 0) for k in econ.ANIMALS},
        "animal_potential_units":{k:int(c["animal_potential_units"].get(k,0) or 0) for k in econ.ANIMALS},
        "animal_mark_by_type":{k:float(c["animal_mark_by_type"].get(k,0) or 0) for k in econ.ANIMALS},
        "animal_total_mark":float(c["animal_base_current_price_potential_mark"]),
    }

def main():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=body_only.agent
    env.run(players)

    checkpoints={}
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<2: continue
        self_obs=plain(getattr(step[SEAT],"observation",None))
        opp_obs=plain(getattr(step[1-SEAT],"observation",None))
        if not isinstance(self_obs,dict) or not isinstance(opp_obs,dict): continue
        key=(int(self_obs.get("day",0) or 0),int(self_obs.get("hour",0) or 0))
        if key not in TARGETS: continue
        ss=side_animal(self_obs); oo=side_animal(opp_obs)
        residual={
            "animal_total_mark":oo["animal_total_mark"]-ss["animal_total_mark"],
            "animal_count_by_type":{k:oo["animal_count"][k]-ss["animal_count"][k] for k in econ.ANIMALS},
            "animal_potential_units_by_type":{k:oo["animal_potential_units"][k]-ss["animal_potential_units"][k] for k in econ.ANIMALS},
            "animal_mark_by_type":{k:oo["animal_mark_by_type"][k]-ss["animal_mark_by_type"][k] for k in econ.ANIMALS},
        }
        checkpoints[f"day{key[0]}_h{key[1]}"]={"self":ss,"opponent":oo,"residual":residual}

    rewards=[float(x.reward) for x in env.state]
    payload={
      "schema":"kaggriculture.strong-origin-v2.battle-value-map.day0-animal-composition.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "checkpoints":checkpoints,
      "boundary":[
        "Only public animal productive-State composition is opened.",
        "Counts, potential units, and current-price marks remain separate.",
        "No Action, purchase, placement cause, Representation, Evaluation, Direction, Candidate, or policy mutation.",
        "Current-price potential mark is valuation under the existing WB-0001 assumptions, not realized Cash."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DAY0_ANIMAL_COMPOSITION "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "checkpoints":{k:v["residual"] for k,v in checkpoints.items()}
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
