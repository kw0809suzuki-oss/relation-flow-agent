#!/usr/bin/env python3
"""SB-01 base-vs-final hand collision preflight.

One unchanged SB-01 replay. Reads G15 snapshots after run and compares the
Strong Origin base_action with the final action after the livestock overlay.
"""
import json,os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED=7001; SEAT=0
OUT=Path("sb01_base_vs_final_hand_collision_7001.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def plant_collision(action,unit_pos_sig):
    positions=[tuple(unit_pos_sig[0])]+[tuple(x) for x in unit_pos_sig[1]]
    acts=[(action or {}).get("farmer",["PASS"])]
    hs=(action or {}).get("hands",[])
    if isinstance(hs,list):acts.extend(hs)
    groups={}
    for idx,a in enumerate(acts):
        if idx>=len(positions):continue
        if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT":
            key=(positions[idx],a[1])
            groups[key]=groups.get(key,0)+1
    return sum(max(0,n-1) for n in groups.values())

def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[base.OPPONENT,base.OPPONENT];players[SEAT]=combat.agent
    env.run(players)
    trace=combat.get_trace()
    snaps=trace["body"]["observe"]["body"]["snapshots"]
    rows=[]
    for s in snaps:
        if int(s.get("day",0) or 0)!=0:continue
        pos=s.get("unit_pos_sig")
        b=s.get("base_action") or {}
        f=s.get("action") or {}
        rows.append({
          "turn":s.get("turn"),"day":s.get("day"),"positions":pos,
          "base_collision":plant_collision(b,pos),
          "final_collision":plant_collision(f,pos),
          "overlay_changed_hands":bool(s.get("overlay_changed_hands")),
          "base_hands":b.get("hands",[]),"final_hands":f.get("hands",[])
        })
    payload={
      "seed":SEED,"rows":rows,
      "summary":{
        "base_collision_total":sum(r["base_collision"] for r in rows),
        "final_collision_total":sum(r["final_collision"] for r in rows),
        "turns_overlay_changed_hands":sum(r["overlay_changed_hands"] for r in rows),
        "collision_turns_base":[r["turn"] for r in rows if r["base_collision"]>0],
        "collision_turns_final":[r["turn"] for r in rows if r["final_collision"]>0],
      },
      "boundary":["Observer-only trace read after unchanged replay.","base_action is Strong Origin output before livestock overlay.","final action is the executed agent output after overlay."]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SB01_BASE_VS_FINAL_COLLISION "+json.dumps(payload["summary"],ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
