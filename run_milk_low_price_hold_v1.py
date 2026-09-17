#!/usr/bin/env python3
import json
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import milk_low_price_hold_v1 as hold

OPPONENT=base.OPPONENT
CASES=base.DEFAULT_CASES


def play(agent_fn, seed, seat, reset=None):
    base._configure_baseline()
    if reset: reset()
    env=make("kaggriculture", configuration={"seed":seed}, debug=False)
    players=[OPPONENT,OPPONENT]; players[seat]=agent_fn
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return rewards[seat], rewards[seat]-rewards[1-seat]


def main():
    rows=[]
    for seed,seat in CASES:
        b,bm=play(baseline.agent,seed,seat)
        h,hm=play(hold.agent,seed,seat,hold.reset_experiment)
        rows.append({"seed":seed,"seat":seat,"activated":hold.get_hold_count(),"baseline_self":b,"hold_self":h,"self_diff":h-b,
                     "baseline_margin":bm,"hold_margin":hm,"margin_diff":hm-bm})
    mean=lambda k:sum(r[k] for r in rows)/len(rows)
    summary={"case_count":len(rows),"activated_cases":sum(r["activated"]>0 for r in rows),"activation_count":sum(r["activated"] for r in rows),
             "mean_baseline_self":mean("baseline_self"),"mean_hold_self":mean("hold_self"),"mean_self_diff":mean("self_diff"),
             "mean_margin_diff":mean("margin_diff"),"improved":sum(r["self_diff"]>0 for r in rows),
             "worsened":sum(r["self_diff"]<0 for r in rows),"equal":sum(r["self_diff"]==0 for r in rows)}
    out={"hypothesis":"one-shot hold of Day9-10 MILK sell below 180 may improve terminal self",
         "change":"remove only SELL MILK once when day in 9-10 and current MILK price <180; next turn returns to v6 normally",
         "cases":rows,"summary":summary}
    open("milk_low_price_hold_v1.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("MILK_LOW_PRICE_HOLD_V1 "+json.dumps(summary,separators=(",",":")))

if __name__=="__main__": main()
