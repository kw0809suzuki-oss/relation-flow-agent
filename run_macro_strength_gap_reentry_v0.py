#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"macro_strength_gap_reentry_v0_{SEED}.json")

def configure():
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
    combat.set_probe_enabled(True); combat.set_attribution_enabled(True); combat.reset_telemetry()

def visible(farm):
    crops=0; animals=0; occupied=0
    for row in farm.get("tiles",[]) or []:
        for tile in row:
            if tile=="LOCKED" or tile is None:
                continue
            if isinstance(tile,dict):
                kind=tile.get("kind")
                if kind=="PLANT": crops += 1
                if tile.get("animal") is not None or kind=="ANIMAL": animals += 1
                if kind in ("PLANT","ANIMAL") or tile.get("animal") is not None:
                    occupied += 1
    return {
      "money":float(farm.get("money",0) or 0),
      "hands":len(farm.get("hands",[]) or []),
      "land":len(farm.get("unlocked_quadrants",[]) or []),
      "crop_tiles":crops,
      "animal_tiles":animals,
      "production_tiles":occupied,
    }

def main():
    configure()
    trace=[]
    def observed(obs):
        me=obs["farms"][obs["player"]]
        opp=obs["farms"][1-obs["player"]]
        trace.append({
          "turn":len(trace),
          "day":int(obs.get("day",0) or 0),
          "self":visible(me),
          "opponent":visible(opp)
        })
        return combat.agent(obs)

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=observed
    env.run(players)
    rewards=[float(s.reward) for s in env.state]

    day_end={}
    for r in trace:
        day_end[r["day"]]=r
    days=[]
    for d in sorted(day_end):
        r=day_end[d]
        gaps={k:r["opponent"][k]-r["self"][k] for k in r["self"]}
        days.append({"day":d,"self":r["self"],"opponent":r["opponent"],"gap":gaps})

    payload={
      "schema":"kaggriculture.macro-strength-gap-reentry.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{
        "self":rewards[SEAT],
        "opponent":rewards[1-SEAT],
        "residual":rewards[1-SEAT]-rewards[SEAT]
      },
      "day_end":days,
      "boundary":"Visible comparable Battle-wide observation only. No causal attribution."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"self":rewards[SEAT],"opp":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},ensure_ascii=False))

if __name__=="__main__": main()
