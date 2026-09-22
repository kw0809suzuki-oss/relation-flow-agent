#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"state_interpretation_shadow_probe_v0_{SEED}.json")

GUIDANCE={
  "current_thought":"The useful amount of slack may depend on what is currently under pressure: own resource continuity, relative position, or neither.",
  "autonomy":"This is only a way of seeing the State. Decide for yourself which pressure matters now, whether this framing applies, and how strongly to use it.",
  "search_task":"Inspect the current State and choose the smallest commitment adjustment that fits the pressure you infer. You may keep native behavior if no adjustment is justified."
}

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

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def compact_state(s):
    internal=dict(s.get("origin_internal",{}) or {})
    opp=dict(s.get("opponent",{}) or {})
    return {
      "day":s.get("day"),
      "remaining":s.get("remaining"),
      "self":{
        "money":s.get("money"),
        "units":s.get("units"),
        "cows":s.get("cows"),
        "wheat":s.get("wheat"),
        "land":s.get("land"),
        "feed_need":s.get("feed_need"),
      },
      "opponent":{
        "money":opp.get("money"),
        "land":opp.get("land"),
        "hands":opp.get("hands"),
        "supply":opp.get("supply"),
      },
      "model_state":{
        "strategy_name":internal.get("strategy_name"),
        "reserve":internal.get("reserve"),
        "empty_tile_count":internal.get("empty_tile_count"),
        "seed_stock":internal.get("seed_stock"),
        "live_plants":internal.get("live_plants"),
        "native_desired_units":internal.get("native_desired_units"),
        "realizable_units":internal.get("realizable_units"),
        "land_activation_capacity":internal.get("land_activation_capacity"),
        "land_realizable_ok":internal.get("land_realizable_ok"),
      }
    }

def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=combat.agent; env.run(players)

    candidates=[]
    for s in snapshots(combat.get_trace()):
        if int(s.get("day",0) or 0)<14: continue
        internal=dict(s.get("origin_internal",{}) or {})
        choice=internal.get("model_guidance_choice")
        reason=internal.get("model_guidance_reason")
        reserve=internal.get("reserve")
        money=s.get("money")
        try:
            liquidity_gap=float(money)-float(reserve)
        except Exception:
            liquidity_gap=None
        candidates.append({
          "turn":s.get("turn"),"day":s.get("day"),
          "choice":choice,"reason":reason,
          "liquidity_gap":liquidity_gap,
          "state":compact_state(s),
        })

    selected=[]
    used=set()
    def add(item,criterion):
        if not item: return
        key=item["turn"]
        if key in used: return
        used.add(key)
        selected.append({
          "sample_id":f"{SEED}-{key}",
          "sampling_criterion":criterion,
          "interview_input":{
            "state":item["state"],
            "flowchan_guidance":GUIDANCE,
            "available_modes":["throughput_match","throughput_with_slack","native"]
          },
          "sealed_actual":{
            "battle_choice":item["choice"],
            "battle_reason":item["reason"]
          }
        })

    add(next((x for x in candidates if x["choice"]=="throughput_match"),None),"first_match_choice")
    add(next((x for x in candidates if x["choice"]=="native"),None),"first_native_choice")
    low=[x for x in candidates if x["liquidity_gap"] is not None]
    add(min(low,key=lambda x:x["liquidity_gap"]) if low else None,"minimum_money_minus_reserve")

    payload={
      "schema":"kaggriculture.state-interpretation-shadow-probe.v0",
      "seed":SEED,"seat":SEAT,
      "purpose":"Measure fresh interpretation response to saved State; not hidden-reasoning reconstruction.",
      "samples":selected,
      "boundary":[
        "Actual Battle choice is sealed from the interview input.",
        "Sampling criterion is not a semantic label such as slack-state.",
        "Interview response is a new interpretation measurement, not evidence of the runtime model's hidden reasoning."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"sample_count":len(selected)},ensure_ascii=False))

if __name__=="__main__": main()
