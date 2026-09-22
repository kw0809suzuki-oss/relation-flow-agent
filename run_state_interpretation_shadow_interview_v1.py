#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
BLIND=Path(f"shadow_interview_blind_{SEED}.json")
SEALED=Path(f"shadow_interview_sealed_{SEED}.json")

GUIDANCE={
  "current_thought":"The useful amount of slack may depend on what is currently under pressure: own resource continuity, relative position, or neither.",
  "autonomy":"This is only a way of seeing the State. Decide for yourself which pressure matters now, whether this framing applies, and how strongly to use it.",
  "search_task":"Inspect the current State and choose the smallest commitment adjustment that fits the pressure you infer. You may keep native behavior if no adjustment is justified."
}
MODES=["throughput_match","throughput_with_slack","native"]

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
      "day":s.get("day"), "remaining":s.get("remaining"),
      "self":{"money":s.get("money"),"units":s.get("units"),"cows":s.get("cows"),"wheat":s.get("wheat"),"land":s.get("land"),"feed_need":s.get("feed_need")},
      "opponent":{"money":opp.get("money"),"land":opp.get("land"),"hands":opp.get("hands"),"supply":opp.get("supply")},
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
        if choice not in MODES:
            continue
        reserve=internal.get("reserve")
        money=s.get("money")
        remaining=s.get("remaining")
        cows=s.get("cows") or 0
        wheat=s.get("wheat") or 0
        try: cash_buffer=float(money)-float(reserve)
        except Exception: cash_buffer=None
        feed_gap=max(0.0,float(cows)*2.0-float(wheat))
        try:
            desired_gap=float(internal.get("native_desired_units"))-float(internal.get("realizable_units"))
        except Exception:
            desired_gap=None
        candidates.append({
          "turn":s.get("turn"),"day":s.get("day"),"choice":choice,
          "reason":internal.get("model_guidance_reason"),
          "cash_buffer":cash_buffer,"feed_gap":feed_gap,"desired_gap":desired_gap,
          "remaining":remaining,"state":compact_state(s),
        })

    selected=[]; used=set()
    def add(item,criterion):
        if not item or item["turn"] in used: return
        used.add(item["turn"])
        selected.append({
          "sample_id":f"{SEED}-{item['turn']}",
          "sampling_criterion":criterion,
          "interview_input":{
            "state":item["state"],
            "flowchan_guidance":GUIDANCE,
            "available_modes":MODES,
            "fixed_protocol":{
              "stage1":"Without using mode names, list pressures, slack, bottlenecks, and continuity conditions. For each: state evidence, importance high/medium/low, confidence high/medium/low. Say none if absent.",
              "stage2":"For each available mode independently report fit 0-10, fit_band high/medium/low, supporting_evidence, contradicting_evidence, uncertainty.",
              "stage3":"Choose one preferred_mode, nearest_alternative, and the smallest condition that would switch the choice.",
              "stage4":"Name the State variable(s) required to judge the primary pressure and whether each is present in this State.",
              "stage5":"Describe how the preferred mode would be converted to an Action: what must be preserved, what may be lost, and whether the defining property survives projection."
            }
          }
        })

    add(next((x for x in candidates if x["choice"]=="throughput_match"),None),"first_match_choice")
    add(next((x for x in candidates if x["choice"]=="native"),None),"first_native_choice")
    vals=[x for x in candidates if x["cash_buffer"] is not None]
    add(min(vals,key=lambda x:x["cash_buffer"]) if vals else None,"minimum_cash_buffer")
    feed=[x for x in candidates if x["feed_gap"]>0]
    add(max(feed,key=lambda x:x["feed_gap"]) if feed else None,"maximum_feed_obligation_gap")
    dg=[x for x in candidates if x["desired_gap"] is not None]
    add(max(dg,key=lambda x:x["desired_gap"]) if dg else None,"maximum_desired_minus_realizable")

    blind={
      "schema":"kaggriculture.shadow-interview.blind.v1","seed":SEED,"seat":SEAT,
      "purpose":"Fresh interpretation measurement from saved State; not hidden-reasoning reconstruction.",
      "samples":selected
    }
    sealed={
      "schema":"kaggriculture.shadow-interview.sealed.v1","seed":SEED,"seat":SEAT,
      "actuals":[{"sample_id":f"{SEED}-{x['turn']}","battle_choice":x["choice"],"battle_reason":x["reason"]} for x in candidates if x["turn"] in used]
    }
    BLIND.write_text(json.dumps(blind,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SEALED.write_text(json.dumps(sealed,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"blind_samples":len(selected)},ensure_ascii=False))

if __name__=="__main__": main()
