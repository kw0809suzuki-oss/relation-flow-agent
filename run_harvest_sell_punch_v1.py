#!/usr/bin/env python3
import json, os
from kaggle_environments import make
import whole_flow_control_agent as baseline
import harvest_sell_punch_v1 as punch

OPPONENT = "opponents/seyamalam_v21.py"
CASES=((3202,0),(3206,0),(3215,1),(3218,0),(3222,0),(3227,1),(3231,1),(3240,0),(3243,1),(3246,0),(3250,0),(3251,1))


def configure(agent):
    os.environ.update({
        "ORIGIN_GATE_POLARITY":"inverted","ORIGIN_GATE_MAGNITUDE":"0.04",
        "G15_CONNECT_OPPONENT_FIELD_DESCRIPTION":"1","G15_ADAPTIVE_W_AMPLITUDE":"1",
        "G15_REMOVE_R_RELATION":"0","G15_REMOVE_E_RELATION":"0","G15_REMOVE_W_RELATION":"0",
        "G15_DISABLE_RESONANCE_CONTROL":"0","ORIGIN_CROP_COMMITMENT":"1"})
    agent.set_control_enabled(False); agent.set_probe_enabled(True); agent.set_attribution_enabled(True); agent.reset_telemetry()


def play(agent,seed,seat):
    configure(agent)
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    players=[OPPONENT,OPPONENT]; players[seat]=agent.agent
    env.run(players); r=[s.reward for s in env.state]
    return float(r[seat]),float(r[seat])-float(r[1-seat])


def main():
    rows=[]
    for seed,seat in CASES:
        b,bm=play(baseline,seed,seat); p,pm=play(punch,seed,seat)
        rows.append({"seed":seed,"seat":seat,"baseline_self":b,"punch_self":p,"self_diff":p-b,"baseline_margin":bm,"punch_margin":pm,"margin_diff":pm-bm})
    mean=lambda k:sum(x[k] for x in rows)/len(rows)
    out={"hypothesis":"shorten harvest-to-sell conversion","policy_change":"prioritize immediate SELL of all sellable shed stock; otherwise preserve base action","cases":rows,"summary":{"case_count":len(rows),"mean_baseline_self":mean("baseline_self"),"mean_punch_self":mean("punch_self"),"mean_self_diff":mean("self_diff"),"mean_margin_diff":mean("margin_diff"),"improved":sum(x["self_diff"]>0 for x in rows),"worsened":sum(x["self_diff"]<0 for x in rows),"equal":sum(x["self_diff"]==0 for x in rows)}}
    open("harvest_sell_punch_v1.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("HARVEST_SELL_PUNCH_V1 "+json.dumps(out["summary"],separators=(",",":")))
if __name__=="__main__": main()
