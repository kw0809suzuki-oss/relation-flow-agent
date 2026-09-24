#!/usr/bin/env python3
"""P12 Initial Commitment Rescue v0 preflight, seed 7351 only.

Compares Body-only v0 against the same Body-only with only Day0 Strong Origin
work-target reservation enabled. Reads Day1/Day4 state and terminal outcome.
"""
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as baseline
import strong_origin_v2_p12_initial_commitment_rescue_v0 as rescue

SEED=int(os.environ.get("BATTLE_SEED","7351"))
SEAT=int(os.environ.get("BATTLE_SEAT","0"))
OUT=Path(f"p12_initial_commitment_rescue_v0_{SEED}.json")

def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    if hasattr(v,"tolist"):
        try:return plain(v.tolist())
        except Exception:pass
    if hasattr(v,"item"):
        try:return plain(v.item())
        except Exception:pass
    return str(v)

def first_obs_for_day(env,seat,day):
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<2: continue
        obs=plain(getattr(step[seat],"observation",None))
        if isinstance(obs,dict) and int(obs.get("day",0) or 0)==day:
            return obs
    return None

def summarize(obs,seat):
    if not obs: return None
    farms=obs.get("farms",[]) or []
    me=farms[seat]
    private=obs.get("private",{}) or {}
    tiles=me.get("tiles",[]) or []
    crop={}; animal={}; occupied=0; empty=0
    d0_crop={}
    for row in tiles:
        for t in row:
            if t=="LOCKED": continue
            if t is None:
                empty+=1; continue
            occupied+=1
            if isinstance(t,dict):
                if t.get("kind")=="PLANT":
                    c=t.get("crop"); crop[c]=crop.get(c,0)+1
                    if int(t.get("planted_day",-999))==0:
                        d0_crop[c]=d0_crop.get(c,0)+1
                if t.get("kind")=="PASTURE":
                    a=t.get("animal"); animal[a]=animal.get(a,0)+1
    return {
        "money":me.get("money"),
        "seeds":plain(private.get("seeds",{})),
        "crop":crop,
        "animal":animal,
        "day0_origin_crop":d0_crop,
        "occupied":occupied,
        "empty":empty,
        "hands":len(me.get("hands",[]) or []),
    }

def configure(agent):
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    agent.reset_telemetry()

def run(agent):
    configure(agent)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    ps=[basecfg.OPPONENT,basecfg.OPPONENT]
    ps[SEAT]=agent.agent
    env.run(ps)
    rewards=[float(x.reward) for x in env.state]
    return {
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "day1":summarize(first_obs_for_day(env,SEAT,1),SEAT),
      "day4":summarize(first_obs_for_day(env,SEAT,4),SEAT),
    }

b=run(baseline)
r=run(rescue)
payload={
  "schema":"kaggriculture.p12.initial-commitment-rescue.v0",
  "seed":SEED,"seat":SEAT,
  "baseline":b,"rescue":r,
  "delta_terminal_self":r["terminal"]["self"]-b["terminal"]["self"],
  "boundary":[
    "Only Day0 Strong Origin work-target reservation differs.",
    "Body-only v0 D14 closure and all Day1+ policy behavior remain unchanged.",
    "Preflight is one seed only; no generalization."
  ]
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("P12_INITIAL_COMMITMENT_RESCUE "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))
