#!/usr/bin/env python3
"""Operational A/B: existing v6 baseline vs Transition Link v0, same cases."""
import json
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import transition_link_v0 as link

OPPONENT = base.OPPONENT
CASES = base.DEFAULT_CASES


def play(agent_fn, seed, seat):
    base._configure_baseline()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = agent_fn
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return rewards[seat], rewards[seat] - rewards[1-seat]


def main():
    rows=[]
    for seed,seat in CASES:
        b,bm=play(baseline.agent,seed,seat)
        t,tm=play(link.agent,seed,seat)
        rows.append({"seed":seed,"seat":seat,"baseline_self":b,"link_self":t,"self_diff":t-b,
                     "baseline_margin":bm,"link_margin":tm,"margin_diff":tm-bm})
    mean=lambda k:sum(r[k] for r in rows)/len(rows)
    summary={"case_count":len(rows),"mean_baseline_self":mean("baseline_self"),"mean_link_self":mean("link_self"),
             "mean_self_diff":mean("self_diff"),"mean_margin_diff":mean("margin_diff"),
             "improved":sum(r["self_diff"]>0 for r in rows),"worsened":sum(r["self_diff"]<0 for r in rows),
             "equal":sum(r["self_diff"]==0 for r in rows)}
    out={"hypothesis":"same-turn scheduled SELL value should be connected to the next investment decision as a minimal Action->next-State link",
         "change":"v6 unchanged; wrapper may insert BUY_LAND after scheduled SELLs when sell-value makes the existing v6 reserve/occupancy/remaining-days gate affordable",
         "cases":rows,"summary":summary}
    open("transition_link_v0.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("TRANSITION_LINK_V0 "+json.dumps(summary,separators=(",",":")))

if __name__=="__main__": main()
