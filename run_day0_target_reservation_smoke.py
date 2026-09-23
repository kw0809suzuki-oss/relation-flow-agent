#!/usr/bin/env python3
"""Day0 Target Reservation v0 smoke test on one fresh seed."""
import json,os
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import day0_target_reservation_v0 as candidate

SEED=7051; SEAT=0

def configure(agent):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    agent.set_control_enabled(False)
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_telemetry()

def collision_total(agent):
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

def run(agent):
    configure(agent)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    ps=[base.OPPONENT,base.OPPONENT];ps[SEAT]=agent.agent
    env.run(ps)
    rw=[float(x.reward) for x in env.state]
    return {"self":rw[SEAT],"opponent":rw[1-SEAT],"margin":rw[SEAT]-rw[1-SEAT],"day0_plant_collision":collision_total(agent)}

b=run(baseline)
c=run(candidate)
print("DAY0_TARGET_RESERVATION_SMOKE "+json.dumps({"seed":SEED,"baseline":b,"candidate":c,"delta_self":c["self"]-b["self"],"delta_margin":c["margin"]-b["margin"]},ensure_ascii=False,separators=(",",":")))
