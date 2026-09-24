#!/usr/bin/env python3
"""Paired Battle: Day4 PLANT Conflict Transform v0.

Primary evaluation is terminal self.
Baseline and candidate share seed/seat/opponent/configuration.
Only candidate's post-projection transformation arbitration differs.
"""
import copy,json,os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as baseline
import strong_origin_v2_plant_conflict_transform_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"plant_conflict_transform_battle_v0_{SEED}.json")


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    return str(v)


def getv(x,key,default=None):
    if isinstance(x,dict):return x.get(key,default)
    try:return getattr(x,key)
    except Exception:return default


def configure(agent):
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    agent.reset_telemetry()


def first_obs(env,seat,day):
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<2:continue
        obs=plain(getv(step[seat],"observation"))
        if isinstance(obs,dict) and int(obs.get("day",-1))==day:
            return obs
    return None


def origin4_crop_counts(obs):
    out={}
    if not obs:return out
    p=int(obs["player"]);farm=obs["farms"][p]
    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if not (isinstance(t,dict) and t.get("kind")=="PLANT"):
                continue
            if int(t.get("planted_day",-999))!=4:continue
            c=str(t.get("crop"))
            out[c]=out.get(c,0)+1
    return out


def run(agent,is_candidate):
    configure(agent)
    first_transform=None

    def observed(obs):
        nonlocal first_transform
        action=agent.agent(obs)
        if is_candidate:
            tr=agent.get_last_trace()
            if tr.get("modified") and first_transform is None:
                first_transform=copy.deepcopy(tr)
        return action

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=observed
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    d5=first_obs(env,SEAT,5)
    return {
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
            "win":rewards[SEAT]>rewards[1-SEAT],
        },
        "day5_origin4_crop_count":origin4_crop_counts(d5),
        "first_transform":first_transform,
        "telemetry":plain(agent.get_telemetry()),
    }


b=run(baseline,False)
c=run(candidate,True)

payload={
    "schema":"kaggriculture.strong-origin-v2.plant-conflict-transform-battle.paired.v0",
    "seed":SEED,"seat":SEAT,
    "baseline":b,"candidate":c,
    "delta":{
        "terminal_self":c["terminal"]["self"]-b["terminal"]["self"],
        "terminal_opponent":c["terminal"]["opponent"]-b["terminal"]["opponent"],
        "terminal_margin":c["terminal"]["margin"]-b["terminal"]["margin"],
        "day5_origin4_melon":c["day5_origin4_crop_count"].get("MELON",0)-b["day5_origin4_crop_count"].get("MELON",0),
        "day5_origin4_wheat":c["day5_origin4_crop_count"].get("WHEAT",0)-b["day5_origin4_crop_count"].get("WHEAT",0),
        "day5_origin4_strawberry":c["day5_origin4_crop_count"].get("STRAWBERRY",0)-b["day5_origin4_crop_count"].get("STRAWBERRY",0),
    },
    "boundary":[
        "Baseline is unchanged Strong Origin v2 Body-only v0.",
        "Candidate preserves the Body's projected action and changes only Day4 same-empty-tile PLANT conflict transformation.",
        "Candidate never creates a PLANT request, crop choice, target tile, movement, market order, representation, evaluation or direction.",
        "Within a conflict group, highest unit index among already-projected legal PLANT requests gets the one transformable tile opportunity; crop identity is not consulted.",
        "Other conflicting PLANT requests become PASS rather than reaching the public interpreter as guaranteed target-tile no-ops.",
        "No automatic adoption."
    ]
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PLANT_CONFLICT_TRANSFORM_PAIR "+json.dumps({
    "seed":SEED,"seat":SEAT,
    "baseline_terminal":b["terminal"],
    "candidate_terminal":c["terminal"],
    "delta":payload["delta"],
    "baseline_origin4":b["day5_origin4_crop_count"],
    "candidate_origin4":c["day5_origin4_crop_count"],
    "candidate_transform":c["telemetry"].get("winner_crop_counts",{}),
    "modified_turns":c["telemetry"].get("modified_turns",0),
    "conflict_groups":c["telemetry"].get("conflict_groups",0),
},ensure_ascii=False,separators=(",",":")))
