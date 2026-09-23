#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"mode_to_action_reachability_path_v0_{SEED}.json")

def configure(mode):
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
    os.environ["ORIGIN_GUIDANCE_MODE"]=mode
    combat.set_probe_enabled(True); combat.set_attribution_enabled(True); combat.reset_telemetry()

def snaps(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def compact(s):
    i=dict(s.get("origin_internal",{}) or {})
    return {
      "turn":s.get("turn"),
      "day":s.get("day"),
      "remaining":s.get("remaining"),
      "money":s.get("money"),
      "reserve":s.get("reserve"),
      "cows":s.get("cows"),
      "wheat":s.get("wheat"),
      "feed_need":s.get("feed_need"),
      "choice":i.get("model_guidance_choice"),
      "reason":i.get("model_guidance_reason"),
      "regime":i.get("coarse_regime"),
      "boundary_changed":bool(i.get("coarse_boundary_changed",False)),
      "action":s.get("action")
    }

def play(mode):
    configure(mode)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=combat.agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    rows=[compact(s) for s in snaps(combat.get_trace()) if int(s.get("day",0) or 0)>=14]
    return {"self":rewards[SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"rows":rows}

def main():
    current=play("objective_pressure_guidance")
    coarse=play("coarse_boundary_guidance")
    a={r["turn"]:r for r in current["rows"]}; b={r["turn"]:r for r in coarse["rows"]}
    common=sorted(set(a)&set(b))

    mode_div_turn=None
    for t in common:
        if a[t].get("choice") != b[t].get("choice"):
            mode_div_turn=t
            break

    first_action_turn=None
    if mode_div_turn is not None:
        for t in common:
            if t < mode_div_turn: continue
            if a[t].get("action") != b[t].get("action"):
                first_action_turn=t
                break

    path=[]
    if mode_div_turn is not None:
        end=first_action_turn if first_action_turn is not None else common[-1]
        for t in common:
            if mode_div_turn <= t <= end:
                path.append({
                  "turn":t,
                  "same_action":a[t].get("action")==b[t].get("action"),
                  "current":a[t],
                  "coarse":b[t]
                })

    post_action_state=None
    if first_action_turn is not None:
        later=[t for t in common if t>first_action_turn]
        if later:
            t=later[0]
            post_action_state={
              "turn":t,
              "current":a[t],
              "coarse":b[t],
              "state_fields_differ":{
                k:a[t].get(k)!=b[t].get(k)
                for k in ["money","reserve","cows","wheat","feed_need","choice","regime"]
              }
            }

    payload={
      "schema":"kaggriculture.mode-to-action-reachability-path.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{
        "self_diff":coarse["self"]-current["self"],
        "margin_diff":coarse["margin"]-current["margin"]
      },
      "first_mode_divergence_turn":mode_div_turn,
      "first_action_divergence_turn":first_action_turn,
      "mode_to_action_distance":(
        first_action_turn-mode_div_turn
        if mode_div_turn is not None and first_action_turn is not None else None
      ),
      "same_action_turns_before_first_action_divergence":(
        sum(1 for x in path[:-1] if x["same_action"]) if first_action_turn is not None else None
      ),
      "path":path,
      "post_first_action_state":post_action_state,
      "boundary":[
        "Observer only.",
        "The path is temporal reachability evidence, not causal proof.",
        "The first mode divergence is a marker, not an established source of value."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
      "seed":SEED,
      "self_diff":payload["terminal"]["self_diff"],
      "mode_turn":mode_div_turn,
      "action_turn":first_action_turn,
      "distance":payload["mode_to_action_distance"],
      "path_len":len(path)
    },ensure_ascii=False))

if __name__=="__main__": main()
