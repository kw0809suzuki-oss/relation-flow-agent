#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ.get("BATTLE_SEED","7161"))
SEAT=int(os.environ.get("BATTLE_SEAT","0"))
OUT=Path(f"state_transition_pressure_trace_v0_{SEED}.json")
OPPONENT=base.OPPONENT

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
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=combat.agent
    env.run(players)

    rows=[]
    prev_choice=None
    for s in snapshots(combat.get_trace()):
        day=int(s.get("day",0) or 0)
        if day<14:
            continue
        internal=dict(s.get("origin_internal",{}) or {})
        opp=dict(s.get("opponent",{}) or {})
        money=s.get("money")
        reserve=internal.get("reserve")
        opp_money=opp.get("money")
        try: cash_buffer=float(money)-float(reserve)
        except Exception: cash_buffer=None
        try: relative_gap=float(money)-float(opp_money)
        except Exception: relative_gap=None
        cows=float(s.get("cows") or 0)
        wheat=float(s.get("wheat") or 0)
        feed_obligation_gap=max(0.0,cows*2.0-wheat)
        nd=internal.get("native_desired_units")
        ru=internal.get("realizable_units")
        try: desired_realizable_gap=float(nd)-float(ru)
        except Exception: desired_realizable_gap=None
        choice=internal.get("model_guidance_choice")
        rows.append({
          "turn":s.get("turn"),"day":day,"remaining":s.get("remaining"),
          "money":money,"reserve":reserve,"cash_buffer":cash_buffer,
          "opponent_money":opp_money,"relative_money_gap":relative_gap,
          "cows":s.get("cows"),"wheat":s.get("wheat"),"feed_need":s.get("feed_need"),
          "feed_obligation_gap":feed_obligation_gap,
          "native_desired_units":nd,"realizable_units":ru,
          "desired_minus_realizable":desired_realizable_gap,
          "empty_tile_count":internal.get("empty_tile_count"),
          "land_activation_capacity":internal.get("land_activation_capacity"),
          "land_realizable_ok":internal.get("land_realizable_ok"),
          "choice":choice,"reason":internal.get("model_guidance_reason"),
          "choice_changed_from_previous":choice!=prev_choice if prev_choice is not None else False,
          "action":s.get("action"),
        })
        prev_choice=choice

    payload={
      "schema":"kaggriculture.state-transition-pressure-trace.v0",
      "seed":SEED,"seat":SEAT,
      "purpose":"Observation-only temporal trace. No pressure label, causal interpretation, or mode-quality judgment is assigned.",
      "rows":rows
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"rows":len(rows),"choice_changes":sum(1 for r in rows if r["choice_changed_from_previous"])},ensure_ascii=False))

if __name__=="__main__": main()
