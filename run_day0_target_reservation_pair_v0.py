#!/usr/bin/env python3
"""Paired fresh10: Day0 Target Reservation v0 vs current baseline."""
import json,os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as basecfg
import whole_flow_control_agent as baseline
import day0_target_reservation_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"day0_target_reservation_pair_{SEED}.json")


def configure(agent):
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    agent.set_control_enabled(False)
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_telemetry()


def plant_collision(agent):
    tr=agent.get_trace()
    snaps=tr["body"]["observe"]["body"]["snapshots"]
    total=0
    for s in snaps:
        if int(s.get("day",0) or 0)!=0:continue
        pos=s.get("unit_pos_sig")
        positions=[tuple(pos[0])]+[tuple(x) for x in pos[1]]
        act=s.get("action") or {}
        acts=[act.get("farmer",["PASS"])]+list(act.get("hands",[]) or [])
        groups={}
        for idx,a in enumerate(acts):
            if idx>=len(positions):continue
            if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT":
                k=(positions[idx],a[1]);groups[k]=groups.get(k,0)+1
        total+=sum(max(0,n-1) for n in groups.values())
    return total


def first_day1_melon(env,seat):
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<2:continue
        obs=step[seat].observation
        try:
            day=int(obs["day"])
        except Exception:
            try: day=int(obs.day)
            except Exception: continue
        if day!=1:continue
        try: player=int(obs["player"])
        except Exception: player=int(obs.player)
        farms=obs["farms"] if isinstance(obs,dict) else obs.farms
        farm=farms[player]
        tiles=farm["tiles"] if isinstance(farm,dict) else farm.tiles
        n=0
        for row in tiles:
            for tile in row:
                if isinstance(tile,dict) and tile.get("crop")=="MELON" and int(tile.get("planted_day",-999))==0:
                    n+=1
        return n
    return None


def run(agent):
    configure(agent)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    ps=[basecfg.OPPONENT,basecfg.OPPONENT];ps[SEAT]=agent.agent
    env.run(ps)
    rewards=[float(x.reward) for x in env.state]
    return {
      "self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],
      "day0_plant_collision":plant_collision(agent),
      "day1_melon_planted":first_day1_melon(env,SEAT),
    }


b=run(baseline)
c=run(candidate)
payload={
 "seed":SEED,"seat":SEAT,"baseline":b,"candidate":c,
 "delta_self":c["self"]-b["self"],"delta_opponent":c["opponent"]-b["opponent"],"delta_margin":c["margin"]-b["margin"],
 "boundary":["Only Day0 Strong Origin work-target reservation differs.","Crop targets/scores, market logic, livestock logic and post-Day0 Strong Origin behavior are unchanged."]
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("DAY0_TARGET_RESERVATION_PAIR "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))
