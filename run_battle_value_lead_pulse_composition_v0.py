#!/usr/bin/env python3
"""Battle Value Map — repeated lead-pulse productive composition v0.

Question:
Do Day13->14 and Day16->17 production-led pulses have the same public
productive-State composition?

Observation only. Same WB-0001 valuation basis.
No Action, cause, Representation, Evaluation, Direction, or Candidate.
"""
import json,os
from pathlib import Path
from kaggle_environments import make

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
TARGET_DAYS=(13,14,16,17)
OUT=Path(f"battle_value_lead_pulse_composition_v0_{SEED}_seat{SEAT}.json")


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)):return v
    if isinstance(v,dict):return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    return str(v)


def getv(x,key,default=None):
    if isinstance(x,dict):return x.get(key,default)
    try:return getattr(x,key)
    except Exception:return default


def side(obs):
    s=econ.derive_side(obs)
    c=s["committed_production"]
    return {
      "total_mark":float(c["same_basis_subtotal"]),
      "crop_total_mark":float(c["crop_current_price_potential_mark"]),
      "animal_total_mark":float(c["animal_base_current_price_potential_mark"]),
      "crop_count":{k:int(c["crop_count"].get(k,0) or 0) for k in econ.CROPS},
      "crop_potential_units":{k:int(c["crop_potential_units"].get(k,0) or 0) for k in econ.CROPS},
      "crop_mark_by_type":{k:float(c["crop_mark_by_type"].get(k,0) or 0) for k in econ.CROPS},
      "animal_count":{k:int(c["animal_count"].get(k,0) or 0) for k in econ.ANIMALS},
      "animal_potential_units":{k:int(c["animal_potential_units"].get(k,0) or 0) for k in econ.ANIMALS},
      "animal_mark_by_type":{k:float(c["animal_mark_by_type"].get(k,0) or 0) for k in econ.ANIMALS},
    }


def diff(a,b):
    # opponent minus self
    return {
      "total_mark":b["total_mark"]-a["total_mark"],
      "crop_total_mark":b["crop_total_mark"]-a["crop_total_mark"],
      "animal_total_mark":b["animal_total_mark"]-a["animal_total_mark"],
      "crop_count":{k:b["crop_count"][k]-a["crop_count"][k] for k in econ.CROPS},
      "crop_potential_units":{k:b["crop_potential_units"][k]-a["crop_potential_units"][k] for k in econ.CROPS},
      "crop_mark_by_type":{k:b["crop_mark_by_type"][k]-a["crop_mark_by_type"][k] for k in econ.CROPS},
      "animal_count":{k:b["animal_count"][k]-a["animal_count"][k] for k in econ.ANIMALS},
      "animal_potential_units":{k:b["animal_potential_units"][k]-a["animal_potential_units"][k] for k in econ.ANIMALS},
      "animal_mark_by_type":{k:b["animal_mark_by_type"][k]-a["animal_mark_by_type"][k] for k in econ.ANIMALS},
    }


def subtract(b,a):
    out={
      "total_mark":b["total_mark"]-a["total_mark"],
      "crop_total_mark":b["crop_total_mark"]-a["crop_total_mark"],
      "animal_total_mark":b["animal_total_mark"]-a["animal_total_mark"],
    }
    for field,keys in (
      ("crop_count",econ.CROPS),
      ("crop_potential_units",econ.CROPS),
      ("crop_mark_by_type",econ.CROPS),
      ("animal_count",econ.ANIMALS),
      ("animal_potential_units",econ.ANIMALS),
      ("animal_mark_by_type",econ.ANIMALS),
    ):
        out[field]={k:b[field][k]-a[field][k] for k in keys}
    return out


def main():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=body_only.agent
    env.run(players)

    states={}
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<2:continue
        so=plain(getv(step[SEAT],"observation"))
        oo=plain(getv(step[1-SEAT],"observation"))
        if not isinstance(so,dict) or not isinstance(oo,dict):continue
        d=int(so.get("day",0) or 0);h=int(so.get("hour",0) or 0)
        if d in TARGET_DAYS and h==0 and str(d) not in states:
            ss=side(so);oside=side(oo)
            states[str(d)]={"self":ss,"opponent":oside,"residual":diff(ss,oside)}

    if any(str(d) not in states for d in TARGET_DAYS):
        raise SystemExit(f"missing states {states.keys()}")

    pulses={
      "pulse_A_day13_to_14":subtract(states["14"]["residual"],states["13"]["residual"]),
      "pulse_B_day16_to_17":subtract(states["17"]["residual"],states["16"]["residual"]),
    }

    rewards=[float(x.reward) for x in env.state]
    payload={
      "schema":"kaggriculture.strong-origin-v2.battle-value-map.lead-pulse-composition.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "states":states,
      "pulse_residual_change":pulses,
      "boundary":[
        "Pulse composition is change in opponent-minus-self productive-State residual from interval start to end.",
        "Same WB-0001 current-price valuation basis is used for both pulse intervals.",
        "Counts, potential units, and marks remain separate.",
        "No Action, cause, Representation, Evaluation, Direction, Candidate, or policy mutation."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LEAD_PULSE_COMPOSITION "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "A":pulses["pulse_A_day13_to_14"],
      "B":pulses["pulse_B_day16_to_17"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
